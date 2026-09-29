"""The smallest possible factory: implements the four core interfaces with no
extra columns and enables no feature. Start a new factory project from here.
"""

from wms_sdk.core.db import Base
from wms_sdk.modules.inventory.models import PalletBase
from wms_sdk.modules.master_data.models import ProductPropertiesBase
from wms_sdk.modules.storage.models import LocationPropertiesBase, ZonePropertiesBase


class ProductProperties(ProductPropertiesBase, Base):
    pass


class ZoneProperties(ZonePropertiesBase, Base):
    pass


class LocationProperties(LocationPropertiesBase, Base):
    pass


class Pallet(PalletBase, Base):
    pass
