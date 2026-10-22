import enum


class EnquiryType(enum.StrEnum):
    consultation = "consultation"
    order = "order"
    laundry = "laundry"
    general = "general"


class EnquiryStatus(enum.StrEnum):  # FR-53
    new = "new"
    contacted = "contacted"
    in_progress = "in_progress"
    completed = "completed"
    closed = "closed"


class ContactMethod(enum.StrEnum):  # FR-30
    whatsapp = "whatsapp"
    call = "call"
    email = "email"


class GalleryCategory(enum.StrEnum):  # FR-25
    senator = "senator"
    kaftan = "kaftan"
    suit = "suit"
    shirt = "shirt"
    trouser = "trouser"
    agbada = "agbada"
    womens_senator = "womens_senator"


class AdminRole(enum.StrEnum):  # FR-57 (Release 2; column exists now)
    owner = "owner"
    staff = "staff"
