"""Custom FastAPI response classes."""

from fastapi.responses import JSONResponse


class UTF8JSONResponse(JSONResponse):
    """JSON response with explicit UTF-8 charset for Windows clients."""

    media_type = "application/json; charset=utf-8"


__all__ = [
    "UTF8JSONResponse",
]