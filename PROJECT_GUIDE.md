# Live Polling System - Project Guide

This guide explains how to set up, run, and test the UDP-based polling project.

## 1) Prerequisites

- macOS, Linux, or Windows
- Python 3.10+ (recommended: 3.11+)
- Terminal access

## 2) Setup

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3) Run the Server

Start the UDP vote server:

```bash
python -m app.main server --host 0.0.0.0 --port 9999 --web-host 0.0.0.0 --web-port 8443
```

Open dashboard:

- `http://127.0.0.1:8443`

Predefined login credentials for dashboard users are stored in `users.json`.

## 4) Send Votes

### Option A: Demo UDP client from terminal

Open a second terminal:

```bash
source .venv/bin/activate
python -m app.main client-demo --host 127.0.0.1 --port 9999 --option A --client-id 1001 --listen-seconds 4
```

## 5) Run Tests

```bash
source .venv/bin/activate
pytest -q
```

## 6) What Reliability Is Implemented

- UDP vote datagrams with custom format + CRC check
- ACK response from server to client
- Client retries if ACK not received
- Sequence number based duplicate detection
- Packet loss estimation by sequence gaps, which is a sequence-based estimate rather than raw network capture loss
- Periodic result broadcast to connected UDP clients
- Performance evaluation is supported by `scripts/benchmark_udp.py`.

## 7) Rubric Checklist

- Direct socket usage: Implemented with low-level UDP sockets.
- Multiple concurrent clients: Implemented with a datagram receive loop and periodic broadcasts.
- Network-based communication only: Implemented using socket communication only.
- Performance metrics: Supported by benchmark script.

Dashboard is an HTTP visualization layer; all vote/control/data messages still flow through the UDP socket endpoints.

## 8) Useful Commands

Run server on default ports:

```bash
python -m app.main server
```

Send quick vote (default values):

```bash
python -m app.main client-demo
```

Run a benchmark:

```bash
python scripts/benchmark_udp.py --host 127.0.0.1 --port 9999 --clients 50 --concurrency 10
```

## 9) Troubleshooting

### Error: No module named pytest

Install dependencies in virtual environment:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### Port already in use

Change ports:

```bash
python -m app.main server --host 127.0.0.1 --port 10000
```

## 10) Final Submission Writeup

Include these points in your final report:

- Problem statement and why the socket-based UDP design was chosen.
- Architecture summary with the client, server, protocol, and dashboard flow.
- Core features implemented: custom packets, ACK handling, duplicate detection, broadcasts, and UDP transport.
- Performance notes from the benchmark script, especially latency and throughput under multiple clients.
- A short clarification that the loss metric is a sequence-gap estimate and that the dashboard is an HTTP visualization layer.

Suggested benchmark summary format:

- Test setup: number of clients, concurrency, host, and port.
- Observations: average latency, throughput, and whether results stayed stable under load.
- Conclusion: whether the system handled concurrent voting as expected.

## Credits

R P Pranav, Deeksha, Nikitha V
