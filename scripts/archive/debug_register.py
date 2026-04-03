"""
Registration Debug Script
Calls the /api/auth/register endpoint directly to expose real error.
Run this while the Flask app is running locally, OR call your Vercel URL.
"""
import requests
import json

# Change this to your Vercel URL to test production
BASE_URL = "https://agentic-multiagentsupportsystem.vercel.app"

def test_register():
    payload = {
        "role": "student",
        "email": "debug.test123@gmail.com",
        "password": "TestPass@123",
        "confirm_password": "TestPass@123",
        "full_name": "Debug Test",
        "roll_number": "22B91A0999",
        "department": "CSE",
        "year": 2,
        "section": "A"
    }

    print(f"Sending POST to {BASE_URL}/api/auth/register")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        resp = requests.post(
            f"{BASE_URL}/api/auth/register",
            json=payload,
            timeout=30
        )
        print(f"\nStatus Code: {resp.status_code}")
        print(f"Response Headers: {dict(resp.headers)}")
        try:
            print(f"Response Body: {json.dumps(resp.json(), indent=2)}")
        except Exception:
            print(f"Raw Response: {resp.text[:2000]}")
    except requests.exceptions.ConnectionError as e:
        print(f"Connection Error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    test_register()
