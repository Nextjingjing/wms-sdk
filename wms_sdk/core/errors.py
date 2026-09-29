class NotSet(Exception):
    """A row the factory has not provided yet (e.g. product properties)."""


class LookupNotSeeded(Exception):
    """A lookup table the factory must seed is empty."""
