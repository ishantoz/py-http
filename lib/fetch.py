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
      resp_headers = {k: v for k, v in resp.getheaders() if k.lower() not in _HOP_BY_HOP}
      return Response(resp.read(), resp.status, resp_headers)
  except HTTPError as e:
    resp_headers = {k: v for k, v in e.headers.items() if k.lower() not in _HOP_BY_HOP}
    return Response(e.read(), e.code, resp_headers)
  except URLError as e:
    return Response(f"Bad Gateway: {e.reason}", 502)
  except TimeoutError:
    return Response("Gateway Timeout", 504)
