from pydantic import BaseModel


class ChartSeries(BaseModel):
    labels: list[str]
    values: list[float]
