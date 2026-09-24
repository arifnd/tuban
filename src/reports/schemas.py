from pydantic import BaseModel


class ReportTable(BaseModel):
    key: str
    title: str
    columns: list[str]
    rows: list[list[str]]
