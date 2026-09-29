import enum


class PalletEvent(enum.StrEnum):
    """Standard event_type values for pallet changes, so reports read the same
    across factories. Pass to `record_event`; a factory may add its own
    `pallet.<verb>` types for steps these do not cover.
    """

    LOADED = "pallet.loaded"  # goods put on an empty pallet
    PUTAWAY = "pallet.putaway"  # placed into a storage location
    MOVED = "pallet.moved"  # moved between locations or positions
    PICKED = "pallet.picked"  # part of the load taken off
    ADJUSTED = "pallet.adjusted"  # qty corrected, e.g. after a count
    SHIPPED = "pallet.shipped"  # left the warehouse with its load
    RETURNED = "pallet.returned"  # came back, usually empty
    RETIRED = "pallet.retired"  # broken or lost; deleted_at set
