from __future__ import annotations

import contextlib
import socket
import threading
import time
from dataclasses import dataclass, field

from app.engine import PollEngine
from app.protocol import AckPacket, PacketError, STATUS_INVALID, build_ack_packet, build_result_packet, parse_vote_packet


@dataclass
class ClientSession:
    address: tuple[str, int]
    client_id: int | None = None
    last_seen: float = field(default_factory=time.time)
    alive: bool = True

    def close(self) -> None:
        self.alive = False


class UDPPollingServer:
    def __init__(
        self,
        engine: PollEngine,
        host: str,
        port: int,
        broadcast_interval: float = 3.0,
        session_timeout: float = 300.0,
    ) -> None:
        self.engine = engine
        self.host = host
        self.port = port
        self.broadcast_interval = broadcast_interval
        self.session_timeout = session_timeout
        self._stop_event = threading.Event()
        self._listener: socket.socket | None = None
        self._clients: dict[tuple[str, int], ClientSession] = {}
        self._clients_lock = threading.Lock()
        self._broadcast_thread: threading.Thread | None = None

    def serve_forever(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._listener = listener
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.host, self.port))
        listener.settimeout(1.0)

        self._broadcast_thread = threading.Thread(target=self._broadcast_loop, daemon=True)
        self._broadcast_thread.start()

        try:
            while not self._stop_event.is_set():
                try:
                    packet_bytes, address = listener.recvfrom(65535)
                except socket.timeout:
                    continue
                except OSError:
                    break

                session = self._get_or_create_session(address)
                session.last_seen = time.time()
                self._handle_datagram(packet_bytes, address, session)
        finally:
            self.close()

    def close(self) -> None:
        if self._stop_event.is_set():
            return
        self._stop_event.set()

        if self._listener is not None:
            with contextlib.suppress(OSError):
                self._listener.close()

        with self._clients_lock:
            sessions = list(self._clients.values())
            self._clients.clear()

        for session in sessions:
            session.close()

    def broadcast_once(self) -> int:
        self._prune_stale_sessions()
        snapshot = self.engine.snapshot()
        payload = build_result_packet(self.engine.poll_id, snapshot)

        with self._clients_lock:
            sessions = list(self._clients.values())

        sent_count = 0
        for session in sessions:
            if not session.alive:
                continue

            try:
                self._send_datagram(session.address, payload)
            except OSError:
                continue

            sent_count += 1

        return sent_count

    def _broadcast_loop(self) -> None:
        while not self._stop_event.wait(self.broadcast_interval):
            self.broadcast_once()

    def _handle_datagram(self, packet_bytes: bytes, address: tuple[str, int], session: ClientSession) -> None:
        try:
            packet = parse_vote_packet(packet_bytes)
        except PacketError:
            self.engine.register_invalid_packet()
            ack = build_ack_packet(
                AckPacket(
                    poll_id=self.engine.poll_id,
                    client_id=0,
                    sequence=0,
                    status=STATUS_INVALID,
                )
            )
            with contextlib.suppress(OSError):
                self._send_datagram(address, ack)
            return

        session.client_id = packet.client_id
        status = self.engine.register_vote(packet)
        ack = build_ack_packet(
            AckPacket(
                poll_id=packet.poll_id,
                client_id=packet.client_id,
                sequence=packet.sequence,
                status=status,
            )
        )
        with contextlib.suppress(OSError):
            self._send_datagram(address, ack)

    def _get_or_create_session(self, address: tuple[str, int]) -> ClientSession:
        with self._clients_lock:
            session = self._clients.get(address)
            if session is None:
                session = ClientSession(address=address)
                self._clients[address] = session
            return session

    def _send_datagram(self, address: tuple[str, int], payload: bytes) -> None:
        if self._listener is None:
            raise OSError("UDP listener is not running")
        self._listener.sendto(payload, address)

    def _prune_stale_sessions(self) -> None:
        cutoff = time.time() - self.session_timeout
        with self._clients_lock:
            stale_addresses = [address for address, session in self._clients.items() if session.last_seen < cutoff]
            for address in stale_addresses:
                session = self._clients.pop(address, None)
                if session is not None:
                    session.close()