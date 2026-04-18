from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, Set, Tuple

from app.protocol import STATUS_ACCEPTED, STATUS_DUPLICATE, STATUS_INVALID, VotePacket


@dataclass
class ClientStats:
    seen_sequences: Set[int] = field(default_factory=set)

    def register(self, sequence: int) -> None:
        self.seen_sequences.add(sequence)

    @property
    def expected_packets(self) -> int:
        if not self.seen_sequences:
            return 0
        low = min(self.seen_sequences)
        high = max(self.seen_sequences)
        return high - low + 1

    @property
    def missing_packets(self) -> int:
        expected = self.expected_packets
        if expected == 0:
            return 0
        return expected - len(self.seen_sequences)

    @property
    def loss_rate(self) -> float:
        if len(self.seen_sequences) < 2:
            return 0.0
        expected = self.expected_packets
        if expected == 0:
            return 0.0
        return self.missing_packets / expected

    @property
    def loss_percentage(self) -> float:
        return self.loss_rate * 100.0

    @property
    def gap_triggers(self) -> int:
        if len(self.seen_sequences) < 2:
            return 0
        sorted_sequences = sorted(self.seen_sequences)
        triggers = 0
        for idx in range(1, len(sorted_sequences)):
            if sorted_sequences[idx] - sorted_sequences[idx - 1] > 1:
                triggers += 1
        return triggers


class PollEngine:
    def __init__(self, poll_id: int, options: list[int] | None = None) -> None:
        self._lock = Lock()
        self.poll_id = poll_id
        self.options = options or [1, 2, 3]
        if self.options == [1, 2, 3]:
            self.option_labels = {1: "A", 2: "B", 3: "C"}
        else:
            self.option_labels = {option: str(option) for option in self.options}
        self._tally: Dict[int, int] = {option: 0 for option in self.options}
        self._seen_vote_keys: Set[Tuple[int, int, int]] = set()
        self._client_stats: Dict[int, ClientStats] = {}
        self.total_votes = 0
        self.duplicate_votes = 0
        self.invalid_packets = 0

    def register_invalid_packet(self) -> None:
        with self._lock:
            self.invalid_packets += 1

    def register_vote(self, packet: VotePacket) -> int:
        with self._lock:
            vote_key = (packet.poll_id, packet.client_id, packet.sequence)
            client_stats = self._client_stats.setdefault(packet.client_id, ClientStats())
            client_stats.register(packet.sequence)

            if vote_key in self._seen_vote_keys:
                self.duplicate_votes += 1
                return STATUS_DUPLICATE

            self._seen_vote_keys.add(vote_key)
            if packet.option_id not in self._tally:
                self.invalid_packets += 1
                return STATUS_INVALID

            self.total_votes += 1
            self._tally[packet.option_id] += 1
            return STATUS_ACCEPTED

    def loss_analysis(self) -> dict[int, float]:
        with self._lock:
            return {client_id: round(stats.loss_rate, 4) for client_id, stats in self._client_stats.items()}

    def loss_analysis_percentage(self) -> dict[int, float]:
        with self._lock:
            return {client_id: round(stats.loss_percentage, 2) for client_id, stats in self._client_stats.items()}

    def duplicate_percentage(self) -> float:
        with self._lock:
            received_packets = self.total_votes + self.duplicate_votes
            if received_packets == 0:
                return 0.0
            return round((self.duplicate_votes / received_packets) * 100.0, 2)

    def overall_loss_percentage(self) -> float:
        with self._lock:
            total_expected = sum(stats.expected_packets for stats in self._client_stats.values())
            if total_expected == 0:
                return 0.0
            total_missing = sum(stats.missing_packets for stats in self._client_stats.values())
            return round((total_missing / total_expected) * 100.0, 2)

    def snapshot(self) -> dict:
        with self._lock:
            received_packets = self.total_votes + self.duplicate_votes
            duplicate_percentage = 0.0
            if received_packets > 0:
                duplicate_percentage = round((self.duplicate_votes / received_packets) * 100.0, 2)

            total_expected = sum(stats.expected_packets for stats in self._client_stats.values())
            total_missing = sum(stats.missing_packets for stats in self._client_stats.values())
            total_gap_triggers = sum(stats.gap_triggers for stats in self._client_stats.values())
            overall_loss_percentage = 0.0
            if total_expected > 0:
                overall_loss_percentage = round((total_missing / total_expected) * 100.0, 2)

            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "poll_id": self.poll_id,
                "total_votes": self.total_votes,
                "duplicate_votes": self.duplicate_votes,
                "duplicate_percentage": duplicate_percentage,
                "invalid_packets": self.invalid_packets,
                "tally": {
                    self.option_labels[option]: self._tally[option]
                    for option in sorted(self._tally)
                },
                "loss_analysis": {
                    client_id: round(stats.loss_rate, 4) for client_id, stats in self._client_stats.items()
                },
                "loss_analysis_percentage": {
                    client_id: round(stats.loss_percentage, 2) for client_id, stats in self._client_stats.items()
                },
                "loss_gap_triggers": {
                    client_id: stats.gap_triggers for client_id, stats in self._client_stats.items()
                },
                "overall_loss_gap_triggers": total_gap_triggers,
                "overall_loss_percentage": overall_loss_percentage,
            }
