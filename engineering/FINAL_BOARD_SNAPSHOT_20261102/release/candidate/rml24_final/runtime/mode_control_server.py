"""Unix control server matching the existing RML24 framebuffer UI protocol."""

from __future__ import annotations

import os
import socket
import stat
import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class ModeSnapshot:
    mode: str
    running: bool
    command_id: int


class ModeState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._mode = "FIXED"
        self._running = True
        self._command_id = 0

    def snapshot(self) -> ModeSnapshot:
        with self._lock:
            return ModeSnapshot(self._mode, self._running, self._command_id)

    def apply(self, line: str) -> tuple[int, ModeSnapshot]:
        tokens = line.strip().split()
        with self._lock:
            if tokens[:1] == ["SET_MODE"] and len(tokens) == 2:
                if tokens[1] not in {"FIXED", "BAND_SCAN"}:
                    raise ValueError("unsupported_mode")
                self._mode = tokens[1]
            elif tokens == ["START"]:
                self._running = True
            elif tokens == ["STOP"]:
                self._running = False
            else:
                raise ValueError("unknown_command")
            self._command_id += 1
            return self._command_id, ModeSnapshot(self._mode, self._running, self._command_id)


def status_line(snapshot: ModeSnapshot) -> str:
    running = 1 if snapshot.running else 0
    return (
        f"OK requested_mode={snapshot.mode} requested_running={running} "
        f"applied_mode={snapshot.mode} applied_running={running} "
        f"pending_mode=0 pending_run=0 last_applied_command_id={snapshot.command_id}"
    )


class ModeControlServer:
    def __init__(self, path: str, state: ModeState) -> None:
        self.path = path
        self.state = state
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._listener: socket.socket | None = None

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("control server already started")
        if os.path.lexists(self.path):
            mode = os.lstat(self.path).st_mode
            if not stat.S_ISSOCK(mode):
                raise RuntimeError(f"refusing to unlink non-socket path {self.path}")
            os.unlink(self.path)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(self.path)
        listener.listen(1)
        listener.settimeout(0.25)
        self._listener = listener
        self._thread = threading.Thread(target=self._serve, name="rml24-mode-control", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._listener is not None:
            self._listener.close()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if os.path.lexists(self.path) and stat.S_ISSOCK(os.lstat(self.path).st_mode):
            os.unlink(self.path)

    def _serve(self) -> None:
        assert self._listener is not None
        while not self._stop.is_set():
            try:
                connection, _ = self._listener.accept()
            except (TimeoutError, socket.timeout):
                continue
            except OSError:
                break
            with connection:
                stream = connection.makefile("rwb", buffering=0)
                while not self._stop.is_set():
                    raw = stream.readline()
                    if not raw:
                        break
                    line = raw.decode("ascii", errors="strict").strip()
                    if line == "STATUS":
                        stream.write((status_line(self.state.snapshot()) + "\n").encode("ascii"))
                        continue
                    try:
                        command_id, _ = self.state.apply(line)
                    except ValueError as exc:
                        stream.write((f"ERR {exc}\n").encode("ascii"))
                        continue
                    stream.write((f"OK accepted command_id={command_id} {line}\n").encode("ascii"))
                    stream.write((f"OK applied command_id={command_id} {line}\n").encode("ascii"))

