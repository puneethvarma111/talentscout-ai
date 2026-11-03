from __future__ import annotations

import re
from io import BytesIO

from fpdf import FPDF


def _safe_line(text: str, max_len: int = 500) -> str:
    text = re.sub(r"[#>*`]", "", text).strip()
    text = re.sub(r"\[(\d+)\]", r"[\1]", text)
    if len(text) > max_len:
        text = text[: max_len - 3] + "..."
    return text.encode("latin-1", "replace").decode("latin-1")


def markdown_to_pdf_bytes(markdown: str) -> bytes:
    pdf = FPDF()
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    width = pdf.epw
    for line in markdown.splitlines():
        text = _safe_line(line)
        if not text:
            pdf.ln(4)
            continue
        pdf.multi_cell(width, 6, text)
    out = BytesIO()
    pdf.output(out)
    return out.getvalue()
