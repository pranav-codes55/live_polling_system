from __future__ import annotations

import socket

from app.protocol import FrameError, build_frame, split_frame


class StreamClosedError(ConnectionError):
    """Raised when a framed socket stream closes before a frame is fully read."""


def send_frame(sock: socket.socket, payload: bytes) -> None:
    sock.sendall(build_frame(payload))


def recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size

    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise StreamClosedError("Socket closed while reading frame")
        chunks.append(chunk)
        remaining -= len(chunk)

    return b"".join(chunks)


def recv_frame(sock: socket.socket, buffer: bytearray | None = None) -> bytes:
    local_buffer = buffer if buffer is not None else bytearray()

    while True:
        payload = split_frame(local_buffer)
        if payload is not None:
            return payload

        chunk = sock.recv(4096)
        if not chunk:
            raise StreamClosedError("Socket closed while reading frame")
        local_buffer.extend(chunk)
