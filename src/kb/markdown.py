import nh3
from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark", {"html": False, "linkify": True, "typographer": False}).enable("table").enable("strikethrough")

ALLOWED_TAGS = {
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "p",
    "br",
    "hr",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "s",
    "del",
    "code",
    "pre",
    "blockquote",
    "ul",
    "ol",
    "li",
    "a",
    "img",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
}

ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
}

ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}


def render_markdown(text: str | None) -> str:
    """Render Markdown to HTML and sanitize it with a strict allow-list."""
    raw = _md.render(text or "")
    return nh3.clean(raw, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, url_schemes=ALLOWED_URL_SCHEMES)


def plain_excerpt(text: str | None, limit: int = 240) -> str:
    """Strip Markdown-ish noise and return a short plain-text snippet."""
    if not text:
        return ""
    stripped = _md.render(text or "")
    stripped = nh3.clean(stripped, tags=set(), attributes={})
    stripped = " ".join(stripped.split())
    return stripped[:limit]
