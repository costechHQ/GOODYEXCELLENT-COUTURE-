from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, func, text, true
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db.base import Base
from app.models.enums import AdminRole


class AdminUser(Base):
    """A person who can sign in to the admin area (FR-51, FR-57, NFR-06).

    Only a password *hash* is stored; hashing itself belongs to the sign-in feature.
    """

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Least privilege by default: nobody becomes an Owner by accident (FR-57).
    role: Mapped[AdminRole] = mapped_column(
        Enum(AdminRole, validate_strings=True),
        default=AdminRole.staff,
        server_default=AdminRole.staff.value,
    )
    # Deactivate instead of deleting, so enquiry history and audit trails stay intact.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # Failed-login lockout (NFR-06). The counter resets on a good sign-in or when a lock starts.
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Sign-in tokens issued before this moment are refused, so changing a password ends any session
    # that may already be in the wrong hands (FR-56).
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @validates("email")
    def _normalise_email(self, _key: str, value: str) -> str:
        # One account per address, whatever the capitalisation or stray spaces.
        return value.strip().lower()
