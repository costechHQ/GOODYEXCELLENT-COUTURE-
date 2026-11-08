import csv
import io
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_admin, require_owner
from app.core.phone import normalise_phone
from app.db.session import get_session
from app.models import Enquiry
from app.models.enums import EnquiryStatus, EnquiryType
from app.schemas.enquiry import EnquiryDetail, EnquiryPage, EnquiryUpdate

# Enquiries hold clients' personal details, so every route needs a signed-in admin (FR-51, FR-53).
router = APIRouter(prefix="/admin/enquiries", tags=["admin"], dependencies=[Depends(get_current_admin)])

Session = Annotated[AsyncSession, Depends(get_session)]

_SEARCHED_TEXT = (Enquiry.name, Enquiry.email, Enquiry.subject, Enquiry.message, Enquiry.service, Enquiry.phone)
NEWEST_FIRST = (Enquiry.created_at.desc(), Enquiry.id.desc())  # id breaks ties between equal timestamps


def _search_filter(q: str):
    """Case-insensitive substring match. `%` and `_` are escaped so they match themselves and
    never act as wildcards. A phone-like search also matches the stored international form,
    so "08031112222" finds "+2348031112222"."""
    backslash = "\\"
    escaped = q.replace(backslash, backslash * 2).replace("%", backslash + "%").replace("_", backslash + "_")
    pattern = f"%{escaped}%"
    conditions = [column.ilike(pattern, escape=backslash) for column in _SEARCHED_TEXT]
    try:
        conditions.append(Enquiry.phone == normalise_phone(q))
    except ValueError:
        pass
    return or_(*conditions)


@dataclass
class EnquiryFilters:
    """The filters shared by the list and the export, so the two can never disagree."""

    type: EnquiryType | None = None
    status: EnquiryStatus | None = None
    q: Annotated[str | None, Query(max_length=100)] = None

    def conditions(self) -> list:
        conditions = []
        if self.type is not None:
            conditions.append(Enquiry.type == self.type)
        if self.status is not None:
            conditions.append(Enquiry.status == self.status)
        if self.q is not None and self.q.strip():  # a blank search box means no search
            conditions.append(_search_filter(self.q.strip()))
        return conditions


Filters = Annotated[EnquiryFilters, Depends()]


@router.get("", response_model=EnquiryPage)
async def list_enquiries(
    session: Session,
    filters: Filters,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    conditions = filters.conditions()
    total = await session.scalar(select(func.count()).select_from(Enquiry).where(*conditions))
    query = select(Enquiry).where(*conditions).order_by(*NEWEST_FIRST).limit(limit).offset(offset)
    items = (await session.scalars(query)).all()
    return EnquiryPage(items=items, total=total, limit=limit, offset=offset)


# --- CSV export (FR-53) -----------------------------------------------------

MAX_EXPORT_ROWS = 10_000
_EXPORT_COLUMNS = (
    "id", "created_at", "type", "status", "name", "phone", "email", "preferred_contact", "service",
    "subject", "message", "preferred_at", "garment_type", "occasion", "needed_by", "quantity",
    "fabric_preference", "internal_notes",
)  # fmt: skip
_NORMALISED_PHONE = re.compile(r"\+\d{8,15}")
_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")
_UTF8_BOM = "\N{ZERO WIDTH NO-BREAK SPACE}"  # makes Excel read accented names correctly


def _csv_cell(value) -> str:
    """Text for one spreadsheet cell. A cell starting with = + - @ (or a tab or return) would be run
    as a formula by Excel or Sheets, so a malicious name could execute code on the owner's computer;
    those get a leading apostrophe. Normalised phone numbers (+234...) are safe and left as they are."""
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    text = str(getattr(value, "value", value))  # enums export their plain value
    if text.startswith(_FORMULA_STARTS) and not _NORMALISED_PHONE.fullmatch(text):
        return "'" + text
    return text


@router.get("/export.csv", dependencies=[Depends(require_owner)])
async def export_enquiries(session: Session, filters: Filters):
    """Every matching enquiry as a CSV file, newest first. Owner only: it exposes client contact
    details in bulk. Declared before /{enquiry_id} so "export.csv" is not read as an id."""
    conditions = filters.conditions()
    total = await session.scalar(select(func.count()).select_from(Enquiry).where(*conditions))
    if total > MAX_EXPORT_ROWS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{total} enquiries match; narrow the filters to {MAX_EXPORT_ROWS} or fewer",
        )
    rows = (await session.scalars(select(Enquiry).where(*conditions).order_by(*NEWEST_FIRST))).all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)  # quotes commas, quotes and line breaks inside messages
    writer.writerow(_EXPORT_COLUMNS)
    for row in rows:
        writer.writerow([_csv_cell(getattr(row, column)) for column in _EXPORT_COLUMNS])

    filename = f"enquiries-{datetime.now(UTC):%Y-%m-%d}.csv"
    return Response(
        content=_UTF8_BOM + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",  # personal data: never keep a copy in a cache
        },
    )


async def _load_detail(session: AsyncSession, enquiry_id: int) -> Enquiry:
    """One enquiry with its reference images, or 404. The images are never loaded implicitly."""
    enquiry = await session.scalar(
        select(Enquiry)
        .options(selectinload(Enquiry.reference_images))
        .where(Enquiry.id == enquiry_id)
        .execution_options(populate_existing=True)  # always the current database state
    )
    if enquiry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Enquiry not found")
    return enquiry


@router.get("/{enquiry_id}", response_model=EnquiryDetail)
async def get_enquiry(enquiry_id: int, session: Session):
    return await _load_detail(session, enquiry_id)


@router.patch("/{enquiry_id}", response_model=EnquiryDetail)
async def update_enquiry(enquiry_id: int, data: EnquiryUpdate, session: Session):
    """Move an enquiry through its workflow and keep staff notes. Any status may follow any other
    (FR-53 sets no order), so a Closed enquiry can be reopened."""
    enquiry = await _load_detail(session, enquiry_id)
    for name, value in data.model_dump(exclude_unset=True).items():
        setattr(enquiry, name, value)
    await session.commit()
    return await _load_detail(session, enquiry_id)
