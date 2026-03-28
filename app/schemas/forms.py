from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class EventCreateForm(BaseModel):
    event_date: date
    title: str = Field(min_length=3, max_length=255)
    short_description: str | None = None
    location: str | None = None


class ValuationCreateForm(BaseModel):
    valuation_kind: str
    date_effective: date
    value_uah: Decimal | None = None
    document_id: int | None = None
    notes: str | None = None
