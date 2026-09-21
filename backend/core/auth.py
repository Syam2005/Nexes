"""
NEXUS — Authentication Layer
Google OAuth2 (primary) + GitHub OAuth2 (secondary/connections)
JWT sessions stored server-side in DB. No localStorage on client.

EMAIL STRATEGY:
- Google login always has a real verified email → use it directly
- GitHub login: if user has public email on GitHub → use it
- GitHub login: if no public email → check if a Google account already
  exists with the same GitHub username or display name → merge/link
- GitHub login: if truly no match → create account but flag email as
  unverified so email reports are disabled until user links Google
"""
import uuid
import httpx
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.config import settings
from core.database import get_db, User, GitHubConnection

bearer_scheme = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"

# Sentinel suffix — used internally only, never shown to users as report destination
NOEMAIL_SUFFIX = "@github.noemail"


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def is_real_email(email: str) -> bool:
    """Returns False for placeholder emails created when GitHub has no public email."""
    return bool(email) and NOEMAIL_SUFFIX not in email


# ── Current User ──────────────────────────────────────────────────────────────

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = decode_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


# ── Google OAuth ──────────────────────────────────────────────────────────────

GOOGLE_TOKEN_URL    = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


async def exchange_google_code(code: str, redirect_uri: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        })
        r.raise_for_status()
        token_data = r.json()

        info = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        info.raise_for_status()
        return info.json()


async def upsert_google_user(db: AsyncSession, google_info: dict) -> User:
    email = google_info["email"]
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # Also check if there's a GitHub-created account with a placeholder email
        # that might belong to this Google user (same display name)
        # This merges accounts when user first signed up via GitHub then uses Google
        name = google_info.get("name", "")
        if name:
            result2 = await db.execute(
                select(User).where(
                    User.name == name,
                    User.auth_provider == "github",
                )
            )
            existing_github_user = result2.scalar_one_or_none()
            if existing_github_user and not is_real_email(existing_github_user.email):
                # Upgrade the placeholder GitHub account to have the real Google email
                existing_github_user.email = email
                existing_github_user.photo_url = google_info.get("picture", existing_github_user.photo_url)
                existing_github_user.auth_provider = "google"
                existing_github_user.updated_at = datetime.utcnow()
                await db.commit()
                await db.refresh(existing_github_user)
                return existing_github_user

        user = User(
            id=str(uuid.uuid4()),
            email=email,
            name=google_info.get("name", email),
            photo_url=google_info.get("picture"),
            auth_provider="google",
        )
        db.add(user)
    else:
        user.photo_url = google_info.get("picture", user.photo_url)
        user.name = google_info.get("name", user.name)
        user.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(user)
    return user


# ── GitHub OAuth ──────────────────────────────────────────────────────────────

GITHUB_TOKEN_URL    = "https://github.com/login/oauth/access_token"
GITHUB_USERINFO_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL   = "https://api.github.com/user/emails"


async def exchange_github_code(code: str, redirect_uri: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        token_data = r.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(400, "GitHub OAuth failed: no access_token")

        info = await client.get(
            GITHUB_USERINFO_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        info.raise_for_status()
        user_info = info.json()
        user_info["_access_token"] = access_token

        # If GitHub profile has no public email, try fetching verified emails
        if not user_info.get("email"):
            try:
                emails_resp = await client.get(
                    GITHUB_EMAILS_URL,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github+json",
                    },
                )
                if emails_resp.status_code == 200:
                    emails = emails_resp.json()
                    # Prefer primary verified email
                    for e in emails:
                        if e.get("primary") and e.get("verified"):
                            user_info["email"] = e["email"]
                            break
                    # Fallback: any verified email
                    if not user_info.get("email"):
                        for e in emails:
                            if e.get("verified"):
                                user_info["email"] = e["email"]
                                break
            except Exception:
                pass  # Non-fatal — will fall back to placeholder below

        return user_info


async def upsert_github_login_user(db: AsyncSession, gh_info: dict) -> User:
    """
    Used when someone logs in DIRECTLY with GitHub.
    Priority order for email:
    1. Public GitHub email
    2. Verified email from /user/emails API
    3. Check if Google account exists with same name → link to it
    4. Create new account with placeholder (email reports disabled)
    """
    github_email = gh_info.get("email")
    github_login = gh_info["login"]
    github_name  = gh_info.get("name") or github_login

    # 1. Try to find existing user by real GitHub email
    if github_email and is_real_email(github_email):
        result = await db.execute(select(User).where(User.email == github_email))
        user = result.scalar_one_or_none()
        if user:
            user.photo_url = gh_info.get("avatar_url", user.photo_url)
            user.name = github_name or user.name
            user.updated_at = datetime.utcnow()
            await upsert_github_connection(db, user.id, gh_info)
            await db.commit()
            await db.refresh(user)
            return user

    # 2. Try to find existing Google account with same display name
    # This handles: user signed up with Google first, now logging in via GitHub
    if github_name:
        result = await db.execute(
            select(User).where(
                User.name == github_name,
                User.auth_provider == "google",
            )
        )
        google_user = result.scalar_one_or_none()
        if google_user:
            # Link GitHub to the existing Google account silently
            await upsert_github_connection(db, google_user.id, gh_info)
            await db.commit()
            await db.refresh(google_user)
            return google_user

    # 3. Check by placeholder email (returning GitHub-only user)
    placeholder_email = f"{github_login}{NOEMAIL_SUFFIX}"
    result = await db.execute(select(User).where(User.email == placeholder_email))
    user = result.scalar_one_or_none()

    if not user:
        # 4. Create new account
        # Use real email if we got one, otherwise placeholder
        email_to_use = github_email if (github_email and is_real_email(github_email)) else placeholder_email
        user = User(
            id=str(uuid.uuid4()),
            email=email_to_use,
            name=github_name,
            photo_url=gh_info.get("avatar_url"),
            auth_provider="github",
            # Disable email reports if we only have a placeholder email
            email_reports=is_real_email(email_to_use),
        )
        db.add(user)
        await db.flush()

    # Always upsert the GitHub connection
    await upsert_github_connection(db, user.id, gh_info)
    await db.commit()
    await db.refresh(user)
    return user


async def upsert_github_connection(
    db: AsyncSession, user_id: str, gh_info: dict
) -> GitHubConnection:
    """Connect a GitHub account to an existing user (multi-GitHub support)."""
    github_user_id = str(gh_info["id"])
    result = await db.execute(
        select(GitHubConnection).where(
            GitHubConnection.user_id == user_id,
            GitHubConnection.github_user_id == github_user_id,
        )
    )
    conn = result.scalar_one_or_none()

    if not conn:
        existing = await db.execute(
            select(GitHubConnection).where(GitHubConnection.user_id == user_id)
        )
        is_first = existing.scalar_one_or_none() is None

        conn = GitHubConnection(
            id=str(uuid.uuid4()),
            user_id=user_id,
            github_username=gh_info["login"],
            github_user_id=github_user_id,
            access_token=gh_info["_access_token"],
            avatar_url=gh_info.get("avatar_url"),
            is_primary=is_first,
        )
        db.add(conn)
    else:
        conn.access_token    = gh_info["_access_token"]
        conn.avatar_url      = gh_info.get("avatar_url")
        conn.github_username = gh_info["login"]

    await db.flush()
    return conn