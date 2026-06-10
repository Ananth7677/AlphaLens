import uuid
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """Adds created_at and updated_at to any model."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


def generate_uuid() -> str:
    return str(uuid.uuid4())


def model_to_dict(model) -> dict:
    """Convert a SQLAlchemy model to a plain dict, coercing Decimal to float."""
    if model is None:
        return {}

    result = {}
    for column in model.__table__.columns:
        value = getattr(model, column.name)
        if value is not None and hasattr(value, '__float__'):
            value = float(value)
        result[column.name] = value

    return result
