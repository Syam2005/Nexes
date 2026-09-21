"""
NEXUS — FastAPI Application Entry Point
All routes, WebSocket, CORS, startup.

GITHUB OAUTH STRATEGY:
GitHub only allows ONE callback URL per OAuth app.
We use a single callback /auth/github/callback for BOTH login and connect.
The 'state' parameter encodes intent:
  - state starts with "connect:" → connecting to existing account (token follows)
  - state is empty / "login"    → fresh login
"""
import uuid
import json
import asyncio
import hmac
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import aiofiles
from fastapi import (
    FastAPI, Depends, HTTPException, UploadFile, File,
    Form, BackgroundTasks, WebSocket, WebSocketDisconnect, Request
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel

from core.config import settings
from core.database import (
    init_db, get_db, User, Analysis, ProposedChange, GitHubConnection
)
from core.auth import (
    create_access_token, get_current_user, decode_token,
    exchange_google_code, upsert_google_user,
    exchange_github_code, upsert_github_login_user, upsert_github_connection,
)
from core.observability import configure_logging, register_ws, unregister_ws, broadcast
from core.pipeline import run_pipeline
from core.email_service import send_report_email
from agents.documenter import build_html_email

import structlog
logger = structlog.get_logger()

configure_logging()

app = FastAPI(
    title="NEXUS — Agentic Codebase Modernization",
    version="3.0.0",
    description="Team Algerithm | Capgemini ExcellEr AgentifAI Buildathon 2026",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await init_db()
    logger.info("nexus_started", version="3.0.0")


# ════════════════════════════════════════════════════════════════════
# AUTH ROUTES
# ════════════════════════════════════════════════════════════════════

class GoogleCallbackRequest(BaseModel):
    code: str
    redirect_uri: str

class GitHubCallbackRequest(BaseModel):
    code: str
    redirect_uri: str


@app.get("/auth/google/login")
async def google_login():
    from fastapi.responses import RedirectResponse
    redirect_uri = f"{settings.BACKEND_URL}/auth/google/callback"
    url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
        "&access_type=offline"
    )
    return RedirectResponse(url=url)


@app.get("/auth/google/callback")
async def google_callback_get(code: str, db: AsyncSession = Depends(get_db)):
    from fastapi.responses import RedirectResponse
    import urllib.parse
    try:
        redirect_uri = f"{settings.BACKEND_URL}/auth/google/callback"
        google_info = await exchange_google_code(code, redirect_uri)
        user = await upsert_google_user(db, google_info)
        token = create_access_token(user.id)
        user_data = json.dumps({
            "id": user.id, "email": user.email, "name": user.name,
            "photo_url": user.photo_url, "auth_provider": user.auth_provider,
            "email_reports": user.email_reports,
            "risk_threshold": user.risk_threshold, "theme": user.theme,
        })
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback"
                f"?token={token}&user={urllib.parse.quote(user_data)}"
        )
    except Exception as e:
        logger.error("google_callback_failed", error=str(e))
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error={str(e)}")


@app.get("/auth/github/login")
async def github_login():
    """Login intent — state=login."""
    from fastapi.responses import RedirectResponse
    redirect_uri = f"{settings.BACKEND_URL}/auth/github/callback"
    url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        "&scope=repo%20user"
        "&state=login"
    )
    return RedirectResponse(url=url)


@app.get("/auth/github/connect")
async def github_connect_redirect(token: Optional[str] = None):
    """
    Connect intent — state=connect:<jwt>.
    Frontend passes the JWT as ?token= query param.
    Same callback URL as login — only ONE URL needed in GitHub OAuth app settings.
    """
    from fastapi.responses import RedirectResponse
    import urllib.parse

    if not token:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/profile?error=Not+authenticated"
        )
    user_id = decode_token(token)
    if not user_id:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/profile?error=Invalid+or+expired+session"
        )

    state = f"connect:{token}"
    redirect_uri = f"{settings.BACKEND_URL}/auth/github/callback"
    url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        "&scope=repo%20user"
        f"&state={urllib.parse.quote(state)}"
    )
    return RedirectResponse(url=url)


@app.get("/auth/github/callback")
async def github_callback_unified(
    code: str,
    state: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Single unified GitHub OAuth callback.
    state == "login" (or empty)   → fresh GitHub login
    state starts "connect:<token>" → connect to existing user
    Register ONLY this URL in your GitHub OAuth app:
        https://nexus-1-dndd.onrender.com/auth/github/callback
    """
    from fastapi.responses import RedirectResponse
    import urllib.parse

    redirect_uri = f"{settings.BACKEND_URL}/auth/github/callback"

    try:
        gh_info = await exchange_github_code(code, redirect_uri)
    except Exception as e:
        logger.error("github_code_exchange_failed", error=str(e))
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error=GitHub+authentication+failed"
        )

    # ── CONNECT flow ──────────────────────────────────────────────────────
    if state and state.startswith("connect:"):
        jwt_token = state[len("connect:"):]
        user_id = decode_token(jwt_token)
        if not user_id:
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/profile?error=Session+expired.+Please+log+in+again."
            )
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/profile?error=User+not+found"
            )
        try:
            await upsert_github_connection(db, user.id, gh_info)
            await db.commit()
            logger.info("github_connected", user_id=user.id, github=gh_info.get("login"))
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/profile?connected=true")
        except Exception as e:
            logger.error("github_connect_failed", error=str(e))
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/profile?error=Connection+failed"
            )

    # ── LOGIN flow ────────────────────────────────────────────────────────
    try:
        user = await upsert_github_login_user(db, gh_info)
        token = create_access_token(user.id)
        user_data = json.dumps({
            "id": user.id, "email": user.email, "name": user.name,
            "photo_url": user.photo_url, "auth_provider": user.auth_provider,
            "email_reports": user.email_reports,
            "risk_threshold": user.risk_threshold, "theme": user.theme,
        })
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback"
                f"?token={token}&user={urllib.parse.quote(user_data)}"
        )
    except Exception as e:
        logger.error("github_login_failed", error=str(e))
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/login?error=GitHub+login+failed"
        )


@app.post("/auth/github/callback")
async def github_login_callback_post(
    body: GitHubCallbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """POST version for API clients."""
    try:
        gh_info = await exchange_github_code(body.code, body.redirect_uri)
        user = await upsert_github_login_user(db, gh_info)
        token = create_access_token(user.id)
        return {"access_token": token, "token_type": "bearer", "user": _user_to_dict(user)}
    except Exception as e:
        raise HTTPException(400, f"GitHub authentication failed: {str(e)}")


@app.delete("/auth/github/{connection_id}")
async def disconnect_github(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GitHubConnection).where(
            GitHubConnection.id == connection_id,
            GitHubConnection.user_id == current_user.id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(404, "GitHub connection not found")
    await db.delete(conn)
    await db.commit()
    return {"message": "GitHub disconnected"}


# ════════════════════════════════════════════════════════════════════
# USER / PROFILE ROUTES
# ════════════════════════════════════════════════════════════════════

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email_reports: Optional[bool] = None
    risk_threshold: Optional[str] = None
    theme: Optional[str] = None


@app.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(GitHubConnection).where(GitHubConnection.user_id == current_user.id)
    )
    connections = result.scalars().all()
    user_dict = _user_to_dict(current_user)
    user_dict["github_connections"] = [_conn_to_dict(c) for c in connections]
    return user_dict


@app.patch("/me")
async def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.name is not None:           current_user.name = body.name
    if body.phone is not None:          current_user.phone = body.phone
    if body.email_reports is not None:  current_user.email_reports = body.email_reports
    if body.risk_threshold is not None: current_user.risk_threshold = body.risk_threshold
    if body.theme is not None:          current_user.theme = body.theme
    current_user.updated_at = datetime.utcnow()
    await db.commit()
    return _user_to_dict(current_user)


@app.patch("/me/settings")
async def update_settings(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.email_reports is not None:  current_user.email_reports = body.email_reports
    if body.risk_threshold is not None: current_user.risk_threshold = body.risk_threshold
    if body.theme is not None:          current_user.theme = body.theme
    current_user.updated_at = datetime.utcnow()
    await db.commit()
    return _user_to_dict(current_user)


# ════════════════════════════════════════════════════════════════════
# GITHUB REPO ROUTES
# ════════════════════════════════════════════════════════════════════

@app.get("/github/repos")
async def list_repos(
    connection_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from github import Github
    conn = await _get_github_conn(db, current_user.id, connection_id)
    if not conn:
        raise HTTPException(404, "No GitHub connection found")
    try:
        gh = Github(conn.access_token)
        repos = []
        for repo in gh.get_user().get_repos(sort="updated")[:50]:
            repos.append({
                "id": repo.id, "full_name": repo.full_name, "name": repo.name,
                "description": repo.description, "language": repo.language,
                "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
                "private": repo.private, "stars": repo.stargazers_count,
                "default_branch": repo.default_branch,
            })
        return {"repos": repos, "github_username": conn.github_username}
    except Exception as e:
        raise HTTPException(400, f"GitHub API error: {str(e)}")


@app.get("/github/repos/{owner}/{repo}/tree")
async def get_repo_tree(
    owner: str, repo: str,
    connection_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from github import Github
    conn = await _get_github_conn(db, current_user.id, connection_id)
    if not conn:
        raise HTTPException(404, "No GitHub connection found")
    try:
        gh = Github(conn.access_token)
        repository = gh.get_repo(f"{owner}/{repo}")
        tree = repository.get_git_tree(repository.default_branch, recursive=True)
        files = [
            {"path": item.path, "size": item.size, "url": item.url}
            for item in tree.tree
            if item.type == "blob"
            and Path(item.path).suffix.lower() in {
                ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
                ".rs", ".cpp", ".c", ".rb", ".php", ".cs", ".kt", ".swift"
            }
        ]
        return {
            "repo": f"{owner}/{repo}",
            "branch": repository.default_branch,
            "total_files": len(files),
            "files": files[:settings.MAX_REPO_FILES],
        }
    except Exception as e:
        raise HTTPException(400, f"GitHub API error: {str(e)}")


# ════════════════════════════════════════════════════════════════════
# ANALYSIS ROUTES
# ════════════════════════════════════════════════════════════════════

@app.post("/analyze/file")
async def analyze_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    size_kb = len(content) / 1024
    if size_kb > settings.MAX_FILE_SIZE_KB:
        raise HTTPException(413, f"File too large ({size_kb:.0f}KB). Max {settings.MAX_FILE_SIZE_KB}KB.")
    if b"\x00" in content[:8192]:
        raise HTTPException(400, "Binary files are not supported")
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "File must be UTF-8 encoded")

    analysis = Analysis(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        input_mode="file",
        source_name=file.filename,
    )
    db.add(analysis)
    await db.commit()

    background_tasks.add_task(
        _run_analysis_bg,
        analysis.id,
        [{"path": file.filename, "content": text_content}],
        current_user,
        text_content,
    )
    return {"analysis_id": analysis.id, "status": "pending", "source": file.filename}


@app.post("/analyze/url")
async def analyze_url(
    background_tasks: BackgroundTasks,
    repo_url: str = Form(...),
    file_paths: Optional[str] = Form(None),
    connection_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from github import Github, GithubException
    conn = await _get_github_conn(db, current_user.id, connection_id)
    token = conn.access_token if conn else None
    try:
        gh = Github(token) if token else Github()
        repo_name = _parse_repo_name(repo_url)
        repository = gh.get_repo(repo_name)
        selected_paths = None
        if file_paths and file_paths != "all":
            selected_paths = set(p.strip() for p in file_paths.split(",") if p.strip())
        files = await _fetch_repo_files(repository, selected_paths)
        if not files:
            raise HTTPException(400, "No supported files found in repository")
        analysis = Analysis(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            input_mode="url",
            source_name=repo_name,
            github_repo=repo_url,
            github_connection_id=conn.id if conn else None,
        )
        db.add(analysis)
        await db.commit()
        background_tasks.add_task(_run_analysis_bg, analysis.id, files, current_user)
        return {
            "analysis_id": analysis.id, "status": "pending",
            "source": repo_name, "total_files": len(files),
        }
    except GithubException as e:
        raise HTTPException(400, f"GitHub error: {e.data.get('message', str(e))}")


@app.get("/analysis/{analysis_id}")
async def get_analysis(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Analysis).where(
            Analysis.id == analysis_id,
            Analysis.user_id == current_user.id,
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(404, "Analysis not found")
    changes_result = await db.execute(
        select(ProposedChange).where(ProposedChange.analysis_id == analysis_id)
    )
    changes = changes_result.scalars().all()
    return {**_analysis_to_dict(analysis), "changes": [_change_to_dict(c) for c in changes]}


@app.get("/history")
async def get_history(
    limit: int = 20,
    offset: int = 0,
    language: Optional[str] = None,
    risk: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Analysis).where(Analysis.user_id == current_user.id)
    if language:
        query = query.where(Analysis.language == language)
    if risk:
        query = query.where(Analysis.overall_risk == risk.upper())
    query = query.order_by(Analysis.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    analyses = result.scalars().all()
    return {"analyses": [_analysis_to_dict(a) for a in analyses], "total": len(analyses)}


# ════════════════════════════════════════════════════════════════════
# APPROVAL + COMMIT ROUTES
# ════════════════════════════════════════════════════════════════════

class ApproveChangesRequest(BaseModel):
    change_ids: List[str]
    skip_ids: Optional[List[str]] = []


@app.post("/analysis/{analysis_id}/approve")
async def approve_changes(
    analysis_id: str,
    body: ApproveChangesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Analysis).where(
            Analysis.id == analysis_id, Analysis.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(404, "Analysis not found")
    for change_id in body.change_ids:
        r = await db.execute(select(ProposedChange).where(ProposedChange.id == change_id))
        c = r.scalar_one_or_none()
        if c: c.status = "accepted"
    for change_id in (body.skip_ids or []):
        r = await db.execute(select(ProposedChange).where(ProposedChange.id == change_id))
        c = r.scalar_one_or_none()
        if c: c.status = "skipped"
    await db.commit()
    return {"message": f"{len(body.change_ids)} approved, {len(body.skip_ids or [])} skipped"}


@app.post("/analysis/{analysis_id}/commit")
async def commit_changes(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from github import Github
    result = await db.execute(
        select(Analysis).where(
            Analysis.id == analysis_id, Analysis.user_id == current_user.id,
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis or not analysis.github_repo:
        raise HTTPException(400, "No GitHub repo to commit to")
    changes_result = await db.execute(
        select(ProposedChange).where(
            ProposedChange.analysis_id == analysis_id,
            ProposedChange.status == "accepted",
        )
    )
    accepted = changes_result.scalars().all()
    if not accepted:
        raise HTTPException(400, "No accepted changes to commit")
    conn = await _get_github_conn(db, current_user.id, analysis.github_connection_id)
    if not conn:
        raise HTTPException(400, "No GitHub connection found")
    try:
        gh = Github(conn.access_token)
        repository = gh.get_repo(_parse_repo_name(analysis.github_repo))
        files_map: dict = {}
        for change in accepted:
            files_map.setdefault(change.file_path, []).append(change)
        committed = []
        for file_path, file_changes in files_map.items():
            file_obj = repository.get_contents(file_path)
            content = file_obj.decoded_content.decode("utf-8")
            from core.diff_engine import apply_changes
            modified = apply_changes(content, [_change_to_dict(c) for c in file_changes])["modified_file"]
            if modified == content:
                continue
            change_types = list({c.issue_type for c in file_changes})
            commit_msg = (
                f"[NEXUS] Modernize {file_path}: {len(file_changes)} changes\n\n"
                + "\n".join(f"- {t}" for t in change_types)
                + f"\n\nNEXUS v3.0 | Analysis: {analysis_id[:8]}"
            )
            repository.update_file(file_path, commit_msg, modified, file_obj.sha)
            for c in file_changes: c.status = "committed"
            committed.append(file_path)
        await db.commit()
        return {"message": f"Committed to {len(committed)} files", "committed_files": committed}
    except Exception as e:
        raise HTTPException(500, f"Commit failed: {str(e)}")


@app.get("/analysis/{analysis_id}/download")
async def download_analysis(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from fastapi.responses import Response
    result = await db.execute(
        select(Analysis).where(
            Analysis.id == analysis_id, Analysis.user_id == current_user.id,
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(404, "Analysis not found")
    changes_result = await db.execute(
        select(ProposedChange).where(
            ProposedChange.analysis_id == analysis_id, ProposedChange.status == "accepted",
        )
    )
    accepted = changes_result.scalars().all()
    if not accepted:
        raise HTTPException(400, "No accepted changes to download")
    original = (analysis.full_report or {}).get("original_content", "")
    if not original:
        raise HTTPException(404, "Original content not stored. Please re-analyse.")
    from core.diff_engine import apply_changes
    modified = apply_changes(original, [_change_to_dict(c) for c in accepted])["modified_file"]
    return Response(
        content=modified, media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="modernized_{analysis.source_name}"'},
    )


@app.get("/analysis/{analysis_id}/report")
async def download_report(
    analysis_id: str,
    format: str = "markdown",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from fastapi.responses import Response
    result = await db.execute(
        select(Analysis).where(
            Analysis.id == analysis_id, Analysis.user_id == current_user.id,
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(404, "Analysis not found")
    if format == "markdown":
        return Response(
            content=analysis.report_markdown or "No report available.",
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="nexus-report-{analysis_id[:8]}.md"'},
        )
    return Response(
        content=str(analysis.full_report or "{}"),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="nexus-report-{analysis_id[:8]}.json"'},
    )


# ════════════════════════════════════════════════════════════════════
# PER-CHANGE ROUTES
# ════════════════════════════════════════════════════════════════════

@app.post("/changes/{change_id}/approve")
async def approve_change(
    change_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(ProposedChange).where(ProposedChange.id == change_id))
    change = r.scalar_one_or_none()
    if not change: raise HTTPException(404, "Change not found")
    change.status = "accepted"
    await db.commit()
    return {"message": "Change accepted", "id": change_id}


@app.post("/changes/{change_id}/skip")
async def skip_change(
    change_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(ProposedChange).where(ProposedChange.id == change_id))
    change = r.scalar_one_or_none()
    if not change: raise HTTPException(404, "Change not found")
    change.status = "skipped"
    await db.commit()
    return {"message": "Change skipped", "id": change_id}


@app.get("/analyses/{analysis_id}/changes")
async def get_changes(
    analysis_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(ProposedChange).where(ProposedChange.analysis_id == analysis_id))
    return [_change_to_dict(c) for c in r.scalars().all()]


# ════════════════════════════════════════════════════════════════════
# WEBHOOK
# ════════════════════════════════════════════════════════════════════

@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    mac = hmac.HMAC(settings.WEBHOOK_SECRET.encode(), body, hashlib.sha256)
    expected = "sha256=" + mac.hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(403, "Invalid webhook signature")
    payload = json.loads(body)
    event = request.headers.get("X-GitHub-Event")
    if event == "pull_request" and payload.get("action") in ("opened", "synchronize"):
        pr = payload.get("pull_request", {})
        repo_url = pr.get("head", {}).get("repo", {}).get("clone_url", "")
        analysis = Analysis(
            id=str(uuid.uuid4()), input_mode="cicd",
            source_name=repo_url, github_repo=repo_url, status="pending",
        )
        db.add(analysis)
        await db.commit()
        logger.info("webhook_triggered", analysis_id=analysis.id, repo=repo_url)
    return {"status": "received"}


# ════════════════════════════════════════════════════════════════════
# WEBSOCKET
# ════════════════════════════════════════════════════════════════════

@app.websocket("/ws/{analysis_id}")
async def websocket_endpoint(websocket: WebSocket, analysis_id: str):
    await websocket.accept()
    register_ws(analysis_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        unregister_ws(analysis_id, websocket)


# ════════════════════════════════════════════════════════════════════
# HEALTH
# ════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {"status": "ok", "version": "3.0.0", "team": "Algerithm"}


# ════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════

async def _run_analysis_bg(
    analysis_id: str,
    files: list,
    user: User,
    original_content: str = "",
):
    """
    Background task: runs pipeline then sends email report.
    Every email decision point is logged — check Render backend logs
    to see exactly why an email was or wasn't sent.
    """
    from core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            await run_pipeline(analysis_id, files, db)

            result = await db.execute(select(Analysis).where(Analysis.id == analysis_id))
            analysis = result.scalar_one_or_none()

            # Store original content for download
            if analysis and original_content:
                report_copy = dict(analysis.full_report or {})
                report_copy["original_content"] = original_content
                analysis.full_report = report_copy
                await db.commit()

            if not analysis:
                logger.error("email_skipped_analysis_not_found", analysis_id=analysis_id)
                return

            # Log the email decision so you can diagnose in Render logs
            logger.info(
                "email_decision_check",
                analysis_id=analysis_id,
                user_email=user.email,
                user_email_reports=user.email_reports,
                analysis_status=analysis.status,
                has_full_report=bool(analysis.full_report),
            )

            if not user.email_reports:
                logger.warning(
                    "email_skipped_user_disabled",
                    analysis_id=analysis_id,
                    user_email=user.email,
                    hint="email_reports=False in DB — go to Settings and enable, or log out "
                         "and sign in with Google to get a real email address",
                )
                return

            if not analysis.full_report:
                logger.warning(
                    "email_skipped_no_report",
                    analysis_id=analysis_id,
                )
                return

            # Get report data — try nested "report" key first, fall back to full dict
            report_data = analysis.full_report.get("report") or analysis.full_report

            # Build the real link to the analysis page on the frontend
            report_url = f"{settings.FRONTEND_URL}/analysis/{analysis_id}"

            try:
                html = build_html_email(report_data, user.name, analysis.source_name, report_url)
            except Exception as e:
                logger.error("email_html_build_failed", analysis_id=analysis_id, error=str(e))
                return

            send_report_email(
                user.email,
                user.name,
                analysis.source_name,
                html,
                analysis_id,
            )

        except Exception as e:
            logger.error("background_pipeline_failed", analysis_id=analysis_id, error=str(e))


async def _fetch_repo_files(repository, selected_paths=None) -> list:
    supported_exts = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
        ".cpp", ".c", ".rb", ".php", ".cs", ".kt", ".swift"
    }
    files = []
    tree = repository.get_git_tree(repository.default_branch, recursive=True)
    for item in tree.tree:
        if item.type != "blob": continue
        if selected_paths and item.path not in selected_paths: continue
        if Path(item.path).suffix.lower() not in supported_exts: continue
        if item.size and item.size > settings.MAX_FILE_SIZE_KB * 1024: continue
        if len(files) >= settings.MAX_REPO_FILES: break
        path_lower = item.path.lower()
        if any(s in path_lower for s in [
            "node_modules", "vendor", "dist/", "build/", ".min.",
            "package-lock", "yarn.lock", "__pycache__"
        ]): continue
        try:
            fc = repository.get_contents(item.path)
            files.append({"path": item.path, "content": fc.decoded_content.decode("utf-8", errors="replace")})
        except Exception:
            continue
    return files


async def _get_github_conn(db: AsyncSession, user_id: str, connection_id: Optional[str]):
    if connection_id:
        r = await db.execute(
            select(GitHubConnection).where(
                GitHubConnection.id == connection_id,
                GitHubConnection.user_id == user_id,
            )
        )
        return r.scalar_one_or_none()
    r = await db.execute(
        select(GitHubConnection).where(
            GitHubConnection.user_id == user_id,
            GitHubConnection.is_primary == True,
        )
    )
    return r.scalar_one_or_none()


def _parse_repo_name(url: str) -> str:
    url = url.rstrip("/").replace(".git", "")
    parts = url.split("/")
    return f"{parts[-2]}/{parts[-1]}"


def _user_to_dict(user: User) -> dict:
    return {
        "id": user.id, "email": user.email, "name": user.name,
        "photo_url": user.photo_url, "phone": user.phone,
        "auth_provider": user.auth_provider, "email_reports": user.email_reports,
        "risk_threshold": user.risk_threshold, "theme": user.theme,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _conn_to_dict(conn: GitHubConnection) -> dict:
    return {
        "id": conn.id, "github_username": conn.github_username,
        "avatar_url": conn.avatar_url, "is_primary": conn.is_primary,
        "connected_at": conn.connected_at.isoformat() if conn.connected_at else None,
    }


def _analysis_to_dict(a: Analysis) -> dict:
    return {
        "id": a.id, "status": a.status, "input_mode": a.input_mode,
        "source_name": a.source_name, "github_repo": a.github_repo,
        "language": a.language, "era": a.era,
        "language_breakdown": a.language_breakdown,
        "total_files": a.total_files, "total_issues": a.total_issues,
        "security_issues": a.security_issues, "overall_risk": a.overall_risk,
        "minimality_score": a.minimality_score,
        "complexity_before": a.complexity_before, "complexity_after": a.complexity_after,
        "confidence_score": a.confidence_score,
        "estimated_hours_saved": a.estimated_hours_saved,
        "tests_passed": a.tests_passed, "test_count": a.test_count,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "completed_at": a.completed_at.isoformat() if a.completed_at else None,
        "error_message": a.error_message,
        "full_report": a.full_report, "report_markdown": a.report_markdown,
    }


def _change_to_dict(c: ProposedChange) -> dict:
    return {
        "id": c.id, "file_path": c.file_path, "issue_type": c.issue_type,
        "description": c.description, "old_code": c.old_code, "new_code": c.new_code,
        "line_start": c.line_start, "line_end": c.line_end,
        "risk_level": c.risk_level, "risk_reason": c.risk_reason,
        "confidence": c.confidence, "priority": c.priority,
        "callers": c.callers, "status": c.status,
    }