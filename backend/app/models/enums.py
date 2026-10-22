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
