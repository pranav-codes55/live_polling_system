from __future__ import annotations

import socket
import time

from app.protocol import (
    AckPacket,
    PacketError,
    STATUS_ACCEPTED,
    STATUS_DUPLICATE,
    VotePacket,
    build_vote_packet,
    parse_ack_packet,
    parse_result_packet,
)


class VoteClient:
    def __init__(
        self,
        server_host: str,
        server_port: int,
        ca_cert: str | None = None,
        timeout: float = 1.0,
        retries: int = 3,
    ) -> None:
        self.server_addr = (socket.gethostbyname(server_host), server_port)
        self.timeout = timeout
        self.retries = retries
        self.ca_cert = ca_cert

    def send_vote(self, packet: VotePacket, listen_seconds: float = 0.0) -> tuple[int, list[dict]]:
        last_error: Exception | None = None

        for _ in range(self.retries):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
                    udp_socket.settimeout(self.timeout)
                    udp_socket.sendto(build_vote_packet(packet), self.server_addr)

                    snapshots: list[dict] = []
                    ack_packet, pre_ack_snapshots = self._recv_ack(udp_socket, packet)
                    snapshots.extend(pre_ack_snapshots)

                    if listen_seconds > 0:
                        snapshots.extend(self.listen_for_results(udp_socket, listen_seconds))
                    return ack_packet.status, snapshots
            except (socket.timeout, OSError, ValueError, PacketError) as exc:
                last_error = exc

        if last_error is not None:
            raise TimeoutError("Vote ACK not received after retries") from last_error
        raise TimeoutError("Vote ACK not received after retries")

    def _recv_ack(self, udp_socket: socket.socket, packet: VotePacket) -> tuple[AckPacket, list[dict]]:
        snapshots: list[dict] = []
        deadline = time.monotonic() + self.timeout

        while time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            udp_socket.settimeout(remaining)
            data, addr = udp_socket.recvfrom(65535)
            if addr != self.server_addr:
                continue

            try:
                ack_packet = parse_ack_packet(data)
            except PacketError:
                try:
                    _, snapshot = parse_result_packet(data)
                except PacketError:
                    continue
                snapshots.append(snapshot)
                continue

            if ack_packet.sequence != packet.sequence or ack_packet.client_id != packet.client_id:
                raise ValueError("ACK does not match sent vote")

            return ack_packet, snapshots

        raise socket.timeout("Vote ACK not received before deadline")

    def listen_for_results(self, udp_socket: socket.socket, listen_seconds: float) -> list[dict]:
        snapshots: list[dict] = []
        deadline = time.monotonic() + listen_seconds

        while time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            udp_socket.settimeout(min(self.timeout, remaining))
            try:
                payload, addr = udp_socket.recvfrom(65535)
            except socket.timeout:
                continue

            if addr != self.server_addr:
                continue

            try:
                _, snapshot = parse_result_packet(payload)
            except PacketError:
                continue

            snapshots.append(snapshot)

        return snapshots


def status_label(status: int) -> str:
    if status == STATUS_ACCEPTED:
        return "accepted"
    if status == STATUS_DUPLICATE:
        return "duplicate"
    return "invalid"
