import json
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "talentscout.sqlite3"


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE IF NOT EXISTS candidates (
        candidate_key TEXT PRIMARY KEY, payload TEXT NOT NULL,
        stage TEXT NOT NULL DEFAULT 'Sourced', updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    connection.commit()
    return connection


def save_candidates(items: list[dict[str, Any]]) -> None:
    with _connect() as connection:
        for index, item in enumerate(items):
            key = item.get("profile_url") or item.get("url") or item.get("username") or f"candidate-{index}"
            connection.execute(
                """INSERT INTO candidates(candidate_key, payload)
                VALUES (?, ?) ON CONFLICT(candidate_key) DO UPDATE SET payload=excluded.payload,
                updated_at=CURRENT_TIMESTAMP""",
                (key, json.dumps(item, ensure_ascii=False)),
            )


def list_candidates() -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute("SELECT candidate_key, payload, stage FROM candidates").fetchall()
    return [{**json.loads(row["payload"]), "pipeline_stage": row["stage"], "candidate_key": row["candidate_key"]} for row in rows]


def set_stage(candidate_key: str, stage: str) -> None:
    with _connect() as connection:
        connection.execute(
            "UPDATE candidates SET stage=?, updated_at=CURRENT_TIMESTAMP WHERE candidate_key=?",
            (stage, candidate_key),
        )
        connection.commit()
