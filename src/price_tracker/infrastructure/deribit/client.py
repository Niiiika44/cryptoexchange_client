from collections.abc import Mapping
from decimal import Decimal
from http import HTTPStatus
from typing import Final

import aiohttp
from pydantic import ValidationError
from yarl import URL

from price_tracker.application import ExchangeResponseError, ExchangeUnavailableError
from price_tracker.domain import Ticker
from price_tracker.infrastructure.deribit.schemas import DeribitResponse, IndexPriceResult

_EXCHANGE: Final = "Deribit"
_MAX_RESPONSE_BYTES: Final = 64 * 1024


class DeribitClient:
    """``IndexPriceProvider`` backed by the public Deribit HTTP API."""

    def __init__(self, session: aiohttp.ClientSession, base_url: URL) -> None:
        self._session = session
        self._base_url = base_url

    async def get_index_price(self, ticker: Ticker) -> Decimal:
        result = await self._call(
            "public/get_index_price",
            params={"index_name": ticker.value},
            response_type=DeribitResponse[IndexPriceResult],
        )
        return result.index_price

    async def _call[ResultT](
        self,
        method: str,
        *,
        params: Mapping[str, str],
        response_type: type[DeribitResponse[ResultT]],
    ) -> ResultT:
        status, body = await self._get(method, params)
        if status == HTTPStatus.TOO_MANY_REQUESTS or status >= HTTPStatus.INTERNAL_SERVER_ERROR:
            raise ExchangeUnavailableError(_EXCHANGE)
        if HTTPStatus.MULTIPLE_CHOICES <= status < HTTPStatus.BAD_REQUEST:
            raise ExchangeResponseError(_EXCHANGE, detail=f"unexpected redirect (HTTP {status})")
        try:
            response = response_type.model_validate_json(body)
        except ValidationError as error:
            raise ExchangeResponseError(_EXCHANGE, detail="malformed payload") from error

        if response.error is not None:
            detail = f"error {response.error.code}: {response.error.message}"
            raise ExchangeResponseError(_EXCHANGE, detail=detail)
        if response.result is None:
            raise ExchangeResponseError(_EXCHANGE, detail="payload has no result")
        return response.result

    async def _get(self, method: str, params: Mapping[str, str]) -> tuple[int, bytes]:
        url = self._base_url / method
        try:
            async with self._session.get(url, params=params, allow_redirects=False) as response:
                return response.status, await _read_limited(response)
        except (aiohttp.ClientError, TimeoutError) as error:
            raise ExchangeUnavailableError(_EXCHANGE) from error


async def _read_limited(response: aiohttp.ClientResponse) -> bytes:
    body = bytearray()
    async for chunk in response.content.iter_any():
        body += chunk
        if len(body) > _MAX_RESPONSE_BYTES:
            raise ExchangeResponseError(_EXCHANGE, detail="response is too large")
    return bytes(body)
