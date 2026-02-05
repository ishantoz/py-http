#! /usr/bin/env python3
from lib.error import HttpServerError
from lib.http import HttpServer
from lib.handler import HttpServerHandler

def handler(request: HttpServerHandler) -> None:
  # Example of using response.stream() to proxy a request
  if request.path_no_query == "/search":
      query = request.query_params.get("q", "")
      if not query:
        request.response.json({"error": "Missing ?q= parameter"}, status=400)
        return
      from urllib.parse import quote
      url = f"https://api.duckduckgo.com/?q={quote(query)}&format=json&no_html=1"
      request.response.stream(url)
      return
 
  content_length = request.headers.get("Content-Length")
  body = ""
  if content_length:
    body = request.rfile.read(int(content_length)).decode("utf-8")
  
  data = {
    "path": request.path_no_query,
    "query_params": request.query_params,
    "headers": dict(request.headers.items()),
    "method": request.command,
    "body": body,
  }
  request.response.json(data, status=200)

def error_handler(request: HttpServerHandler, error: HttpServerError) -> None:
  error_data = {
    "status_code": error.status_code,
    "message": error.message,
    "traceback": error.traceback_str() if error.debug else None,
    "path": request.path_no_query,
    "query_params": request.query_params,
    "headers": dict(request.headers.items()),
    "method": request.command,
  }
  request.response.json(error_data, status=error.status_code)

def main():
  with HttpServer(port=8000, handler=handler, error_handler=error_handler, max_threads=3) as server:
    print("Press Ctrl+C to stop the server")
    server.start()

if __name__ == "__main__":
  main()
