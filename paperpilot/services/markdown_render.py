from __future__ import annotations

import html
import re

try:
    import markdown as markdown_lib
except ImportError:
    markdown_lib = None  # type: ignore[assignment]


def render_markdown_html(markdown_text: str) -> str:
    text = markdown_text or ""
    if markdown_lib is not None:
        return markdown_lib.markdown(
            text,
            extensions=["tables", "fenced_code", "nl2br"],
        )
    return _basic_markdown_html(text)


def _basic_markdown_html(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    paragraph: list[str] = []
    list_open = False
    code_open = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            out.append(f"<p>{_inline_markup(' '.join(paragraph))}</p>")
            paragraph = []

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            out.append("</ul>")
            list_open = False

    for raw_line in lines:
        line = raw_line.rstrip()
        if line.strip().startswith("```"):
            if code_open:
                out.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
                code_open = False
                code_lines = []
            else:
                flush_paragraph()
                close_list()
                code_open = True
                code_lines = []
            continue
        if code_open:
            code_lines.append(line)
            continue
        if not line.strip():
            flush_paragraph()
            close_list()
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline_markup(heading.group(2).strip())}</h{level}>")
            continue
        bullet = re.match(r"^\s*[-*]\s+(.+)$", line)
        if bullet:
            flush_paragraph()
            if not list_open:
                out.append("<ul>")
                list_open = True
            out.append(f"<li>{_inline_markup(bullet.group(1).strip())}</li>")
            continue
        paragraph.append(line.strip())

    if code_open:
        out.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
    flush_paragraph()
    close_list()
    return "\n".join(out)


def _inline_markup(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped
