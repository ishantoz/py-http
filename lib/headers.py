"""Web-standard-like Headers class for normalizing HTTP headers."""
from __future__ import annotations
from typing import Union, Iterator
from http.client import HTTPMessage


# Headers to skip when proxying (hop-by-hop + problematic headers)
HOP_BY_HOP = frozenset([
  "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
  "te", "trailers", "transfer-encoding", "upgrade", "host",
  "accept-encoding", "content-length"  # avoid compressed/chunked issues
])


class Headers:
  """
  Web-standard-like Headers class.
  
  Accepts HTTPMessage (from request.headers), dict, list of tuples, or another Headers.
  Header names are case-insensitive (stored lowercase internally).
  
  Examples:
    headers = Headers(request.headers)  # from HTTPMessage
    headers = Headers({"Content-Type": "application/json"})
    headers = Headers([("X-Custom", "value")])
    
    headers.get("content-type")  # case-insensitive
    headers.set("X-New", "value")
    headers["Range"] = "bytes=0-100"
    
    for key, value in headers:
      print(f"{key}: {value}")
  """
  
  def __init__(self, init: Union[HTTPMessage, dict, list, "Headers", None] = None) -> None:
    self._headers: dict[str, str] = {}
    
    if init is None:
      return
    
    if isinstance(init, Headers):
      self._headers = init._headers.copy()
    elif isinstance(init, HTTPMessage):
      for key, value in init.items():
        self._headers[key.lower()] = value
    elif isinstance(init, dict):
      for key, value in init.items():
        self._headers[key.lower()] = str(value)
    elif isinstance(init, list):
      for key, value in init:
        self._headers[key.lower()] = str(value)
  
  def get(self, name: str, default: str = "") -> str:
    """Get header value (case-insensitive)."""
    return self._headers.get(name.lower(), default)
  
  def set(self, name: str, value: str) -> Headers:
    """Set header value. Returns self for chaining."""
    self._headers[name.lower()] = value
    return self
  
  def delete(self, name: str) -> Headers:
    """Delete a header. Returns self for chaining."""
    self._headers.pop(name.lower(), None)
    return self
  
  def has(self, name: str) -> bool:
    """Check if header exists."""
    return name.lower() in self._headers
  
  def keys(self) -> Iterator[str]:
    """Iterate over header names."""
    return iter(self._headers.keys())
  
  def values(self) -> Iterator[str]:
    """Iterate over header values."""
    return iter(self._headers.values())
  
  def items(self) -> Iterator[tuple[str, str]]:
    """Iterate over (name, value) pairs."""
    return iter(self._headers.items())
  
  def to_dict(self) -> dict[str, str]:
    """Convert to plain dict."""
    return self._headers.copy()
  
  def to_proxy_dict(self) -> dict[str, str]:
    """Convert to dict, filtering out hop-by-hop headers (for proxying)."""
    return {k: v for k, v in self._headers.items() if k not in HOP_BY_HOP}
  
  def copy(self) -> Headers:
    """Create a copy of this Headers object."""
    return Headers(self)
  
  def __getitem__(self, name: str) -> str:
    return self._headers.get(name.lower(), "")
  
  def __setitem__(self, name: str, value: str) -> None:
    self._headers[name.lower()] = value
  
  def __delitem__(self, name: str) -> None:
    self._headers.pop(name.lower(), None)
  
  def __contains__(self, name: str) -> bool:
    return name.lower() in self._headers
  
  def __iter__(self) -> Iterator[tuple[str, str]]:
    return iter(self._headers.items())
  
  def __len__(self) -> int:
    return len(self._headers)
  
  def __repr__(self) -> str:
    return f"Headers({self._headers})"
  
  def __bool__(self) -> bool:
    return len(self._headers) > 0


def proxy_headers(headers: Union[Headers, HTTPMessage, dict, None]) -> Headers:
  """
  Create Headers suitable for proxying - filters out hop-by-hop headers.
  
  Example:
    h = proxy_headers(request.headers)
    h.set("referer", "https://example.com")  # override
    request.response.stream(url, headers=h)
  """
  result = Headers()
  if headers is None:
    return result
  
  source = Headers(headers) if not isinstance(headers, Headers) else headers
  for key, value in source:
    if key not in HOP_BY_HOP:
      result.set(key, value)
  return result
