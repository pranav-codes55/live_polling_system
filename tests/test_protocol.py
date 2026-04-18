import pytest

from app.protocol import PacketError, VotePacket, build_frame, parse_vote_packet, split_frame, build_vote_packet


def test_custom_vote_packet_roundtrip() -> None:
    packet = VotePacket(
        poll_id=7,
        client_id=101,
        sequence=33,
        option_id=2,
        timestamp_ms=1710101010101,
    )
    encoded = build_vote_packet(packet)
    decoded = parse_vote_packet(encoded)
    assert decoded == packet


def test_vote_packet_crc_detects_corruption() -> None:
    packet = VotePacket(
        poll_id=1,
        client_id=2,
        sequence=3,
        option_id=4,
        timestamp_ms=5,
    )
    encoded = bytearray(build_vote_packet(packet))
    encoded[-1] ^= 0xFF

    with pytest.raises(PacketError):
        parse_vote_packet(bytes(encoded))


def test_frame_roundtrip() -> None:
    payload = b"hello over tls"
    framed = build_frame(payload)
    buffer = bytearray(framed)

    assert split_frame(buffer) == payload
    assert buffer == bytearray()
