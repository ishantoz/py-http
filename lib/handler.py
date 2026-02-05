import http.server
import traceback

from lib.error import HttpServerError, default_error_handler
from lib.helpers.query import parse_path_and_query
from lib.response import ResponseHelper


class HttpServerHandler(http.server.BaseHTTPRequestHandler):
  """Calls the app's handler function(request) for every request.
  Request (self) has:
    .command, .path (full path with query), .headers, .rfile, .wfile,
    .path_no_query (path only, no query string),
    .query_params (param name -> str or list[str]; arrays only for ?key[]=),
    .response (request.response.html(), .json(), .text(), .redirect()),
    .send_response(), etc.
  """

  def handle_one_request(self):
    # Set response helper before parsing so it's available to app handlers.
    # (Cannot set in __init__: base class __init__ calls handle() and never returns to our __init__.)
    self.response = ResponseHelper(self)
    try:
      self.raw_requestline = self.rfile.readline(65537)
      if len(self.raw_requestline) > 65536:
        self.requestline = ""
        self.request_version = ""
        self.command = ""
        self.send_error(414, "Request URI Too Long")
        return
      if not self.raw_requestline:
        self.close_connection = True
        return
      if not self.parse_request():
        return
      self._set_path_and_query()
      self.handle_request()
      self.wfile.flush()
    except (BrokenPipeError, ConnectionResetError):
      self.close_connection = True
    except Exception as e:
      self._handle_error(e)

  def _set_path_and_query(self) -> None:
    """Set .path_no_query and .query_params from .path (full path with optional query)."""
    path_only, query_params = parse_path_and_query(self.path)
    self.path_no_query = path_only
    self.query_params = query_params

  def _handle_error(self, exc: Exception) -> None:
    """Call error_handler(request, error) or default; log traceback server-side."""
    # Client disconnected - nothing to do
    if isinstance(exc, (BrokenPipeError, ConnectionResetError)):
      self.close_connection = True
      return
    if not hasattr(self, "path_no_query"):
      path_only, query_params = parse_path_and_query(getattr(self, "path", "/"))
      self.path_no_query = path_only
      self.query_params = query_params
    error = HttpServerError.from_exception(exc, debug=False)
    self.log_error("Request error: %r", exc)
    error_handler = getattr(self.server, "error_handler_func", None)
    if callable(error_handler):
      try:
        error_handler(self, error)
        self.wfile.flush()
      except (BrokenPipeError, ConnectionResetError):
        # Client disconnected during error response
        self.close_connection = True
      except Exception:
        self.log_error("Error in error_handler: %s", traceback.format_exc())
        self.close_connection = True
    else:
      try:
        default_error_handler(self, error)
        self.wfile.flush()
      except (BrokenPipeError, ConnectionResetError):
        self.close_connection = True

  def handle_request(self):
    """Call the app's handler function(request). Request is self (this handler instance)."""
    handler_func = getattr(self.server, "handler_func", None)
    if not callable(handler_func):
      self.send_error(501, "No handler configured")
      return
    try:
      handler_func(self)
    except Exception as e:
      self._handle_error(e)
