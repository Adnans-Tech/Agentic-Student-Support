import urllib.request
import json
import ssl

ctx = ssl._create_unverified_context()
url = 'https://agentic-multiagentsupportsystem.vercel.app/api/auth/register'
payload = {
    'role': 'student',
    'email': 'diag_final@gmail.com',
    'password': 'TestPass@1234',
    'confirm_password': 'TestPass@1234',
    'full_name': 'Test',
    'roll_number': '22B91A0595',
    'department': 'CSE',
    'year': 2,
    'section': 'A'
}

req = urllib.request.Request(
    url, 
    data=json.dumps(payload).encode('utf-8'), 
    method='POST', 
    headers={'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req, context=ctx, timeout=60) as resp:
        print('SUCCESS:', resp.read().decode())
except urllib.error.HTTPError as e:
    resp_body = e.read().decode()
    with open('data/vercel_err.json', 'w') as f:
        f.write(resp_body)
    print('Wrote error to data/vercel_err.json')
    try:
        body = json.loads(resp_body)
        print('ERROR:', body.get('error', 'N/A'))
        print('DEBUG:', body.get('debug', 'N/A'))
    except:
        print('RAW:', resp_body[:500])
