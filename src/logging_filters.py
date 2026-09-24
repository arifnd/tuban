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
