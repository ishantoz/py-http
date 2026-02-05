"""Response helpers attached to request as request.response.html(), .json(), etc."""
from __future__ import annotations
import mimetypes
import os
import time
from json import dumps
from typing import TYPE_CHECKING, Literal, Optional, Union
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from lib.headers import Headers, HOP_BY_HOP

if TYPE_CHECKING:
  from lib.handler import HttpServerHandler


class Response:
  """
  Response object similar to Web Response API.
  Body type determines Content-Type automatically.
  
  Examples:
    Response({"ok": True})              # JSON, status 200
    Response({"error": "not found"}, 404)  # JSON with status
    Response("Hello", 200)              # text/plain
    Response(b"raw bytes", 200)         # raw bytes, no Content-Type
    Response({"data": 1}, headers={"X-Custom": "value"})
  """
  
  def __init__(
    self,
    body: Union[dict, list, str, bytes] = b"",
    status: int = 200,
    headers: Optional[dict[str, str]] = None
  ) -> None:
    self.status = status
    self.headers: dict[str, str] = headers.copy() if headers else {}
    
    # Infer Content-Type from body type
    if isinstance(body, (dict, list)):
      self.body = dumps(body).encode("utf-8")
      if "Content-Type" not in self.headers:
        self.headers["Content-Type"] = "application/json; charset=utf-8"
    elif isinstance(body, str):
      self.body = body.encode("utf-8")
      if "Content-Type" not in self.headers:
        self.headers["Content-Type"] = "text/plain; charset=utf-8"
    else:
      self.body = body
  
  def header(self, key: str, value: str) -> Response:
    """Set a header. Returns self for chaining."""
    self.headers[key] = value
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
    Send a Response object to the client.
    
    Examples:
      request.response.rewrite(Response({"ok": True}))
      request.response.rewrite(Response("Hello", 200))
      request.response.rewrite(Response({"error": "not found"}, 404))
    """
    r = self._request
    r.send_response(resp.status)
    for key, value in resp.headers.items():
      r.send_header(key, value)
    r.end_headers()
    r.wfile.write(resp.body)

  def streamProxy(
    self,
    url: str,
    method: str = "GET",
    headers = None,
    body: Optional[bytes] = None,
    timeout: int = 30,
    chunk_size: int = 8192
  ) -> None:
    """
    Stream response from URL directly to client without buffering.
    
    Pass headers to forward to upstream. Accepts Headers object, dict, or HTTPMessage.
    Hop-by-hop headers are filtered automatically.
    
    Examples:
      request.response.streamProxy(url)  # no headers
      request.response.streamProxy(url, headers=proxy_headers(request.headers))
      request.response.streamProxy(url, headers={"Referer": "https://example.com"})
    """
    r = self._request
    req_headers = headers.to_proxy_dict()

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
    
    # Send status and headers (206 for partial content, 200 for full)
    r.send_response(upstream.status)
    for key, value in upstream.getheaders():
      if key.lower() not in HOP_BY_HOP:
        r.send_header(key, value)
    # Ensure Accept-Ranges is set for seekable content
    if not any(h[0].lower() == "accept-ranges" for h in upstream.getheaders()):
      r.send_header("Accept-Ranges", "bytes")
    r.end_headers()
    
    # Stream body in chunks
    while True:
      chunk = upstream.read(chunk_size)
      if not chunk:
        break
      r.wfile.write(chunk)
    
    upstream.close()

  def file(
    self,
    path: str,
    mode: Literal["stream", "buffer", "sendfile"] = "sendfile",
    content_type: Optional[str] = None,
    headers: Optional[dict[str, str]] = None,
    chunk_size: int = 8192,
    simulate_delay_ms: int = 0,
    status: int = 200
  ) -> None:
    """
    Send a local file to the client.
    
    Args:
      path: Path to the local file
      mode: "sendfile" uses kernel-level zero-copy transfer (most efficient, default),
            "stream" reads and sends in chunks (low memory, holds file during transfer),
            "buffer" reads into memory first then sends all at once (higher memory usage)
      content_type: MIME type (auto-detected from extension if not provided)
      headers: Additional response headers (e.g., Content-Disposition for download)
      chunk_size: Chunk size for stream mode (default 8192 bytes)
      simulate_delay_ms: Delay in milliseconds between chunks (stream mode only, for testing)
      status: HTTP status code (default 200)
    
    Examples:
      request.response.file("/path/to/video.mp4")  # sendfile (most efficient) by default
      request.response.file("/path/to/video.mp4", mode="stream")  # manual chunking
      request.response.file("/path/to/image.png", mode="buffer")  # load into memory first
      request.response.file("/path/to/data.bin", content_type="application/octet-stream")
      request.response.file("/path/to/video.mp4", headers={"Content-Disposition": "attachment"})
    """
    r = self._request
    
    # Check if file exists
    if not os.path.exists(path):
      r.send_response(404)
      r.send_header("Content-Type", "text/plain")
      r.end_headers()
      r.wfile.write(b"File not found")
      return
    
    # Check if path is a file (not a directory)
    if not os.path.isfile(path):
      r.send_response(400)
      r.send_header("Content-Type", "text/plain")
      r.end_headers()
      r.wfile.write(b"Path is not a file")
      return
    
    # Get file size and detect content type
    file_size = os.path.getsize(path)
    if content_type is None:
      content_type, _ = mimetypes.guess_type(path)
      content_type = content_type or "application/octet-stream"
    
    # Parse Range header for partial content support
    range_header = r.headers.get("Range")
    start, end = 0, file_size - 1
    
    if range_header and range_header.startswith("bytes="):
      try:
        range_spec = range_header[6:]  # Remove "bytes="
        if range_spec.startswith("-"):
          # Last N bytes: bytes=-500
          suffix_len = int(range_spec[1:])
          start = max(0, file_size - suffix_len)
        elif range_spec.endswith("-"):
          # From offset to end: bytes=500-
          start = int(range_spec[:-1])
        else:
          # Explicit range: bytes=500-999
          parts = range_spec.split("-")
          start = int(parts[0])
          end = int(parts[1]) if parts[1] else file_size - 1
        
        # Validate range
        if start > end or start >= file_size:
          r.send_response(416)  # Range Not Satisfiable
          r.send_header("Content-Range", f"bytes */{file_size}")
          r.end_headers()
          return
        
        end = min(end, file_size - 1)
        status = 206  # Partial Content
      except ValueError:
        pass  # Invalid range, send full file
    
    content_length = end - start + 1
    
    # Send headers
    r.send_response(status)
    r.send_header("Content-Type", content_type)
    r.send_header("Content-Length", str(content_length))
    r.send_header("Accept-Ranges", "bytes")
    if status == 206:
      r.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
    if headers:
      for key, value in headers.items():
        r.send_header(key, value)
    r.end_headers()
    
    # Send file content
    if mode == "sendfile":
      # Sendfile mode: kernel-level zero-copy transfer (most efficient)
      # Data goes directly from file to socket without copying through Python
      r.wfile.flush()  # Flush any buffered headers
      socket_fd = r.connection.fileno()
      with open(path, "rb") as f:
        file_fd = f.fileno()
        sent = 0
        while sent < content_length:
          # os.sendfile returns number of bytes sent (may be less than requested)
          chunk = os.sendfile(socket_fd, file_fd, start + sent, content_length - sent)
          if chunk == 0:
            break  # Connection closed
          sent += chunk
    elif mode == "buffer":
      # Buffer mode: read entire range into memory, then send all at once
      with open(path, "rb") as f:
        f.seek(start)
        data = f.read(content_length)
      r.wfile.write(data)
    else:
      # Stream mode: read and send in chunks (holds file open during transfer)
      with open(path, "rb") as f:
        f.seek(start)
        remaining = content_length
        while remaining > 0:
          read_size = min(chunk_size, remaining)
          chunk = f.read(read_size)
          if not chunk:
            break
          r.wfile.write(chunk)
          remaining -= len(chunk)
          if simulate_delay_ms > 0:
            time.sleep(simulate_delay_ms / 1000)
