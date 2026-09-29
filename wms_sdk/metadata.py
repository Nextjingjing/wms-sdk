"""Import this to register every SDK table on `Base.metadata` — Alembic
autogenerate and DDL rendering only see tables whose modules were imported.
"""

from .core.db import Base
from .modules.events import models as events_models  # noqa: F401
from .modules.inventory import models as inventory_models  # noqa: F401
from .modules.master_data import models as master_data_models  # noqa: F401
from .modules.storage import models as storage_models  # noqa: F401
from .shared.models import plant, role, user  # noqa: F401

metadata = Base.metadata
