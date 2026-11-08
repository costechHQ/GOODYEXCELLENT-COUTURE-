"""Turns an uploaded picture into safe, web-ready WebP files (FR-29, NFR-04, NFR-08).

Nothing from the original file is kept: it is decoded and drawn again from the pixels, which
drops hidden metadata (phone photos carry GPS locations) and anything smuggled into the file.
"""

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}  # judged from the file's contents, never its name or declared type
MAX_PIXELS = 40_000_000  # a 40-megapixel photo; larger is refused before it is decoded
VARIANT_WIDTHS = (400, 800, 1600)  # thumbnail, card and full size
WEBP_QUALITY = 82


class ImageRejected(Exception):
    """The upload cannot be used. `status` is the HTTP code to answer with."""

    def __init__(self, reason: str, status: int):
        super().__init__(reason)
        self.reason = reason
        self.status = status


@dataclass
class ProcessedImage:
    width: int  # the original, after rotating it upright
    height: int
    variants: dict[int, bytes]  # width in pixels -> WebP file contents


def process_image(data: bytes) -> ProcessedImage:
    try:
        image = Image.open(BytesIO(data))  # reads only the header, so the size check below is cheap
    except Image.DecompressionBombError:
        # Pillow's own guard fires at open time for absurd sizes, before our check can run.
        raise ImageRejected("That image is too large. Use one under 40 megapixels.", 422) from None
    except (UnidentifiedImageError, OSError, ValueError):
        raise ImageRejected("Upload a JPEG, PNG or WebP image.", 415) from None
    if image.format not in ALLOWED_FORMATS:
        raise ImageRejected("Upload a JPEG, PNG or WebP image.", 415)
    if image.width * image.height > MAX_PIXELS:
        raise ImageRejected("That image is too large. Use one under 40 megapixels.", 422)
    if getattr(image, "is_animated", False):
        raise ImageRejected("Animated images are not supported.", 422)

    try:
        image.load()  # the full decode: this is where a corrupt or booby-trapped file fails
        image = ImageOps.exif_transpose(image)  # stand it upright, then forget the orientation tag
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise ImageRejected("That image could not be read. It may be damaged.", 422) from None

    has_transparency = image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info)
    image = image.convert("RGBA" if has_transparency else "RGB")

    width, height = image.size
    widths = sorted({w for w in VARIANT_WIDTHS if w < width} | {min(width, max(VARIANT_WIDTHS))})
    variants = {}
    for target in widths:
        resized = image if target == width else image.resize((target, max(1, round(height * target / width))), Image.LANCZOS)
        out = BytesIO()
        resized.save(out, format="WEBP", quality=WEBP_QUALITY, method=4)  # no exif or icc argument: nothing carried over
        variants[target] = out.getvalue()
    return ProcessedImage(width=width, height=height, variants=variants)
