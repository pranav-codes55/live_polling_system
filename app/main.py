from __future__ import annotations

import argparse
import threading
import time

from app.client import VoteClient, status_label
from app.engine import PollEngine
from app.protocol import VotePacket
from app.server import UDPPollingServer

OPTION_TO_ID = {"A": 1, "B": 2, "C": 3}


def run_server(
    host: str,
    port: int,
    poll_id: int,
    broadcast_interval: float,
    web_host: str,
    web_port: int,
    ws_port: int,
    enable_dashboard: bool,
    users_file: str,
) -> None:
    engine = PollEngine(poll_id=poll_id)
    server = UDPPollingServer(
        engine=engine,
        host=host,
        port=port,
        broadcast_interval=broadcast_interval,
    )
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"Starting UDP polling server on {host}:{port}")

    if not enable_dashboard:
        server_thread.join()
        return

    from app.web import create_dashboard_app

    dashboard = create_dashboard_app(
        engine=engine,
        vote_host="127.0.0.1" if host == "0.0.0.0" else host,
        vote_port=port,
        ca_cert=None,
        users_file=users_file,
        ws_port=ws_port,
    )
    print(f"Starting dashboard on http://{web_host}:{web_port}")
    try:
        dashboard.run(
            host=web_host,
            port=web_port,
            debug=False,
            threaded=True,
            use_reloader=False,
        )
    finally:
        server.close()
        server_thread.join(timeout=2.0)


def demo_vote_client(
    server_host: str,
    server_port: int,
    ca_cert: str,
    poll_id: int,
    option: str,
    client_id: int,
    sequence: int | None,
    listen_seconds: float,
) -> None:
    client = VoteClient(server_host=server_host, server_port=server_port, ca_cert=ca_cert)
    normalized_option = option.upper().strip()
    if normalized_option not in OPTION_TO_ID:
        raise ValueError("Option must be one of A, B, C")

    timestamp_ms = int(time.time() * 1000)
    packet = VotePacket(
        poll_id=poll_id,
        client_id=client_id,
        sequence=sequence if sequence is not None else timestamp_ms % 100000,
        option_id=OPTION_TO_ID[normalized_option],
        timestamp_ms=timestamp_ms,
    )
    status, snapshots = client.send_vote(packet, listen_seconds=listen_seconds)
    print(f"Client {packet.client_id} voted {normalized_option} (seq={packet.sequence}) -> {status_label(status)}")

    for snapshot in snapshots:
        tally = snapshot["tally"]
        print(f"Broadcast poll {snapshot['poll_id']}: {tally}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UDP polling and voting system")
    parser.add_argument("mode", choices=["server", "client-demo"], help="Run server or send one demo vote")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9999)
    parser.add_argument("--web-host", default="0.0.0.0")
    parser.add_argument("--web-port", type=int, default=8443)
    parser.add_argument("--ws-port", type=int, default=9001)
    parser.add_argument("--no-dashboard", action="store_true", help="Run only UDP socket server without Flask UI")
    parser.add_argument("--poll-id", type=int, default=1)
    parser.add_argument("--broadcast-interval", type=float, default=3.0)
    parser.add_argument("--users-file", default="users.json")
    parser.add_argument("--ca-cert", default=None)
    parser.add_argument("--option", choices=["A", "B", "C"], default="A")
    parser.add_argument("--client-id", type=int, default=1001)
    parser.add_argument("--sequence", type=int, default=None)
    parser.add_argument("--listen-seconds", type=float, default=4.0)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "client-demo":
        demo_vote_client(
            server_host=args.host,
            server_port=args.port,
            ca_cert=args.ca_cert,
            poll_id=args.poll_id,
            option=args.option,
            client_id=args.client_id,
            sequence=args.sequence,
            listen_seconds=args.listen_seconds,
        )
        return

    run_server(
        host=args.host,
        port=args.port,
        poll_id=args.poll_id,
        broadcast_interval=args.broadcast_interval,
        web_host=args.web_host,
        web_port=args.web_port,
        ws_port=args.ws_port,
        enable_dashboard=not args.no_dashboard,
        users_file=args.users_file,
    )


if __name__ == "__main__":
    main()
