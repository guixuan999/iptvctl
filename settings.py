import json
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"


@dataclass(frozen=True)
class AppConfig:
    interface: str
    ip_command: str
    brctl_command: str
    python_command: str
    logger_command: str
    command_timeout_seconds: int
    timer_poll_interval_seconds: float
    timer_cancel_join_timeout_seconds: float
    timer_state_file: Path
    timer_log_file: Path
    check_off_script: Path
    check_off_python_script: Path
    crontab_marker_start: str
    crontab_marker_end: str

    @property
    def iptv_commands(self):
        return {
            "on": [self.ip_command, "link", "set", self.interface, "up"],
            "off": [self.ip_command, "link", "set", self.interface, "down"],
        }

    @property
    def status_command(self):
        return [self.ip_command, "link", "show", self.interface]

    @property
    def schedule_on_command(self):
        return (
            f"{self.ip_command} link set {self.interface} up && "
            f'{self.logger_command} "IPTV RESTORED: web schedule"'
        )


def _read_config_text():
    encodings = ("utf-8", "utf-8-sig", "utf-16")
    last_error = None
    for encoding in encodings:
        try:
            return CONFIG_FILE.read_text(encoding=encoding)
        except UnicodeError as exc:
            last_error = exc
            continue
        except FileNotFoundError:
            return "{}"
    if last_error:
        raise last_error
    return "{}"


def load_config():
    raw = json.loads(_read_config_text() or "{}")

    interface = raw.get("interface", "eth3")
    ip_command = raw.get("ip_command", "/sbin/ip")
    brctl_command = raw.get("brctl_command", "/usr/sbin/brctl")
    python_command = raw.get("python_command", "/usr/bin/python3")
    logger_command = raw.get("logger_command", "/usr/bin/logger")
    timer_state_file = Path(raw.get("timer_state_file", "/tmp/iptv_manual_timer"))
    timer_log_file = Path(raw.get("timer_log_file", "timer_log.txt"))
    if not timer_log_file.is_absolute():
        timer_log_file = BASE_DIR / timer_log_file

    check_off_script = Path(raw.get("check_off_script", "check_and_off.sh"))
    if not check_off_script.is_absolute():
        check_off_script = BASE_DIR / check_off_script

    check_off_python_script = Path(
        raw.get("check_off_python_script", "check_and_off.py")
    )
    if not check_off_python_script.is_absolute():
        check_off_python_script = BASE_DIR / check_off_python_script

    return AppConfig(
        interface=interface,
        ip_command=ip_command,
        brctl_command=brctl_command,
        python_command=python_command,
        logger_command=logger_command,
        command_timeout_seconds=int(raw.get("command_timeout_seconds", 30)),
        timer_poll_interval_seconds=float(raw.get("timer_poll_interval_seconds", 1)),
        timer_cancel_join_timeout_seconds=float(
            raw.get("timer_cancel_join_timeout_seconds", 2)
        ),
        timer_state_file=timer_state_file,
        timer_log_file=timer_log_file,
        check_off_script=check_off_script,
        check_off_python_script=check_off_python_script,
        crontab_marker_start=raw.get(
            "crontab_marker_start", "# === IPTV SCHEDULE START ==="
        ),
        crontab_marker_end=raw.get(
            "crontab_marker_end", "# === IPTV SCHEDULE END ==="
        ),
    )


CONFIG = load_config()
