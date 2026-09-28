import logging
import re

SENSITIVE_PATTERN = re.compile(r"((?:code|state|token|access_token|id_token|refresh_token)=)[^&\s\"']+", re.IGNORECASE)


class RedactSensitiveQueryFilter(logging.Filter):
    """Mask OAuth code/state and token query parameters in log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - defensive against bad log args
            return True
        redacted = SENSITIVE_PATTERN.sub(r"\1[REDACTED]", message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def install_redaction_filter() -> None:
    """Attach the redaction filter to every configured logger and handler.

    ``logging.config.fileConfig`` ignores filters, so this runs afterwards to
    cover uvicorn, the root logger and the shared console handler.
    """
    redaction = RedactSensitiveQueryFilter()
    loggers = [logging.getLogger()]
    loggers.extend(logging.getLogger(name) for name in ("uvicorn", "uvicorn.error", "uvicorn.access"))
    handlers = {id(handler): handler for logger in loggers for handler in logger.handlers}
    for handler in handlers.values():
        handler.addFilter(redaction)
    for logger in loggers:
        logger.addFilter(redaction)
