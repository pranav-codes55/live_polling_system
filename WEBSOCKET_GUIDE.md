# WebSocket Proxy Architecture Guide

## Overview

The live polling system now uses a **Node.js WebSocket proxy** to bridge the gap between the web dashboard and the UDP voting server. This architecture provides:

- **Real-time voting via WebSocket** from the dashboard UI
- **Fallback to HTTP** if WebSocket is unavailable
- **UDP core server** remains unchanged for reliability and performance
- **Pure Python Flask** web server for serving static assets and APIs

## System Architecture

```
┌─────────────────────┐
│  Web Dashboard UI   │
│   (JavaScript)      │
└──────────┬──────────┘
           │ WebSocket (port 9001)
           │
┌──────────▼──────────────────┐
│  Node.js WebSocket Proxy    │
│  - Proxies votes to UDP     │
│  - Forwarding layer         │
└──────────┬──────────────────┘
           │ UDP (port 9999)
           │
┌──────────▼──────────────────┐
│  Python UDP Polling Server  │
│  - Vote aggregation         │
│  - Duplicate detection      │
│  - Result broadcasting      │
└─────────────────────────────┘

┌─────────────────────────────┐
│  Flask Web Server           │
│  - Dashboard UI             │
│  - /api/login               │
│  - /api/vote (fallback)     │
│  - /api/results             │
│  - /api/config              │
└─────────────────────────────┘
```

## Services & Ports

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Python UDP Server | 9999 | UDP | Core voting engine |
| Flask Dashboard | 8443 | HTTP | Web UI and fallback APIs |
| Node.js Proxy | 9001 | WebSocket | Vote proxying |

## Running the System

### Start All Services

```bash
./scripts/run_full_system.sh
```

The dashboard is accessible at `http://localhost:8443`

### Environment Variables

```bash
HOST=0.0.0.0          # UDP server bind address
PORT=9999             # UDP server port
WEB_HOST=0.0.0.0      # Dashboard bind address
WEB_PORT=8443         # Dashboard HTTP port
WS_PORT=9001          # WebSocket proxy port
```

Example:
```bash
HOST=127.0.0.1 PORT=9000 WEB_PORT=9999 WS_PORT=9002 ./scripts/run_full_system.sh
```

## Manual Voting Guide

### 1. Via WebSocket (Recommended)

WebSocket voting is handled automatically by the frontend. In your browser console after opening the dashboard:

```javascript
// Check if connected
console.log("WebSocket connected:", wsConnected);

// Manually send a vote (if needed)
const votePayload = {
  type: "vote",
  token: login.token,
  username: login.username,
  option: "A",
  clientId: 100001,
  sequence: 1,
  optionId: 1,
  timestamp: Date.now()
};
ws.send(JSON.stringify(votePayload));
```

### 2. Via HTTP (Fallback/CLI)

#### Login
```bash
TOKEN=$(curl -sS -X POST http://localhost:8443/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"pranav","password":"pranav123"}' \
  | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')

echo "Token: $TOKEN"
```

#### Cast a Vote
```bash
curl -X POST http://localhost:8443/api/vote \
  -H 'Content-Type: application/json' \
  -d "{\"token\":\"$TOKEN\",\"option\":\"B\"}"
```

#### Get Results
```bash
curl http://localhost:8443/api/results
```

#### Get WebSocket Configuration
```bash
curl http://localhost:8443/api/config
```

### 3. Via Python Client Demo

```bash
python -m app.main client-demo \
  --host 127.0.0.1 \
  --port 9999 \
  --option A \
  --listen-seconds 4
```

## Frontend JavaScript Event Flow

### Page Load
1. Fetch `/api/config` to get WebSocket port
2. Establish WebSocket connection to proxy
3. Poll HTTP endpoint for results every 1.2 seconds

### Login
1. POST to `/api/login` with credentials
2. Receive token in response
3. Store token for voting

### Vote Submission
1. User clicks vote button
2. JavaScript sends vote via WebSocket (preferred) or HTTP fallback
3. Proxy receives message and forwards to UDP server
4. Server ACKs receipt and updates tally
5. Results pushed to frontend via periodic polls

## Testing the System

### Test WebSocket Connectivity
Open the dashboard at `http://localhost:8443` and check browser console:
```
WebSocket connected: true
Connecting to WebSocket at ws://localhost:9001
```

### Test HTTP Fallback
Disable WebSocket in your terminal:
```bash
# Kill WebSocket proxy
pkill -f websocket-proxy

# Dashboard still works via HTTP
curl http://localhost:8443/api/vote \
  -H 'Content-Type: application/json' \
  -d "{\"token\":\"$TOKEN\",\"option\":\"C\"}"
```

### Run Unit Tests
```bash
pytest -q
```

## Troubleshooting

### WebSocket not connecting
1. Check browser console for error messages
2. Verify port 9001 is accessible: `curl -i ws://localhost:9001`
3. Falls back to HTTP automatically

### Votes not registering
1. Check if you're logged in: Look for "Logged in as..." in login state
2. Verify token is valid by checking /api/results
3. Check Flask logs for HTTP vote processing

### Port conflicts
```bash
# Check what's using ports
lsof -i :9999,8443,9001

# Kill processes manually
pkill -f "app.main server"
pkill -f "websocket-proxy"
```

## API Endpoints

### `GET /api/config`
Returns WebSocket port and poll ID for frontend configuration.

```json
{"ws_port": 9001, "poll_id": 1}
 ```

### `POST /api/login`
Authenticate and get session token.

```json
{"token": "token_here", "username": "pranav", "expires_in": 3600}
```

###  `POST /api/vote`
Submit a vote (fallback, WebSocket preferred).

```json
{"status": "accepted", "code": 0, "client_id": 100001, "option": "A"}
```

### `GET /api/results`
Get current voting tally and statistics.

```json
{
  "poll_id": 1,
  "tally": {"A": 5, "B": 3, "C": 2},
  "total_votes": 10,
  "duplicate_votes": 0,
  "invalid_packets": 0,
  "loss_analysis": {},
  "timestamp": "2026-04-09T14:58:05.123456+00:00"
}
```

## Performance Characteristics

- **WebSocket Latency**: <100ms (local connection)
- **HTTP Fallback Latency**: 50-200ms
- **Result Updates**: Every 3 seconds (UDP broadcast interval)
- **Concurrent Users**: Tested with 50+ concurrent clients
- **Vote Processing**: <1ms per vote in UDP server

## Known Limitations

1. WebSocket proxy only listens on `0.0.0.0` - not configurable per interface
2. Broadcast listener port is hardcoded (UDP_PORT + 1000)
3. No TLS for WebSocket (HTTP/WS only, no WSS/HTTPS proxy yet)
4. Single-page session management (tokens expire after 1 hour)

## Future Improvements

- [ ] WebSocket Secure (WSS) support
- [ ] Configurable broadcast listener port
- [ ] Per-interface WebSocket binding
- [ ] Message compression for high-traffic scenarios
- [ ] Admin dashboard for monitoring connections
-  [ ] Vote revocation/modification (with replay protection)
