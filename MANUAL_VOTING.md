# Quick Manual Voting Guide

## System is Running!

**Dashboard:** http://localhost:8443
- UDP Server: port 9999
- WebSocket Proxy: port 9001
- Flask Dashboard: port 8443

## How to Vote Manually (Command Line)

### Step 1: Login and Get Token

```bash
TOKEN=$(curl -sS -X POST http://localhost:8443/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"pranav","password":"pranav123"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['token'])")

echo "Your token: $TOKEN"
```

**Available users:**
- Username: `pranav`, Password: `pranav123`
- Username: `diya`, Password: `diya123`
- Username: `nikitha`, Password: `nikitha123`  
- Username: `deeksha`, Password: `deeksha123`

### Step 2: Cast a Vote

```bash
curl -X POST http://localhost:8443/api/vote \
  -H 'Content-Type: application/json' \
  -d "{\"token\":\"$TOKEN\",\"option\":\"A\"}"
```

Change `option` to `"A"`, `"B"`, or `"C"`.

**Response examples:**
- First vote: `"status": "accepted"`
- Duplicate vote: `"status": "duplicate"`

### Step 3: Check Results

```bash
curl -s http://localhost:8443/api/results | python3 -m json.tool
```

This shows the live tally of all votes.

## One-Line Voting Command

Vote as user and see results:

```bash
TOKEN=$(curl -sS -X POST http://localhost:8443/api/login -H 'Content-Type: application/json' -d '{"username":"pranav","password":"pranav123"}' | sed 's/.*"token":"\([^"]*\)".*/\1/'); echo "Token: $TOKEN"; curl -X POST http://localhost:8443/api/vote -H 'Content-Type: application/json' -d "{\"token\":\"$TOKEN\",\"option\":\"B\"}"; sleep 1; echo ""; curl -s http://localhost:8443/api/results | python3 -m json.tool
```

## Testing Multiple Votes

Vote as different users:

```bash
# Vote A as pranav
TOKEN_A=$(curl -sS -X POST http://localhost:8443/api/login -H 'Content-Type: application/json' -d '{"username":"pranav","password":"pranav123"}' | sed 's/.*"token":"\([^"]*\)".*/\1/')
curl -X POST http://localhost:8443/api/vote -H 'Content-Type: application/json' -d "{\"token\":\"$TOKEN_A\",\"option\":\"A\"}"

# Vote B as diya
TOKEN_B=$(curl -sS -X POST http://localhost:8443/api/login -H 'Content-Type: application/json' -d '{"username":"diya","password":"diya123"}' | sed 's/.*"token":"\([^"]*\)".*/\1/')
curl -X POST http://localhost:8443/api/vote -H 'Content-Type: application/json' -d "{\"token\":\"$TOKEN_B\",\"option\":\"B\"}"

# Vote C as nikitha
TOKEN_C=$(curl -sS -X POST http://localhost:8443/api/login -H 'Content-Type: application/json' -d '{"username":"nikitha","password":"nikitha123"}' | sed 's/.*"token":"\([^"]*\)".*/\1/')
curl -X POST http://localhost:8443/api/vote -H 'Content-Type: application/json' -d "{\"token\":\"$TOKEN_C\",\"option\":\"C\"}"

# Check final results
curl -s http://localhost:8443/api/results | python3 -m json.tool
```

##  How the System Works

### Browser Dashboard (Recommended)
1. Open http://localhost:8443
2. Click Login with your credentials
3. Click a Vote button (A, B, or C)
4. Results update in real-time
5. WebSocket handles all communication

### Command Line (Alternative)
1. Login with curl to get a token
2. Send vote with POST request  
3. Monitor results with frequent GET requests

### How It Works Internally

```
You (Browser)
    ↓ WebSocket
Node.js Proxy (port 9001)
    ↓ UDP
Python Server (port 9999)
    ↓ Tallies votes
    ↓ Broadcasts results UDP
Node.js Proxy
    ↓ HTTP polling
Browser Dashboard
    ↓ Displays live results
```

## Troubleshooting

**Q: Votes not showing up?**
- Make sure you logged in first
- Check you're using a real username from the list
- Only 1 vote per user is allowed (duplicate attempts return `duplicate` status)

**Q: Getting "Address already in use" error?**
```bash
# Kill old processes
pkill -f "app.main server"
pkill -f "websocket-proxy"
lsof -i :9999,8443,9001 # See what's using the ports
```

**Q: WebSocket not connecting in browser?**
- Open Developer Tools (F12)
- Go to Console tab
- Look for connection status
- It falls back to HTTP automatically if needed

**Q: Need to change ports?**
```bash
HOST=127.0.0.1 PORT=9000 WEB_PORT=9999 WS_PORT=9002 ./scripts/run_full_system.sh
```

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Dashboard UI |
| `/api/login` | POST | Get authentication token |
| `/api/vote` | POST | Submit a vote |
| `/api/results` | GET | Get current tally |
| `/api/config` | GET | Get WebSocket port |

All API endpoints return JSON.

## Did it work?

✅ System running: You can curl the endpoints above and get responses
✅ Voting works: Tally changes when you submit votes
✅ WebSocket: Browser dashboard shows "WebSocket connected: true"
✅ Fallback: HTTP API still works if WebSocket is down

Enjoy! 🗳️
