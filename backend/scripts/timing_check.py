"""Timing checks for NFR-05 (form responses 2 s or less) and NFR-29 (gallery with 500 items).

Run against a real server and real PostgreSQL. Start the API with the enquiry rate limit raised so the
run is not throttled, for example:

    RATE_LIMIT_MAX_REQUESTS=100000 uv run fastapi run --port 8000
    uv run python scripts/timing_check.py

It adds 500 temporary gallery items (captions start with "timing-check") and removes them afterwards.
Enquiries it creates are removed too (their names start with "Timing Check").
"""

import argparse
import asyncio
import io
import statistics
import time

import httpx
from PIL import Image
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models import Enquiry, GalleryItem
from app.models.enums import GalleryCategory

PHONE = "+2348031234567"
FORMS = {
    "consultation": {"name": "Timing Check", "phone": PHONE, "preferred_contact": "call", "message": "Hello"},
    "laundry": {"name": "Timing Check", "phone": PHONE, "garment_type": "Agbada"},
    "contact": {"name": "Timing Check", "email": "t@example.com", "subject": "Hi", "message": "A test message"},
}
ORDER = {"name": "Timing Check", "phone": PHONE, "preferred_contact": "call", "garment_type": "Senator"}


def jpeg(size=(1600, 1200)) -> bytes:
    img = Image.effect_noise(size, 60).convert("RGB")  # noisy, so it is a realistic (large) photo
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def report(label: str, times: list[float], limit: float) -> bool:
    times = sorted(times)
    p95 = times[max(0, int(len(times) * 0.95) - 1)]
    ok = times[-1] <= limit
    print(
        f"{'PASS' if ok else 'FAIL'}  {label:<46} n={len(times):<3} median={statistics.median(times) * 1000:7.0f} ms"
        f"  p95={p95 * 1000:7.0f} ms  max={times[-1] * 1000:7.0f} ms  (limit {limit * 1000:.0f} ms)"
    )
    return ok


async def timed(client: httpx.AsyncClient, method: str, url: str, expect: int, **kw) -> float:
    start = time.perf_counter()
    response = await client.request(method, url, **kw)
    elapsed = time.perf_counter() - start
    assert response.status_code == expect, f"{method} {url} -> {response.status_code} {response.text[:200]}"
    return elapsed


async def series(client, label, limit, n, concurrency, *args, **kw) -> bool:
    sem = asyncio.Semaphore(concurrency)

    async def one():
        async with sem:
            return await timed(client, *args, **kw)

    return report(label, await asyncio.gather(*(one() for _ in range(n))), limit)


async def main(base_url: str, n: int, concurrency: int) -> int:
    categories = list(GalleryCategory)
    async with SessionLocal() as session:
        session.add_all(
            GalleryItem(
                image_url=f"https://example.com/p/{i}.webp",
                caption=f"timing-check {i}",
                alt_text="A garment",
                category=categories[i % len(categories)],
                featured=i % 10 == 0,
                display_order=i,
            )
            for i in range(500)
        )
        await session.commit()
    results = []
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
            print(f"Gallery with 500 items (NFR-29), {n} requests each, {concurrency} at a time")
            for label, params in [
                ("GET /gallery (first 100)", {"limit": 100}),
                ("GET /gallery (last page, offset 400)", {"limit": 100, "offset": 400}),
                ("GET /gallery?category=suit", {"limit": 100, "category": "suit"}),
                ("GET /gallery?featured=true", {"featured": "true"}),
            ]:
                results.append(await series(client, label, 1.0, n, concurrency, "GET", "/gallery", 200, params=params))
            print(f"\nForm submissions (NFR-05), {n} requests each, {concurrency} at a time")
            for form, body in FORMS.items():
                results.append(
                    await series(
                        client,
                        f"POST /enquiries/{form}",
                        2.0,
                        n,
                        concurrency,
                        "POST",
                        f"/enquiries/{form}",
                        201,
                        json=body,
                    )
                )
            results.append(
                await series(
                    client,
                    "POST /enquiries/order (no pictures)",
                    2.0,
                    n,
                    concurrency,
                    "POST",
                    "/enquiries/order",
                    201,
                    data=ORDER,
                )
            )
            photo = jpeg()
            print(f"\nOrder form with 5 pictures of {len(photo) / 1024:.0f} KB each (the heaviest request)")
            files = [("images", (f"p{i}.jpg", photo, "image/jpeg")) for i in range(5)]
            results.append(
                await series(
                    client,
                    "POST /enquiries/order (5 pictures)",
                    2.0,
                    max(5, n // 3),
                    concurrency,
                    "POST",
                    "/enquiries/order",
                    201,
                    data=ORDER,
                    files=files,
                )
            )
    finally:
        async with SessionLocal() as session:
            await session.execute(delete(GalleryItem).where(GalleryItem.caption.like("timing-check%")))
            await session.execute(delete(Enquiry).where(Enquiry.name.like("Timing Check%")))
            await session.commit()
    print("\nAll within limits." if all(results) else "\nSOME CHECKS FAILED.")
    return 0 if all(results) else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("-n", type=int, default=30, help="requests per check")
    ap.add_argument("--concurrency", type=int, default=5, help="simultaneous requests")
    a = ap.parse_args()
    raise SystemExit(asyncio.run(main(a.base_url, a.n, a.concurrency)))
