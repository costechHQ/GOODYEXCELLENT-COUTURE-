from typing import Annotated

from pydantic import AfterValidator, AnyHttpUrl, StringConstraints, TypeAdapter

_URL = TypeAdapter(AnyHttpUrl)


def _check_image_url(value: str) -> str:
    # Only absolute http(s) URLs: blocks javascript:, data: and relative paths from being stored.
    _URL.validate_python(value)
    return value


ImageUrl = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    AfterValidator(_check_image_url),
]
