import os
import shutil
import subprocess
import sys

# Useful when the app is used via hot reload: the previous instance may still hold the port.
# This kills any process listening on the given port so the new instance can bind.


def kill_process_on_port(port: int) -> bool:
  """Kill process(es) listening on the given port. Returns True if at least one was killed."""
  if sys.platform == "win32":
    return _kill_on_port_windows(port)
  return _kill_on_port_unix(port)


def _kill_on_port_windows(port: int) -> bool:
  """Find PIDs via netstat and kill them with taskkill."""
  flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
  result = subprocess.run(
    ["netstat", "-ano"],
    capture_output=True,
    text=True,
    creationflags=flags,
  )
  if result.returncode != 0:
    return False

  pids = set()
  for line in result.stdout.splitlines():
    if f":{port}" not in line or "LISTENING" not in line:
      continue
    parts = line.split()
    if parts:
      try:
        pids.add(int(parts[-1]))
      except ValueError:
        pass

  for pid in pids:
    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
  return bool(pids)


def _kill_on_port_unix(port: int) -> bool:
  """Find PIDs via lsof and kill them. Skips the current process."""
  lsof = shutil.which("lsof")
  if not lsof:
    return False

  result = subprocess.run(
    [lsof, "-t", "-i", f":{port}"],
    capture_output=True,
    text=True,
  )
  if result.returncode != 0 or not result.stdout.strip():
    return False

  my_pid = str(os.getpid())
  pids = [p for p in result.stdout.strip().split() if p.isdigit() and p != my_pid]

  for pid in pids:
    subprocess.run(["kill", "-9", pid], capture_output=True)
  return len(pids) > 0
