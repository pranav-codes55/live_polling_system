from app.engine import PollEngine
from app.protocol import STATUS_ACCEPTED, STATUS_DUPLICATE, STATUS_INVALID, VotePacket


def test_duplicate_detection() -> None:
    engine = PollEngine(poll_id=1)
    packet = VotePacket(poll_id=1, client_id=10, sequence=1, option_id=2, timestamp_ms=100)

    first = engine.register_vote(packet)
    second = engine.register_vote(packet)

    assert first == STATUS_ACCEPTED
    assert second == STATUS_DUPLICATE
    assert engine.total_votes == 1
    assert engine.duplicate_votes == 1


def test_statistical_loss_analysis() -> None:
    engine = PollEngine(poll_id=1)
    for sequence in (1, 2, 4, 5):
        engine.register_vote(
            VotePacket(poll_id=1, client_id=20, sequence=sequence, option_id=1, timestamp_ms=sequence)
        )

    loss = engine.loss_analysis()
    assert 20 in loss
    assert loss[20] == 0.2


def test_snapshot_contains_required_fields() -> None:
    engine = PollEngine(poll_id=5)
    snap = engine.snapshot()
    assert snap["poll_id"] == 5
    assert "tally" in snap
    assert "loss_analysis" in snap
    assert "loss_analysis_percentage" in snap
    assert "duplicate_percentage" in snap
    assert "overall_loss_percentage" in snap
    assert set(snap["tally"].keys()) == {"A", "B", "C"}


def test_invalid_option_is_rejected() -> None:
    engine = PollEngine(poll_id=1)
    status = engine.register_vote(
        VotePacket(poll_id=1, client_id=30, sequence=10, option_id=99, timestamp_ms=100)
    )
    assert status == STATUS_INVALID
    assert engine.total_votes == 0
    assert engine.invalid_packets == 1


def test_duplicate_and_loss_percentages() -> None:
    engine = PollEngine(poll_id=1)
    packets = [
        VotePacket(poll_id=1, client_id=50, sequence=1, option_id=1, timestamp_ms=100),
        VotePacket(poll_id=1, client_id=50, sequence=2, option_id=1, timestamp_ms=101),
        VotePacket(poll_id=1, client_id=50, sequence=4, option_id=1, timestamp_ms=102),
    ]

    for packet in packets:
        assert engine.register_vote(packet) == STATUS_ACCEPTED

    # Duplicate of sequence=2
    assert engine.register_vote(packets[1]) == STATUS_DUPLICATE

    snap = engine.snapshot()
    assert snap["duplicate_percentage"] == 25.0
    assert snap["loss_analysis"][50] == 0.25
    assert snap["loss_analysis_percentage"][50] == 25.0
    assert snap["loss_gap_triggers"][50] == 1
    assert snap["overall_loss_gap_triggers"] == 1
    assert snap["overall_loss_percentage"] == 25.0
