CHUNK_SIZE = 64 * 1024

IMAGE_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "gif", "webp"})
DOCUMENT_EXTENSIONS = frozenset({"pdf", "txt", "csv", "md", "json", "log", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "zip"})
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS
