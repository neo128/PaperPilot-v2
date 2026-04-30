from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import requests

from paperpilot.utils.http import create_session, request_with_retry


@dataclass
class OAPdfResult:
    status: str
    source: str = ""
    pdf_url: str = ""
    landing_url: str = ""
    error: str = ""


class OpenAccessClient:
    def __init__(
        self,
        *,
        email: Optional[str] = None,
        user_agent: str = "PaperPilot-v2/0.1",
        timeout: int = 30,
    ) -> None:
        self.email = email
        self.timeout = timeout
        self.session = create_session(headers={"User-Agent": user_agent})

    def find_pdf(self, *, doi: str = "", arxiv_id: str = "") -> OAPdfResult:
        arxiv_id = (arxiv_id or "").strip()
        if arxiv_id:
            return OAPdfResult(
                status="found",
                source="arxiv",
                pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                landing_url=f"https://arxiv.org/abs/{arxiv_id}",
            )

        doi = (doi or "").strip()
        if not doi:
            return OAPdfResult(status="missing_identifier")
        if not self.email:
            return OAPdfResult(status="missing_unpaywall_email")

        try:
            resp = request_with_retry(
                self.session,
                "get",
                f"https://api.unpaywall.org/v2/{quote(doi)}",
                params={"email": self.email},
                timeout=self.timeout,
            )
        except Exception as exc:
            return OAPdfResult(status="lookup_failed", source="unpaywall", error=f"{type(exc).__name__}: {exc}")

        data = resp.json() or {}
        best = data.get("best_oa_location") or {}
        pdf_url = best.get("url_for_pdf") or ""
        landing_url = best.get("url") or data.get("doi_url") or ""
        if pdf_url:
            return OAPdfResult(status="found", source="unpaywall", pdf_url=pdf_url, landing_url=landing_url)
        if landing_url and data.get("is_oa"):
            return OAPdfResult(status="oa_landing_only", source="unpaywall", landing_url=landing_url)
        return OAPdfResult(status="not_open_access", source="unpaywall", landing_url=landing_url)

    def download_pdf(self, pdf_url: str, destination: Path, *, force: bool = False) -> Path:
        if destination.exists() and not force:
            return destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        resp = request_with_retry(self.session, "get", pdf_url, timeout=self.timeout, stream=True)
        content_type = (resp.headers.get("Content-Type") or "").lower()
        content = resp.content
        if "pdf" not in content_type and not content.startswith(b"%PDF"):
            raise ValueError(f"URL did not return a PDF: content-type={content_type or 'unknown'}")
        tmp = destination.with_suffix(destination.suffix + ".tmp")
        tmp.write_bytes(content)
        tmp.replace(destination)
        return destination
