"""Import every ORM model module so ``Base.metadata`` is complete.

Alembic autogenerate and the test suite import this module instead of the
individual model packages: adding a new domain only requires registering it here,
which keeps migrations and tests from silently missing a table.
"""

from src.activity import models as activity_models  # noqa: F401
from src.kb import models as kb_models  # noqa: F401
from src.notifications import models as notification_models  # noqa: F401
from src.settings import models as settings_models  # noqa: F401
from src.tickets import models as ticket_models  # noqa: F401
from src.users import models as user_models  # noqa: F401

__all__ = [
    "activity_models",
    "kb_models",
    "notification_models",
    "settings_models",
    "ticket_models",
    "user_models",
]
