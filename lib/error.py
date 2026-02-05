"""Production-ready error handling: HttpServerError and helpers for error_handler."""
from __future__ import annotations
import traceback
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
  from lib.handler import HttpServerHandler

# error_handler(request, error) -> None
ErrorHandlerFunc = Callable[["HttpServerHandler", "HttpServerError"], None]


class HttpServerError(Exception):
  """
  Wraps any error during request handling. Used by the server to call your error_handler.

  - status_code: HTTP status (500 for runtime errors, or 4xx/5xx from HttpStatusError).
  - message: Safe message for response (no stack trace in production).
  - exception: The original exception, if any (for logging; do not send to client).
  - debug: If True, message may include details; set via from_exception(..., debug=True).
  """

  def __init__(
    self,
    status_code: int = 500,
    message: str = "Internal Server Error",
    exception: BaseException | None = None,
    debug: bool = False,
  ) -> None:
    super().__init__(message)
    self.status_code = status_code
    self.message = message
    self.exception = exception
    self.debug = debug

  @classmethod
  def from_exception(
    cls,
    exc: BaseException,
    status_code: int = 500,
    message: str | None = None,
    debug: bool = False,
  ) -> "HttpServerError":
    """
    Build HttpServerError from any exception. Use in production with debug=False.
    """
    if message is None:
      message = str(exc) if debug else "Internal Server Error"
    return cls(
      status_code=status_code,
      message=message,
      exception=exc,
      debug=debug,
    )

  def traceback_str(self) -> str:
    """Full traceback for logging; only use server-side, never send to client."""
    if self.exception is None:
      return ""
    return "".join(traceback.format_exception(type(self.exception), self.exception, self.exception.__traceback__))


def default_error_handler(request: HttpServerHandler, error: HttpServerError) -> None:
  """
  Production default: HTML error page with status, no stack trace.
  Use request.response so it works with your response helpers.
  """
  request.response.html(
    f"<!DOCTYPE html><html><head><title>Error {error.status_code}</title></head>"
    f"<body><h1>Error {error.status_code}</h1><p>{error.message}</p></body></html>",
    status=error.status_code,
  )
