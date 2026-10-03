"""Task statements: Markdown to safe HTML (CLAUDE.md: markdown-it-py + nh3).

Teachers write the Markdown, students read the HTML, so everything is sanitized: no
scripts, styles, event handlers or raw HTML get through, links open only http(s).
Fenced code is highlighted on the server with Pygments.
"""

import nh3
from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

_ALLOWED_TAGS = {
    "p", "br", "hr", "h1", "h2", "h3", "h4", "strong", "em", "del", "code", "pre",
    "blockquote", "ul", "ol", "li", "a", "table", "thead", "tbody", "tr", "th", "td", "span",
}  # fmt: skip
_ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "span": {"class"},
    "code": {"class"},
    "pre": {"class"},
}
_FORMATTER = HtmlFormatter(nowrap=True)


def _highlight(code: str, language: str, _attrs: str) -> str:
    try:
        lexer = get_lexer_by_name(language or "text")
    except ClassNotFound:
        return ""  # markdown-it escapes it as plain code
    return highlight(code, lexer, _FORMATTER)


_MARKDOWN = (
    MarkdownIt("commonmark", {"html": False, "linkify": False, "highlight": _highlight})
    .enable("table")
    .enable("strikethrough")
)


def render_markdown(source: str) -> str:
    html = _MARKDOWN.render(source)
    return nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https"},
        link_rel="noopener noreferrer nofollow",
    )
