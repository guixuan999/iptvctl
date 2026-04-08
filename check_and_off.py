import subprocess
import time
from pathlib import Path

from settings import CONFIG


def manual_timer_running():
    state_file = Path(CONFIG.timer_state_file)
    if not state_file.exists():
        return False

    try:
        end_time = float(state_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False

    return end_time > time.time()


def main():
    if manual_timer_running():
        subprocess.run(
            [CONFIG.logger_command, "IPTV SKIP: manual timer is running"],
            check=False,
        )
        return 0

    result = subprocess.run(CONFIG.iptv_commands["off"], check=False)
    subprocess.run(
        [CONFIG.logger_command, "IPTV BLOCKED: by schedule"],
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
