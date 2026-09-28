CHUNK_SIZE = 64 * 1024

IMAGE_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "gif", "webp"})
DOCUMENT_EXTENSIONS = frozenset({"pdf", "txt", "csv", "md", "json", "log", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "zip"})

# Types that browsers can execute in the app origin (HTML/SVG/JS/XML and friends).
# User media is served same-origin, so these must never be accepted for upload or
# rendered inline, otherwise stored XSS / CSRF-token theft is possible.
ACTIVE_CONTENT_EXTENSIONS = frozenset(
    {
        "htm",
        "html",
        "xhtml",
        "shtml",
        "phtml",
        "svg",
        "svgz",
        "xml",
        "xsl",
        "xslt",
        "js",
        "mjs",
        "cjs",
        "jsx",
        "ts",
        "tsx",
        "vbs",
        "wsf",
        "hta",
        "htc",
        "jar",
        "swf",
    }
)

# Server-side safe allow-list. Admin-configured extensions must be a subset of it.
SAFE_EXTENSIONS = (IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS) - ACTIVE_CONTENT_EXTENSIONS
ALLOWED_EXTENSIONS = SAFE_EXTENSIONS
