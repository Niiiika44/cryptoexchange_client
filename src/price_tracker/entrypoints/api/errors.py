from collections.abc import Awaitable, Callable
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from price_tracker.application import PriceNotFoundError, StorageUnavailableError

type ExceptionHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(PriceNotFoundError, _respond_with(HTTPStatus.NOT_FOUND))
    app.add_exception_handler(
        StorageUnavailableError,
        _respond_with(HTTPStatus.SERVICE_UNAVAILABLE),
    )


def _respond_with(status: HTTPStatus) -> ExceptionHandler:
    async def handle(_: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=status, content={"detail": str(error)})

    return handle
