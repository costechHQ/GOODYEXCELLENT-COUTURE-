import enum


class GalleryCategory(enum.StrEnum):
    """The filter categories in FR-25. A gallery item must be exactly one of these."""

    senator = "senator"
    kaftan = "kaftan"
    suit = "suit"
    shirt = "shirt"
    trouser = "trouser"
    agbada = "agbada"
    womens_senator = "womens_senator"


class EnquiryType(enum.StrEnum):
    """Which form an enquiry came from (SRS 6.1)."""

    consultation = "consultation"
    order = "order"
    laundry = "laundry"
    general = "general"


class ContactMethod(enum.StrEnum):
    """How the client wants to be reached (FR-30)."""

    whatsapp = "whatsapp"
    call = "call"
    email = "email"


class EnquiryStatus(enum.StrEnum):
    """The admin workflow for an enquiry (FR-53)."""

    new = "new"
    contacted = "contacted"
    in_progress = "in_progress"
    completed = "completed"
    closed = "closed"
