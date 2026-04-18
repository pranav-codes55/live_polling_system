from __future__ import annotations

import argparse
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from app.client import VoteClient
from app.protocol import VotePacket


def run_vote(client_host: str, client_port: int, ca_cert: str, poll_id: int, client_id: int, sequence: int, option_id: int) -> float:
    client = VoteClient(server_host=client_host, server_port=client_port, ca_cert=ca_cert)
    packet = VotePacket(poll_id=poll_id, client_id=client_id, sequence=sequence, option_id=option_id, timestamp_ms=int(time.time() * 1000))
    start = time.perf_counter()
    client.send_vote(packet)
    return time.perf_counter() - start


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark the UDP polling server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9999)
    parser.add_argument("--ca-cert", default="certs/cert.pem")
    parser.add_argument("--poll-id", type=int, default=1)
    parser.add_argument("--clients", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--option-id", type=int, default=1)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(run_vote, args.host, args.port, args.ca_cert, args.poll_id, 1000 + index, index + 1, args.option_id)
            for index in range(args.clients)
        ]
        latencies = [future.result() for future in futures]

    elapsed = time.perf_counter() - start
    throughput = args.clients / elapsed if elapsed else 0.0

    print(f"clients={args.clients}")
    print(f"concurrency={args.concurrency}")
    print(f"avg_latency_ms={statistics.mean(latencies) * 1000:.2f}")
    print(f"p95_latency_ms={statistics.quantiles(latencies, n=20)[18] * 1000:.2f}" if len(latencies) >= 20 else f"max_latency_ms={max(latencies) * 1000:.2f}")
    print(f"throughput_votes_per_sec={throughput:.2f}")


if __name__ == "__main__":
    main()