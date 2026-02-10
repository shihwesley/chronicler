from pydantic import BaseModel


class SyncError(BaseModel):
    file: str
    error: str


class SyncReport(BaseModel):
    synced: int = 0
    skipped: int = 0
    errors: list[SyncError] = []
    duration: float = 0.0
