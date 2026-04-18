from app.engine import PollEngine
from app.protocol import TYPE_RESULT, parse_result_packet
from app.server import ClientSession, UDPPollingServer


class DummySocket:
    def __init__(self) -> None:
        self.sent: list[tuple[bytes, tuple[str, int]]] = []

    def sendto(self, data: bytes, addr: tuple[str, int]) -> None:
        self.sent.append((data, addr))


    def close(self) -> None:
        return None


def test_periodic_result_broadcast_packet_content() -> None:
    engine = PollEngine(poll_id=9)
    server = UDPPollingServer(
        engine=engine,
        host="127.0.0.1",
        port=0,
        broadcast_interval=1.0,
    )
    transport = DummySocket()
    session = ClientSession(address=("127.0.0.1", 20001))

    server._clients = {session.address: session}
    server._listener = transport
    sent_count = server.broadcast_once()

    assert sent_count == 1
    assert len(transport.sent) == 1

    pkt = transport.sent[0][0]
    poll_id, payload = parse_result_packet(pkt)

    assert poll_id == 9
    assert payload["poll_id"] == 9
    assert payload["total_votes"] == 0
    assert TYPE_RESULT == 3
