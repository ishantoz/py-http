# py-http

A thin wrapper around Python's `http.server` module.

**Experimental** - Built to learn how Python handles HTTP and TCP at the standard library level. Prototype, not production-ready.

## The problem

Using Python's `http.server` directly means:
- Subclassing `BaseHTTPRequestHandler`
- Writing separate `do_GET()`, `do_POST()`, `do_PUT()` methods for each HTTP method
- Parsing query strings yourself with `urllib.parse`
- Manually writing status codes, headers, and encoding response bytes

I wanted a single function that receives every request, with the path and query params already parsed, and simple helpers to send responses.

## Features

- Single handler function for all HTTP methods
- Parsed query params and path available on request
- Response helpers for common formats
- Reverse proxy / fetch support
- Streaming responses
- Separate error handler for exceptions
- Thread pool with `max_threads` for concurrent requests

## Response Helpers

### Basic responses

```python
# JSON response
request.response.json({"key": "value"}, status=200)

# HTML response
request.response.html("<h1>Hello</h1>", status=200)

# Plain text response
request.response.text("Hello world", status=200)

# Redirect
request.response.redirect("/new-path", status=302)
```

### Response object

Like the Web Response API - body type determines Content-Type automatically:

```python
from lib.response import Response

# JSON (dict/list → application/json)
request.response.rewrite(Response({"ok": True}))
request.response.rewrite(Response({"error": "not found"}, 404))

# Text (str → text/plain)
request.response.rewrite(Response("Hello", 200))

# Raw bytes (no Content-Type)
request.response.rewrite(Response(b"raw data", 200))

# With custom headers
request.response.rewrite(Response(
    {"data": 1},
    status=201,
    headers={"X-Custom": "value"}
))
```

### Fetch and proxy

Fetch a URL and get a Response object you can modify:

```python
from lib.fetch import fetch

resp = fetch("https://api.example.com/data")
resp.header("X-Proxied-By", "py-http")
request.response.rewrite(resp)
```

### Streaming

Stream directly from a URL to the client without buffering:

```python
request.response.stream("https://example.com/large-file.zip")
```

## Example

```python
from lib.http import HttpServer
from lib.handler import HttpServerHandler
from lib.error import HttpServerError

def handler(request: HttpServerHandler) -> None:
    # Read body for POST/PUT (requires Content-Length)
    content_length = request.headers.get("Content-Length")
    body = request.rfile.read(int(content_length)).decode() if content_length else ""
    
    request.response.json({
        "path": request.path_no_query,
        "query_params": request.query_params,
        "method": request.command,
        "body": body,
    })

def error_handler(request: HttpServerHandler, error: HttpServerError) -> None:
    request.response.json({"error": error.message}, status=error.status_code)

with HttpServer(port=8000, handler=handler, error_handler=error_handler, max_threads=3) as server:
    server.start()
```

## Request object

Available on the handler's `request` parameter:

| Property | Description |
|----------|-------------|
| `request.path_no_query` | Path without query string (`/users`) |
| `request.query_params` | Parsed query params as dict |
| `request.headers` | Request headers |
| `request.command` | HTTP method (`GET`, `POST`, etc.) |
| `request.rfile` | Request body stream |
| `request.response` | Response helper object |

## Run

```bash
python main.py
```

With hot reload (requires `watchfiles`):

```bash
./dev.py
```
