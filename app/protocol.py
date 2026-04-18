import json
import struct
import zlib
from dataclasses import dataclass
from typing import Any

MAGIC = b"VOTE"
VERSION = 1

TYPE_VOTE = 1
TYPE_ACK = 2
TYPE_RESULT = 3

STATUS_ACCEPTED = 1
STATUS_DUPLICATE = 2
STATUS_INVALID = 3

_VOTE_NO_CRC = struct.Struct("!4sBBHIIHQ")
_ACK_NO_CRC = struct.Struct("!4sBBHIIb")
_RESULT_HEADER = struct.Struct("!4sBBHH")
_CRC = struct.Struct("!I")
_FRAME_LENGTH = struct.Struct("!I")


class PacketError(ValueError):
    """Raised when packet format or integrity checks fail."""


class FrameError(ValueError):
    """Raised when a framed transport payload is malformed."""


@dataclass(frozen=True)
class VotePacket:
    poll_id: int
    client_id: int
    sequence: int
    option_id: int
    timestamp_ms: int


@dataclass(frozen=True)
class AckPacket:
    poll_id: int
    client_id: int
    sequence: int
    status: int


def _crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def build_vote_packet(packet: VotePacket) -> bytes:
    base = _VOTE_NO_CRC.pack(
        MAGIC,
        VERSION,
        TYPE_VOTE,
        packet.poll_id,
        packet.client_id,
        packet.sequence,
        packet.option_id,
        packet.timestamp_ms,
    )
    return base + _CRC.pack(_crc32(base))


def parse_vote_packet(data: bytes) -> VotePacket:
    expected_size = _VOTE_NO_CRC.size + _CRC.size
    if len(data) != expected_size:
        raise PacketError(f"Vote packet size mismatch: {len(data)} != {expected_size}")

    base = data[:-_CRC.size]
    crc, = _CRC.unpack(data[-_CRC.size:])
    if _crc32(base) != crc:
        raise PacketError("Vote packet CRC mismatch")

    magic, version, pkt_type, poll_id, client_id, sequence, option_id, ts_ms = _VOTE_NO_CRC.unpack(base)
    if magic != MAGIC or version != VERSION or pkt_type != TYPE_VOTE:
        raise PacketError("Vote packet header mismatch")

    return VotePacket(
        poll_id=poll_id,
        client_id=client_id,
        sequence=sequence,
        option_id=option_id,
        timestamp_ms=ts_ms,
    )


def build_ack_packet(packet: AckPacket) -> bytes:
    base = _ACK_NO_CRC.pack(
        MAGIC,
        VERSION,
        TYPE_ACK,
        packet.poll_id,
        packet.client_id,
        packet.sequence,
        packet.status,
    )
    return base + _CRC.pack(_crc32(base))


def parse_ack_packet(data: bytes) -> AckPacket:
    expected_size = _ACK_NO_CRC.size + _CRC.size
    if len(data) != expected_size:
        raise PacketError(f"ACK packet size mismatch: {len(data)} != {expected_size}")

    base = data[:-_CRC.size]
    crc, = _CRC.unpack(data[-_CRC.size:])
    if _crc32(base) != crc:
        raise PacketError("ACK packet CRC mismatch")

    magic, version, pkt_type, poll_id, client_id, sequence, status = _ACK_NO_CRC.unpack(base)
    if magic != MAGIC or version != VERSION or pkt_type != TYPE_ACK:
        raise PacketError("ACK packet header mismatch")

    return AckPacket(
        poll_id=poll_id,
        client_id=client_id,
        sequence=sequence,
        status=status,
    )


def build_frame(payload: bytes) -> bytes:
    if len(payload) > 0xFFFFFFFF:
        raise FrameError("Payload too large to frame")
    return _FRAME_LENGTH.pack(len(payload)) + payload


def split_frame(buffer: bytearray) -> bytes | None:
    if len(buffer) < _FRAME_LENGTH.size:
        return None

    (payload_length,) = _FRAME_LENGTH.unpack(buffer[:_FRAME_LENGTH.size])
    if payload_length < 0:
        raise FrameError("Negative frame length")

    frame_size = _FRAME_LENGTH.size + payload_length
    if len(buffer) < frame_size:
        return None

    payload = bytes(buffer[_FRAME_LENGTH.size:frame_size])
    del buffer[:frame_size]
    return payload


def build_result_packet(poll_id: int, payload: dict[str, Any]) -> bytes:
    raw_payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    base = _RESULT_HEADER.pack(MAGIC, VERSION, TYPE_RESULT, poll_id, len(raw_payload)) + raw_payload
    return base + _CRC.pack(_crc32(base))


def parse_result_packet(data: bytes) -> tuple[int, dict[str, Any]]:
    min_size = _RESULT_HEADER.size + _CRC.size
    if len(data) < min_size:
        raise PacketError("Result packet too short")

    header = data[:_RESULT_HEADER.size]
    magic, version, pkt_type, poll_id, payload_len = _RESULT_HEADER.unpack(header)
    if magic != MAGIC or version != VERSION or pkt_type != TYPE_RESULT:
        raise PacketError("Result packet header mismatch")

    body_end = _RESULT_HEADER.size + payload_len
    if body_end + _CRC.size != len(data):
        raise PacketError("Result packet payload length mismatch")

    base = data[:-_CRC.size]
    crc, = _CRC.unpack(data[-_CRC.size:])
    if _crc32(base) != crc:
        raise PacketError("Result packet CRC mismatch")

    payload = json.loads(data[_RESULT_HEADER.size:body_end].decode("utf-8"))
    return poll_id, payload
