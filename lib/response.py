"""Response helpers attached to request as request.response.html(), .json(), etc."""
from __future__ import annotations
from json import dumps
from typing import TYPE_CHECKING, Optional, Union
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

if TYPE_CHECKING:
  from lib.handler import HttpServerHandler


# Headers to skip when streaming (hop-by-hop headers)
_HOP_BY_HOP = frozenset([
  "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
  "te", "trailers", "transfer-encoding", "upgrade", "host"
])


class Response:
  """
  Customizable response object. Build it, then send with request.response.rewrite(resp).
  
  Example:
    resp = Response(200)
    resp.header("Content-Type", "application/json")
    resp.body = b'{"ok": true}'
    request.response.rewrite(resp)
  """
  
  def __init__(self, status: int = 200) -> None:
    self.status = status
    self.headers: dict[str, str] = {}
    self.body: bytes = b""
  
  def header(self, key: str, value: str) -> Response:
    """Set a header. Returns self for chaining."""
    self.headers[key] = value
    return self
  
  def set_body(self, body: Union[str, bytes]) -> Response:
    """Set body as str or bytes. Returns self for chaining."""
    self.body = body.encode("utf-8") if isinstance(body, str) else body
    return self
  
  def set_json(self, data: Union[dict, list]) -> Response:
    """Set body as JSON and Content-Type header. Returns self for chaining."""
    self.headers["Content-Type"] = "application/json; charset=utf-8"
    self.body = dumps(data).encode("utf-8")
    return self


class ResponseHelper:
  """Bound to the request so handlers can use request.response.html(), .json(), etc."""

  def __init__(self, request: HttpServerHandler) -> None:
    self._request = request

  def html(self, body: Union[str, bytes], status: int = 200) -> None:
    """Send an HTML response. Body can be str (utf-8) or bytes."""
    r = self._request
    r.send_response(status)
    r.send_header("Content-Type", "text/html; charset=utf-8")
    r.end_headers()
    r.wfile.write(body.encode("utf-8") if isinstance(body, str) else body)

  def text(self, body: str, status: int = 200) -> None:
    """Send a plain-text response."""
    r = self._request
    r.send_response(status)
    r.send_header("Content-Type", "text/plain; charset=utf-8")
    r.end_headers()
    r.wfile.write(body.encode("utf-8"))

  def json(self, data: Union[dict, list], status: int = 200) -> None:
    """Send a JSON response."""
    r = self._request
    r.send_response(status)
    r.send_header("Content-Type", "application/json; charset=utf-8")
    r.end_headers()
    r.wfile.write(dumps(data).encode("utf-8"))

  def redirect(self, location: str, status: int = 302) -> None:
    """Send a redirect. Default 302; use 301 for permanent."""
    r = self._request
    r.send_response(status)
    r.send_header("Location", location)
    r.end_headers()

  def rewrite(self, resp: Response) -> None:
    """
    Send a custom Response object to the client.
    
    Example:
      resp = Response(200)
      resp.header("Content-Type", "text/plain")
      resp.set_body("Hello")
      request.response.rewrite(resp)
    """
    r = self._request
    r.send_response(resp.status)
    for key, value in resp.headers.items():
      r.send_header(key, value)
    r.end_headers()
    r.wfile.write(resp.body)

  def stream(
    self,
    url: str,
    method: str = "GET",
    headers: Optional[dict[str, str]] = None,
    body: Optional[bytes] = None,
    timeout: int = 30,
    chunk_size: int = 8192
  ) -> None:
    """
    Stream response from URL directly to client without buffering.
    
    Example:
      request.response.stream("https://example.com/large-file")
    """
    r = self._request
    req_headers = headers or {}
    
    try:
      req = Request(url, data=body, headers=req_headers, method=method)
      upstream = urlopen(req, timeout=timeout)
    except HTTPError as upstream:
      pass  # HTTPError is also a response, continue streaming it
    except URLError as e:
      r.send_response(502)
      r.send_header("Content-Type", "text/plain")
      r.end_headers()
      r.wfile.write(f"Bad Gateway: {e.reason}".encode())
      return
    except TimeoutError:
      r.send_response(504)
      r.send_header("Content-Type", "text/plain")
      r.end_headers()
      r.wfile.write(b"Gateway Timeout")
      return
    
    # Send status and headers
    r.send_response(upstream.status)
    for key, value in upstream.getheaders():
      if key.lower() not in _HOP_BY_HOP:
        r.send_header(key, value)
    r.end_headers()
    
    # Stream body in chunks
    while True:
      chunk = upstream.read(chunk_size)
      if not chunk:
        break
      r.wfile.write(chunk)
    
    upstream.close()
