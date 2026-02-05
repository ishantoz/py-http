"""Fetch helper for making HTTP requests."""
from __future__ import annotations
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from lib.response import Response


# Headers to skip when proxying (hop-by-hop headers)
_HOP_BY_HOP = frozenset([
  "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
  "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length"
])


def fetch(
  url: str,
  method: str = "GET",
  headers: Optional[dict[str, str]] = None,
  body: Optional[bytes] = None,
  timeout: int = 30
) -> Response:
  """
  Fetch a URL and return a Response object.
  
  Example:
    resp = fetch("https://api.example.com/data")
    resp.header("X-Custom", "added")
    request.response.rewrite(resp)
  """
  req_headers = headers or {}
  try:
    req = Request(url, data=body, headers=req_headers, method=method)
    with urlopen(req, timeout=timeout) as resp:
      result = Response(resp.status)
      for key, value in resp.getheaders():
        if key.lower() not in _HOP_BY_HOP:
          result.headers[key] = value
      result.body = resp.read()
      return result
  except HTTPError as e:
    result = Response(e.code)
    for key, value in e.headers.items():
      if key.lower() not in _HOP_BY_HOP:
        result.headers[key] = value
    result.body = e.read()
    return result
  except URLError as e:
    return Response(502).set_body(f"Bad Gateway: {e.reason}")
  except TimeoutError:
    return Response(504).set_body("Gateway Timeout")
