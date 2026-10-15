from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DeribitError(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: int
    message: str


class DeribitResponse[ResultT](BaseModel):
    model_config = ConfigDict(frozen=True)

    result: ResultT | None = None
    error: DeribitError | None = None


class IndexPriceResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    index_price: Decimal = Field(gt=0, allow_inf_nan=False)
