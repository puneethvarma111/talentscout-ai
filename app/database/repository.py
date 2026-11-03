from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.database.connection import get_connection
from app.schemas.research import ResearchPlan, ResearchSessionDetail, ResearchSessionSummary, ResearchStage, SessionStatus
from app.schemas.source import ExtractedFinding, ExtractStatus, SourceRecord


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResearchRepository:
    def create_session(self, question: str) -> str:
        session_id = str(uuid.uuid4())
        now = _now()
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, question, status, stage, iteration, created_at, updated_at)
                VALUES (?, ?, ?, ?, 0, ?, ?)
                """,
                (session_id, question, SessionStatus.PENDING.value, ResearchStage.UNDERSTANDING.value, now, now),
            )
        return session_id

    def update_session(
        self,
        session_id: str,
        *,
        status: SessionStatus | None = None,
        stage: ResearchStage | None = None,
        iteration: int | None = None,
        plan: ResearchPlan | None = None,
        report_md: str | None = None,
        error: str | None = None,
    ) -> None:
        fields: list[str] = ["updated_at = ?"]
        values: list[object] = [_now()]
        if status is not None:
            fields.append("status = ?")
            values.append(status.value)
        if stage is not None:
            fields.append("stage = ?")
            values.append(stage.value)
        if iteration is not None:
            fields.append("iteration = ?")
            values.append(iteration)
        if plan is not None:
            fields.append("plan_json = ?")
            values.append(plan.model_dump_json())
        if report_md is not None:
            fields.append("report_md = ?")
            values.append(report_md)
        if error is not None:
            fields.append("error = ?")
            values.append(error)
        values.append(session_id)
        with get_connection() as conn:
            conn.execute(f"UPDATE sessions SET {', '.join(fields)} WHERE id = ?", values)

    def append_event(self, session_id: str, event_type: str, payload: dict | None = None) -> int:
        payload = payload or {}
        with get_connection() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) AS m FROM events WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            seq = int(row["m"]) + 1
            conn.execute(
                """
                INSERT INTO events (session_id, seq, type, payload_json, ts)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, seq, event_type, json.dumps(payload), _now()),
            )
            return seq

    def add_queries(self, session_id: str, iteration: int, queries: list[str]) -> None:
        with get_connection() as conn:
            for q in queries:
                conn.execute(
                    "INSERT INTO queries (session_id, iteration, query_text) VALUES (?, ?, ?)",
                    (session_id, iteration, q),
                )

    def upsert_source(self, source: SourceRecord) -> int:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sources (session_id, url, title, snippet, published_date, extract_status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id, url) DO UPDATE SET
                    title = excluded.title,
                    snippet = excluded.snippet,
                    published_date = COALESCE(excluded.published_date, sources.published_date)
                """,
                (
                    source.session_id,
                    source.url,
                    source.title,
                    source.snippet,
                    source.published_date,
                    source.extract_status.value,
                ),
            )
            row = conn.execute(
                "SELECT id FROM sources WHERE session_id = ? AND url = ?",
                (source.session_id, source.url),
            ).fetchone()
            return int(row["id"])

    def update_source_status(self, source_id: int, status: ExtractStatus) -> None:
        with get_connection() as conn:
            conn.execute("UPDATE sources SET extract_status = ? WHERE id = ?", (status.value, source_id))

    def update_running_summary(self, session_id: str, summary_md: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET running_summary_md = ?, updated_at = ? WHERE id = ?",
                (summary_md, _now(), session_id),
            )

    def get_running_summary(self, session_id: str) -> str | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT running_summary_md FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return row["running_summary_md"]

    def add_finding(self, session_id: str, source_id: int | None, finding: ExtractedFinding) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO findings (session_id, source_id, finding_json) VALUES (?, ?, ?)",
                (session_id, source_id, finding.model_dump_json()),
            )

    def list_sources(self, session_id: str) -> list[SourceRecord]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM sources WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [
            SourceRecord(
                id=row["id"],
                session_id=row["session_id"],
                url=row["url"],
                title=row["title"] or "",
                snippet=row["snippet"] or "",
                published_date=row["published_date"],
                extract_status=ExtractStatus(row["extract_status"]),
            )
            for row in rows
        ]

    def list_findings(self, session_id: str) -> list[ExtractedFinding]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT finding_json FROM findings WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [ExtractedFinding.model_validate_json(row["finding_json"]) for row in rows]

    def get_session(self, session_id: str) -> ResearchSessionDetail | None:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if not row:
                return None
            qrows = conn.execute(
                "SELECT query_text FROM queries WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
            counts = conn.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM sources WHERE session_id = ?) AS sources_discovered,
                    (SELECT COUNT(*) FROM sources WHERE session_id = ? AND extract_status = 'success') AS sources_extracted,
                    (SELECT COUNT(*) FROM findings WHERE session_id = ?) AS findings_count
                """,
                (session_id, session_id, session_id),
            ).fetchone()
        plan = ResearchPlan.model_validate_json(row["plan_json"]) if row["plan_json"] else None
        return ResearchSessionDetail(
            id=row["id"],
            question=row["question"],
            status=SessionStatus(row["status"]),
            stage=ResearchStage(row["stage"]),
            iteration=row["iteration"],
            sources_discovered=counts["sources_discovered"],
            sources_extracted=counts["sources_extracted"],
            findings_count=counts["findings_count"],
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            plan=plan,
            search_queries=[r["query_text"] for r in qrows],
            report_markdown=row["report_md"],
            running_summary_md=row["running_summary_md"] if "running_summary_md" in row.keys() else None,
        )

    def list_history(self, limit: int = 50) -> list[ResearchSessionSummary]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        summaries: list[ResearchSessionSummary] = []
        for row in rows:
            detail = self.get_session(row["id"])
            if detail:
                summaries.append(
                    ResearchSessionSummary(
                        id=detail.id,
                        question=detail.question,
                        status=detail.status,
                        stage=detail.stage,
                        iteration=detail.iteration,
                        sources_discovered=detail.sources_discovered,
                        sources_extracted=detail.sources_extracted,
                        findings_count=detail.findings_count,
                        error=detail.error,
                        created_at=detail.created_at,
                        updated_at=detail.updated_at,
                    )
                )
        return summaries

    def delete_session(self, session_id: str) -> bool:
        with get_connection() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cur.rowcount > 0

    def list_events(self, session_id: str, since_seq: int = 0) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT seq, type, payload_json, ts FROM events
                WHERE session_id = ? AND seq > ? ORDER BY seq
                """,
                (session_id, since_seq),
            ).fetchall()
        return [
            {
                "seq": row["seq"],
                "type": row["type"],
                "payload": json.loads(row["payload_json"]),
                "ts": row["ts"],
            }
            for row in rows
        ]
