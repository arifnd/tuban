import re
import unicodedata


def slugify(text: str) -> str:
    """Lowercase, strip accents, and hyphenate a title into a URL slug."""
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text or "item"


def normalize_tag(name: str) -> str:
    return " ".join((name or "").split())
