import threading
import time
from pathlib import Path


class TimerManager:
    def __init__(self, config, command_runner, on_start=None, on_stop=None):
        self.config = config
        self.command_runner = command_runner
        self.on_start = on_start
        self.on_stop = on_stop
        self._lock = threading.RLock()
        self._thread = None
        self._cancel_event = None
        self._end_time = None

    def start(self, minutes):
        self.cancel()

        cancel_event = threading.Event()
        end_time = time.time() + minutes * 60
        thread = threading.Thread(
            target=self._run_timer,
            args=(end_time, cancel_event),
            daemon=True,
        )

        with self._lock:
            self._thread = thread
            self._cancel_event = cancel_event
            self._end_time = end_time
            self._write_state_file(end_time)

        thread.start()

    def _run_timer(self, end_time, cancel_event):
        self.command_runner(self.config.iptv_commands["on"])
        if self.on_start:
            self.on_start()

        poll_interval = self.config.timer_poll_interval_seconds

        while True:
            remaining = end_time - time.time()
            if remaining <= 0:
                break
            if cancel_event.wait(timeout=min(poll_interval, remaining)):
                self._clear_if_current(cancel_event)
                return

        self.command_runner(self.config.iptv_commands["off"])
        if self.on_stop:
            self.on_stop()
        self._clear_if_current(cancel_event)

    def cancel(self):
        with self._lock:
            thread = self._thread
            cancel_event = self._cancel_event
            had_timer = thread is not None and thread.is_alive()
            if cancel_event is not None:
                cancel_event.set()

        if thread is not None and thread.is_alive():
            thread.join(timeout=self.config.timer_cancel_join_timeout_seconds)

        if cancel_event is not None:
            self._clear_if_current(cancel_event)

        return had_timer

    def get_remaining(self):
        with self._lock:
            end_time = self._end_time
            if end_time is None:
                return None

            remaining = end_time - time.time()
            if remaining <= 0:
                self._clear_state_unlocked()
                return None
            return int(remaining)

    def should_skip_crontab_off(self):
        return self.get_remaining() is not None

    def _clear_if_current(self, cancel_event):
        with self._lock:
            if self._cancel_event is cancel_event:
                self._clear_state_unlocked()

    def _clear_state_unlocked(self):
        self._thread = None
        self._cancel_event = None
        self._end_time = None
        self._remove_state_file()

    def _write_state_file(self, end_time):
        path = Path(self.config.timer_state_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(end_time), encoding="utf-8")

    def _remove_state_file(self):
        path = Path(self.config.timer_state_file)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
