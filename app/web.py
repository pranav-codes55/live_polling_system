from __future__ import annotations

import hmac
import json
import time
import secrets
from pathlib import Path
from threading import Lock

from flask import Flask, jsonify, render_template, request

from app.client import VoteClient, status_label
from app.engine import PollEngine
from app.protocol import STATUS_ACCEPTED, STATUS_DUPLICATE, VotePacket


PREDEFINED_USERS = {
    "diya": "diya123",
    "nikitha": "nikitha123",
    "deeksha": "deeksha123",
    "pranav": "pranav123",
}

SESSION_TTL_SECONDS = 3600


def _load_predefined_users(users_file: str | None) -> dict[str, str]:
    if not users_file:
        return PREDEFINED_USERS

    path = Path(users_file)
    if not path.exists():
        return PREDEFINED_USERS

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return PREDEFINED_USERS

    if not isinstance(payload, dict):
        return PREDEFINED_USERS

    users: dict[str, str] = {}
    for raw_username, raw_password in payload.items():
        username = str(raw_username).strip().lower()
        password = str(raw_password).strip()
        if username and password:
            users[username] = password

    return users or PREDEFINED_USERS


def _client_id_from_username(username: str) -> int:
    value = 0
    for char in username:
        value = (value * 131 + ord(char)) % 900000
    return 100000 + value


def create_dashboard_app(
    engine: PollEngine,
    vote_host: str,
    vote_port: int,
    ca_cert: str | None = None,
    users_file: str | None = None,
    ws_port: int = 9001,
) -> Flask:
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    sessions: dict[str, tuple[str, float]] = {}
    predefined_users = _load_predefined_users(users_file)
    voted_users: dict[str, tuple[int, int]] = {}
    voted_users_lock = Lock()

    def _create_session(username: str) -> str:
        token = secrets.token_urlsafe(24)
        sessions[token] = (username, time.time() + SESSION_TTL_SECONDS)
        return token

    def _username_from_token(token: str) -> str | None:
        entry = sessions.get(token)
        if entry is None:
            return None
        username, expires_at = entry
        if time.time() > expires_at:
            sessions.pop(token, None)
            return None
        return username

    @app.get("/")
    def home() -> str:
        return render_template("index.html", poll_id=engine.poll_id)

    @app.get("/api/results")
    def results() -> tuple[str, int] | tuple[dict, int]:
        return jsonify(engine.snapshot()), 200

    @app.get("/api/config")
    def config() -> tuple[dict, int]:
        return jsonify({"ws_port": ws_port, "poll_id": engine.poll_id}), 200

    @app.post("/api/login")
    def login() -> tuple[dict, int]:
        payload = request.get_json(silent=True) or {}
        username = str(payload.get("username", "")).strip().lower()
        password = str(payload.get("password", "")).strip()

        expected = predefined_users.get(username)
        if expected is None or not hmac.compare_digest(expected, password):
            return {"error": "invalid username or password"}, 401

        token = _create_session(username)
        return {"token": token, "username": username, "expires_in": SESSION_TTL_SECONDS}, 200

    @app.post("/api/vote")
    def vote() -> tuple[dict, int]:
        payload = request.get_json(silent=True) or {}
        token = str(payload.get("token", "")).strip()
        username = _username_from_token(token)
        option = str(payload.get("option", "")).upper().strip()

        if not username:
            return {"error": "unauthorized: login required"}, 401
        if option not in {"A", "B", "C"}:
            return {"error": "option must be A, B, or C"}, 400

        client_id = payload.get("client_id")
        sequence: int | None = None
        with voted_users_lock:
            previous_vote = voted_users.get(username)

        if previous_vote is not None:
            # Forward a true duplicate packet so server-side duplicate metrics increment.
            client_id, sequence = previous_vote
        else:
            if client_id is None:
                client_id = _client_id_from_username(username)
            else:
                try:
                    client_id = int(client_id)
                except (TypeError, ValueError):
                    return {"error": "client_id must be an integer"}, 400

        option_map = {"A": 1, "B": 2, "C": 3}
        timestamp_ms = int(time.time() * 1000)
        if sequence is None:
            sequence = timestamp_ms % 100000
        packet = VotePacket(
            poll_id=engine.poll_id,
            client_id=client_id,
            sequence=sequence,
            option_id=option_map[option],
            timestamp_ms=timestamp_ms,
        )

        client = VoteClient(server_host=vote_host, server_port=vote_port, ca_cert=ca_cert)
        try:
            status, _ = client.send_vote(packet, listen_seconds=0)
        except TimeoutError:
            return {"error": "vote server timeout"}, 504

        if status == STATUS_ACCEPTED:
            with voted_users_lock:
                voted_users[username] = (packet.client_id, packet.sequence)

        if status == STATUS_DUPLICATE:
            return {
                "status": "duplicate",
                "code": STATUS_DUPLICATE,
                "client_id": packet.client_id,
                "option": option,
                "message": "only one vote per user is allowed",
            }, 200

        return {"status": status_label(status), "code": status, "client_id": client_id, "option": option}, 200

    return app
