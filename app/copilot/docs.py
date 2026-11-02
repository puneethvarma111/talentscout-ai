"""Uploaded document store (in memory, per session) + keyword retrieval with citations."""
from __future__ import annotations

import io
import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

POLICY_FILE = Path(__file__).resolve().parent.parent / "data" / "hr_policies.json"
MAX_BYTES = 5 * 1024 * 1024
STOP = set("a an the of to in for on and or is are be with by at it this that what how do does i my me we our can".split())

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s-]{8,}\d)(?!\d)")


def redact_pii(text: str) -> str:
    return PHONE_RE.sub("[phone redacted]", EMAIL_RE.sub("[email redacted]", text))


@dataclass
class Doc:
    id: str
    name: str
    kind: str  # "policy" | "resume" | "jd" | "other"
    text: str
    chunks: list[str] = field(default_factory=list)


def extract_text(filename: str, data: bytes) -> str:
    if len(data) > MAX_BYTES:
        raise ValueError("File is larger than 5 MB.")
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix in (".txt", ".md", ".csv", ".json"):
        return data.decode("utf-8", errors="replace")
    raise ValueError("Unsupported file type. Use .pdf, .txt, .md or .csv.")


def guess_kind(name: str, text: str) -> str:
    low = (name + " " + text[:1500]).lower()
    if any(w in low for w in ("resume", "curriculum vitae", " cv", "work experience", "education")):
        return "resume"
    if any(w in low for w in ("job description", "responsibilities", "requirements", "we are hiring", "jd")):
        return "jd"
    if any(w in low for w in ("policy", "handbook", "entitle", "leave", "code of conduct")):
        return "policy"
    return "other"


def chunk(text: str, size: int = 700) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out, buf = [], ""
    for p in paras:
        if len(buf) + len(p) > size and buf:
            out.append(buf)
            buf = ""
        buf = (buf + "\n\n" + p).strip()
    if buf:
        out.append(buf)
    return out or [text[:size]]


def make_doc(name: str, text: str, kind: str | None = None) -> Doc:
    return Doc(id=uuid.uuid4().hex[:8], name=name, kind=kind or guess_kind(name, text), text=text, chunks=chunk(text))


def _terms(q: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", q.lower()) if t not in STOP and len(t) > 1]


def builtin_policy_docs() -> list[Doc]:
    data = json.loads(POLICY_FILE.read_text())
    return [Doc(id=f"builtin-{k}", name=f"Company policy: {v['title']}", kind="policy", text=v["answer"], chunks=[v["answer"]]) for k, v in data.items()]


def search(docs: list[Doc], query: str, k: int = 4) -> list[dict[str, Any]]:
    terms = _terms(query)
    pool = [d for d in docs if d.kind in ("policy", "other")] + builtin_policy_docs()
    scored = []
    for d in pool:
        for i, c in enumerate(d.chunks):
            low = c.lower()
            score = sum(low.count(t) for t in terms) + sum(2 for t in terms if t in d.name.lower())
            if score:
                scored.append((score, d, i, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"citation": f"[{d.name} §{i + 1}]", "doc_id": d.id, "doc": d.name, "section": i + 1, "score": s, "text": c[:900]}
        for s, d, i, c in scored[:k]
    ]
