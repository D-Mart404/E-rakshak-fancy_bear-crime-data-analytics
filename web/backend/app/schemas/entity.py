from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AccountSubDoc(BaseModel):
    account_id: str
    account_number: str = ""
    bank_name: str = ""
    ifsc: str = ""
    branch: str = ""


class EntityModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = Field(default=None, alias="_id")
    entity_id: str
    entity_name: str
    is_seed: bool = False
    accounts: list[AccountSubDoc] = []
    phones: list[str] = []
    pan: str = ""
    risk_score: float | None = None
    risk_category: str | None = None
    account_role: str | None = None
