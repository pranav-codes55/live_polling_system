from __future__ import annotations

import socket
import threading
import time

from app.client import VoteClient
from app.engine import PollEngine
from app.protocol import VotePacket
from app.server import UDPPollingServer


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_udp_vote_flow_and_broadcast() -> None:
    port = _get_free_port()
    server = UDPPollingServer(
        engine=PollEngine(poll_id=12),
        host="127.0.0.1",
        port=port,
        broadcast_interval=0.1,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        client = VoteClient(server_host="127.0.0.1", server_port=port)
        packet = VotePacket(poll_id=12, client_id=501, sequence=9, option_id=2, timestamp_ms=1710101010101)
        status, snapshots = client.send_vote(packet, listen_seconds=0.4)

        assert status == 1
        assert len(snapshots) >= 1
        assert snapshots[-1]["poll_id"] == 12
        assert snapshots[-1]["tally"]["B"] == 1
    finally:
        server.close()
        thread.join(timeout=2.0)
