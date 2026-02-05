from __future__ import annotations
import os
import signal
import threading
import time
from collections.abc import Callable
# Thread pool: handle multiple requests concurrently (one slow request doesn't block others).
from concurrent.futures import ThreadPoolExecutor
from http.server import HTTPServer
from typing import TYPE_CHECKING, Optional

from lib.helpers.process import kill_process_on_port
from lib.handler import HttpServerHandler

if TYPE_CHECKING:
  from lib.error import HttpServerError

# Reusable type: handler function(request) -> None
HandlerFunc = Callable[[HttpServerHandler], None]

# error_handler(request, error) -> None; see lib.error
ErrorHandlerFunc = Callable[[HttpServerHandler, "HttpServerError"], None]


class ThreadPooledHTTPServer(HTTPServer):
  """HTTPServer that handles each request in a thread from a fixed-size pool."""

  # Allow binding to a recently-used port (e.g., after restart)
  allow_reuse_address = True

  def __init__(self, server_address, RequestHandlerClass, max_workers: int = 1):
    """
    server_address: Address to bind.
    RequestHandlerClass: Class to handle requests.
    max_workers: Max concurrent handler threads (default 1 = single-threaded).
    """
    # Initialize executor to None first so server_close() won't fail
    # if super().__init__() raises an exception (e.g., "Address already in use")
    self._executor: Optional[ThreadPoolExecutor] = None
    super().__init__(server_address, RequestHandlerClass)

    # Executor for handling requests in threads (Handlers Queue for execution)
    self._executor = ThreadPoolExecutor(max_workers=max_workers)

  def process_request(self, request, client_address):
    # Submit the request to the executor for handling in a thread
    # The executor will handle the request in a thread from the pool, which is already started
    # The thread will be closed when the request is finished (when the handler function returns)
    if self._executor is not None:
      self._executor.submit(self._process_request_thread, request, client_address)

  def _process_request_thread(self, request, client_address):
    # One process (PID), multiple threads (name + id) share the same PID
    t = threading.current_thread()
    print(f"Processing request in thread {t.name} (id {t.ident}) in process PID {os.getpid()}")
    self.finish_request(request, client_address)
    self.shutdown_request(request)

  def server_close(self):
    """Close the listening socket, then wait for all handler threads to finish and shut down the pool."""
    super().server_close()  # stop accepting new connections
    if self._executor is not None:
      self._executor.shutdown(wait=True)  # block until all in-flight handlers complete, then close threads
      self._executor = None


class HttpServer():
  """Server that takes a handler function(request) for all methods and request/response."""

  port: int = 3000
  handler: Optional[HandlerFunc] = None
  error_handler: Optional[HandlerFunc] = None
  server: Optional[ThreadPooledHTTPServer] = None
  max_threads: int = 1

  def __init__(
    self,
    port: int,
    handler: HandlerFunc,
    error_handler: Optional[ErrorHandlerFunc] = None,
    max_threads: int = 1,
  ):
    """
    port: Port to bind.
    handler: Function(request) that handles every request.
    error_handler: Optional function(request, error) for any uncaught error (runtime, 5xx, etc.).
    max_threads: Max concurrent handler threads (default 1 = single-threaded).
    """
    self.port = port
    self.handler = handler
    self.error_handler = error_handler
    self.max_threads = max_threads
    self.server = None

  def start(self, _retries: int = 0):
    max_retries = 2

    def shutdown_handler(signum, frame):
      """Handle SIGINT/SIGTERM by gracefully shutting down the server."""
      print("\nShutting down server...")
      if self.server is not None:
        # shutdown() must be called from a different thread
        threading.Thread(target=self.server.shutdown).start()

    try:
      self.server = ThreadPooledHTTPServer(
        ("", self.port), HttpServerHandler, max_workers=self.max_threads
      )
      self.server.handler_func = self.handler
      self.server.error_handler_func = self.error_handler

      # Register signal handlers for graceful shutdown (hot reload friendly)
      signal.signal(signal.SIGINT, shutdown_handler)
      signal.signal(signal.SIGTERM, shutdown_handler)

      print(f"Serving at port {self.port}")
      self.server.serve_forever(poll_interval=0.1)  # Faster poll for quicker shutdown
    except OSError as e:
      if e.errno == 48 and _retries < max_retries:  # Address already in use
        print(f"Port {self.port} is already in use. Attempting to free it...")
        if kill_process_on_port(self.port):
          print("Freed the port. Waiting for OS to release...")
          time.sleep(0.5)  # Give OS time to release the port
          self.start(_retries=_retries + 1)
        else:
          print(f"Could not free port {self.port}. Stop the other process manually or use a different port.")
          raise
      else:
        raise
    finally:
      if self.server is not None:
        self.server.server_close()
        self.server = None

  def stop(self):
    if self.server is not None:
      self.server.server_close()
      self.server = None

  def __enter__(self):
    """Return self; do not start here. Call server.start() in the with body (it blocks)."""
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    self.stop()