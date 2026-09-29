"""The reference factory's user roles. The seed writes these into the `roles`
table; application code compares against them instead of repeating the strings.
"""

import enum


class RoleCode(enum.StrEnum):
    ADMIN = "Admin"
    PLANNER = "Planner"
    PRODUCTION = "Production"
    LAB = "Lab"
    FORKLIFT = "Forklift"
    MANAGER = "Manager"
    WAREHOUSE_MANAGER = "WarehouseManager"
    DIRECTOR = "Director"
    CHECKER = "Checker"
    PACKER = "Packer"
    DISPATCH = "Dispatch"
    SUPER_ADMIN = "SuperAdmin"
