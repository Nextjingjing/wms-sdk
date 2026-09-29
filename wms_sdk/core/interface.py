from typing import Any, ClassVar

from sqlalchemy.orm import Session, declared_attr

from .errors import NotSet


class Interface:
    """Base for SDK tables that each factory must implement exactly once.

    The SDK declares an interface with `root=True`; it fixes the table name,
    key columns and any constraints on them (`base_table_args`). A factory
    implements it by subclassing it together with `Base` and adding columns.
    Its own constraints go in `extra_table_args`, never `__table_args__`,
    which would silently drop the interface's constraints.
    """

    roots: ClassVar[list[type["Interface"]]] = []
    base_table_args: ClassVar[tuple] = ()
    extra_table_args: ClassVar[tuple] = ()
    _root: ClassVar[type["Interface"]]
    _implementation: ClassVar[type["Interface"] | None]

    @declared_attr.directive
    def __table_args__(cls) -> tuple:
        return (*cls.base_table_args, *cls.extra_table_args)

    def __init_subclass__(cls, root: bool = False, **kwargs: Any) -> None:
        if root:
            cls._root = cls
            cls._implementation = None
            Interface.roots.append(cls)
            super().__init_subclass__(**kwargs)
            return
        # Checked before super(): SQLAlchemy maps the table there and would
        # fail with a less helpful "table already defined" error.
        existing = cls._root._implementation
        if existing is not None:
            raise TypeError(
                f"{cls._root.__tablename__} already implemented by {existing.__qualname__}; "
                f"{cls.__qualname__} cannot implement it again"
            )
        if "__table_args__" in cls.__dict__:
            raise TypeError(f"{cls.__qualname__}: put constraints in extra_table_args")
        super().__init_subclass__(**kwargs)
        cls._root._implementation = cls

    @classmethod
    def implementation(cls) -> type["Interface"]:
        root = cls._root
        if root._implementation is None:
            raise NotImplementedError(
                f"no factory implements {root.__tablename__}; "
                f"subclass {root.__qualname__} together with Base"
            )
        return root._implementation


def get_row(session: Session, interface: type[Interface], key: Any) -> Any:
    """Load the factory's row for `key`; raise NotSet when there is none."""
    row = session.get(interface.implementation(), key)
    if row is None:
        raise NotSet(f"{interface.__tablename__} has no row for {key!r}")
    return row
