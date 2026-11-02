"""HRMS data access with role-based scoping.

Demo mode (default) reads synthetic `app/data/hrms_demo.json`.
Live mode (HRMS_DATA_SOURCE=live) calls hrms_core read-only GET endpoints with
HRMS_API_TOKEN + HRMS_TENANT_ID. Live mode is wired but untested against a real backend.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import httpx

DATA = Path(__file__).resolve().parent.parent / "data" / "hrms_demo.json"


class AccessDenied(Exception):
    pass


def _demo() -> dict[str, Any]:
    return json.loads(DATA.read_text())


def data_source() -> str:
    return "live" if os.getenv("HRMS_DATA_SOURCE", "demo").lower() == "live" else "demo"


def _live_get(base_env: str, default: str, path: str) -> Any:
    base = os.getenv(base_env, default).rstrip("/")
    headers = {
        "Authorization": f"Bearer {os.getenv('HRMS_API_TOKEN', '')}",
        "X-Tenant-ID": os.getenv("HRMS_TENANT_ID", ""),
    }
    resp = httpx.get(f"{base}{path}", headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def personas() -> dict[str, Any]:
    return _demo()["personas"]


def actor_for(persona: str) -> dict[str, Any]:
    p = personas().get(persona) or personas()["employee"]
    return {"persona": persona if persona in personas() else "employee", "user_id": p["user_id"], "label": p["label"]}


def employees() -> list[dict[str, Any]]:
    if data_source() == "live":
        raw = _live_get("HRMS_MASTER_DATA_URL", "http://localhost:8001", "/api/v1/masterdata/employees/active")
        rows = raw.get("content", raw) if isinstance(raw, dict) else raw
        return [
            {
                "id": str(r.get("employeeCode") or r.get("id")),
                "name": " ".join(filter(None, [r.get("firstName"), r.get("lastName")])) or r.get("name", ""),
                "designation": r.get("designationName") or r.get("designation", ""),
                "department": r.get("departmentName") or r.get("department", ""),
                "manager_id": str(r.get("reportingManagerId") or "") or None,
                "joining_date": r.get("dateOfJoining") or r.get("joiningDate"),
            }
            for r in rows
        ]
    return _demo()["employees"]


def visible_ids(actor: dict[str, Any]) -> set[str]:
    emps = employees()
    if actor["persona"] == "hr":
        return {e["id"] for e in emps}
    if actor["persona"] == "manager":
        return {actor["user_id"]} | {e["id"] for e in emps if e.get("manager_id") == actor["user_id"]}
    return {actor["user_id"]}


def resolve_employee(actor: dict[str, Any], who: str = "") -> dict[str, Any]:
    """Find an employee by id or (partial) name, enforcing RBAC."""
    emps = employees()
    who = (who or "").strip().lower()
    if who in ("", "me", "my", "myself", "self"):
        match = next((e for e in emps if e["id"] == actor["user_id"]), None)
    else:
        match = next((e for e in emps if e["id"].lower() == who), None) or next(
            (e for e in emps if who in e["name"].lower()), None
        )
    if not match:
        raise LookupError(f"No employee found matching '{who}'.")
    if match["id"] not in visible_ids(actor):
        raise AccessDenied(
            f"Your role ({actor['persona']}) cannot view {match['name']}'s records. Ask HR or their manager."
        )
    return match


def leave_balance(emp_id: str) -> dict[str, Any]:
    if data_source() == "live":
        return _live_get("HRMS_TIME_MANAGEMENT_URL", "http://localhost:8008", f"/api/leaves/employee/{emp_id}")
    bal = _demo()["leave_balances"].get(emp_id, {})
    return {k: {**v, "available": v["entitled"] - v["used"]} for k, v in bal.items()}


def leave_requests(ids: set[str]) -> list[dict[str, Any]]:
    return [r for r in _demo()["leave_requests"] if r["employee_id"] in ids]


def attendance(emp_id: str) -> dict[str, Any]:
    return _demo()["attendance_30d"].get(emp_id, {})


def tenure_years(joining: str | None, as_of: str | None = None) -> float:
    if not joining:
        return 0.0
    ref = date.fromisoformat(as_of or _demo()["as_of"])
    return round((ref - date.fromisoformat(joining)).days / 365.25, 1)


def as_of() -> str:
    return _demo()["as_of"]
