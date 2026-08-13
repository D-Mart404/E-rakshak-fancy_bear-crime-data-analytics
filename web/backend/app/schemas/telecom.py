from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TelecomEventModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = Field(default=None, alias="_id")
    event_id: str
    event_type: str  # CDR / IPDR
    msisdn: str
    timestamp: datetime | None = None

    # CDR fields
    b_party: str = ""
    duration_sec: int = 0
    call_type: str = ""
    first_cell_id: str = ""
    location: str = ""

    # IPDR fields
    ip_address: str = ""
    data_volume_up: float = 0.0
    data_volume_down: float = 0.0
    cell_id: str = ""
