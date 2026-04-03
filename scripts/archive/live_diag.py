"""
Comprehensive registration diagnostic - calls Vercel endpoint and prints full error.
"""
import urllib.request
import json
import ssl
import sys

ctx = ssl._create_unverified_context()
BASE_URL = "https://agentic-multiagentsupportsystem.vercel.app"

def call_endpoint(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, method='POST',
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
            body = resp.read().decode()
            return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return e.code, body
    except Exception as ex:
        return 0, str(ex)

print("=== Step 1: Health Check ===")
try:
    req = urllib.request.Request(f"{BASE_URL}/api/health", headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        print("Health:", resp.read().decode()[:300])
except Exception as e:
    print("Health FAILED:", e)

print("\n=== Step 2: Registration Test ===")
status, body = call_endpoint(f"{BASE_URL}/api/auth/register", {
    'role': 'student',
    'email': 'live.diag.test@gmail.com',
    'password': 'TestPass@1234',
    'confirm_password': 'TestPass@1234',
    'full_name': 'Live Diag',
    'roll_number': '22B91A0590',
    'department': 'CSE',
    'year': 2,
    'section': 'A'
})
print(f"HTTP Status: {status}")
try:
    d = json.loads(body)
    print(f"success: {d.get('success')}")
    print(f"error: {d.get('error', 'N/A')}")
    print(f"message: {d.get('message', 'N/A')}")
    debug = d.get('debug', '')
    if debug:
        print("--- FULL TRACEBACK ---")
        print(debug)
except Exception:
    print("Raw body:", body[:1000])
