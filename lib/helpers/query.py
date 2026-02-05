"""Parse request path, query string, and POST form body."""
from __future__ import annotations
from urllib.parse import parse_qs
from typing import Union

# Single-value params: str. Array params (?key[]=a&key[]=b): list[str].
QueryParams = dict[str, Union[str, list[str]]]


def parse_path_and_query(full_path: str) -> tuple[str, QueryParams]:
  """
  Split the request path into path-only and query parameters.

  - full_path: Raw path from request (e.g. "/users?id=1&name=foo").
  - Returns: (path_without_query, query_params).
    - path_without_query: Path only (e.g. "/users").
    - query_params: Normal keys give a single value (str). Keys with "[]" (?key[]=a&key[]=b) give a list.
      e.g. ?asdf=23 -> {"asdf": "23"}, ?id[]=1&id[]=2 -> {"id": ["1", "2"]}.
  """
  if "?" not in full_path:
    return full_path, {}
  path_part, _, query_string = full_path.partition("?")
  raw = parse_qs(query_string, keep_blank_values=True)
  query_params: QueryParams = {}
  for key, values in raw.items():
    if key.endswith("[]"):
      name = key[:-2]
      query_params[name] = values
    else:
      query_params[key] = values[0] if values else ""
  return path_part, query_params


def get_first_query(params: QueryParams, key: str, default: str = "") -> str:
  """Get the first value for a query param key (works for both str and list[str] values)."""
  v = params.get(key, default)
  if isinstance(v, list):
    return v[0] if v else default
  return v if v != "" else default


def query_to_string(params: QueryParams) -> str:
  """Build a query string from query_params (for redirects/links). Lists use key[]=v."""
  from urllib.parse import urlencode
  parts: list[tuple[str, str]] = []
  for key, value in params.items():
    if isinstance(value, list):
      for v in value:
        parts.append((f"{key}[]", v))
    else:
      parts.append((key, value))
  return urlencode(parts)


def parse_post_form(rfile, headers) -> QueryParams:
  """
  Read POST body (Content-Length bytes), parse application/x-www-form-urlencoded.
  Returns same shape as query params: key -> str or list[str].
  """
  length = headers.get("Content-Length")
  if not length:
    return {}
  try:
    n = int(length)
  except ValueError:
    return {}
  if n <= 0 or n > 65536:
    return {}
  body = rfile.read(n).decode("utf-8", errors="replace")
  raw = parse_qs(body, keep_blank_values=True)
  out: QueryParams = {}
  for key, values in raw.items():
    if key.endswith("[]"):
      out[key[:-2]] = values
    else:
      out[key] = values[0] if values else ""
  return out
