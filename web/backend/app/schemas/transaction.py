from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TransactionModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = Field(default=None, alias="_id")
    transaction_id: str
    account_id: str
    statement_id: str = ""
    transaction_date: datetime | None = None
    amount: float = 0.0
    direction: str = ""  # DR / CR
    narration: str = ""
    counterparty_name: str = ""
    counterparty_account: str = ""
    counterparty_upi_id: str = ""
    mode: str = ""  # UPI / NEFT / IMPS / RTGS / CASH / OTHER
