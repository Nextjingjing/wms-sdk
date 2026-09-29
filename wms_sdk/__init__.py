"""WMS SDK: shared database design for warehouse management across factories.

Import `wms_sdk.metadata` to register the core tables, implement the
interfaces (`*Base` classes) in your factory package, seed its lookups and
call `wms_sdk.checks.verify_factory` at startup. See README.md.
"""

__version__ = "0.1.2"
