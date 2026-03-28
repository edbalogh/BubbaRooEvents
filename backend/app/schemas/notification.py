from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ChannelCreate(BaseModel):
    channel_type: str
    channel_address: str


class ChannelResponse(BaseModel):
    id: int
    channel_type: str
    channel_address: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationPreferencesUpdate(BaseModel):
    max_per_day: int = 5
    quiet_hours_start: str | None = "22:00"
    quiet_hours_end: str | None = "08:00"
    enabled_types: list[str] = ["ticket_alert", "tonight", "weekly_digest", "new_match"]
