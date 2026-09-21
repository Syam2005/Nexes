# NEXUS Demo File — Python 2.7 era legacy patterns
import urllib2

print "Starting legacy application..."
name = "World"
message = "Hello, %s!" % name
print message

def fetch_data(url):
    response = urllib2.urlopen(url)
    return response.read()

config = {"debug": True, "version": "2.7"}
if config.has_key("debug"):
    print "Debug mode:", config["debug"]

def process_items(n):
    total = 0
    for i in xrange(n):
        total += i
    return total

def safe_divide(a, b):
    try:
        return a / b
    except ZeroDivisionError, e:
        print "Error:", e
        return None

def format_report(filename, issues, risk):
    header = "=== Report for %s ===" % filename
    body = "Issues found: %d | Risk: %s" % (issues, risk)
    return "%s\n%s" % (header, body)

# Demo: hardcoded credential for security scanner
API_KEY = "sk-hardcoded-demo-key-12345"

def is_string(val):
    return isinstance(val, basestring)

print process_items(100)