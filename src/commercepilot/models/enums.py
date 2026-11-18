from enum import StrEnum


class ProductStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class PriceChangeType(StrEnum):
    INITIAL = "initial"
    DECREASED = "decreased"
    UNCHANGED = "unchanged"
    INCREASED = "increased"
