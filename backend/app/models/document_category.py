import enum


class DocumentCategory(str, enum.Enum):
    """What kind of purchase a scanned historical document is about — used
    only by the (secondary) document-extraction pipeline when importing a
    previously issued document image. Not a property of a `Sale` itself."""

    GROCERIES = "groceries"
    DINING = "dining"
    TRANSPORT = "transport"
    UTILITIES = "utilities"
    HEALTH = "health"
    SHOPPING = "shopping"
    ENTERTAINMENT = "entertainment"
    TRAVEL = "travel"
    HOUSING = "housing"
    OTHER = "other"
