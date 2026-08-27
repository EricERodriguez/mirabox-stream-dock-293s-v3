"""Entrypoint: wires the device connection, the active profile, and the
page controller together, then runs the daemon's main loop. Run as
``python -m daemon`` with this package's parent directory as the working
directory (so the sibling ``profile_store`` module is importable).
"""

from __future__ import annotations

import logging
import os
import signal
import time

from profile_store import active_profile_path, load_profile

from .device import DeviceConnection
from .page_controller import PageController
from .rendering import STATE_HOME, read_cpu_percent


def main() -> int:
    STATE_HOME.mkdir(parents=True, exist_ok=True)
    os.chdir(STATE_HOME)
    logging.basicConfig(filename=STATE_HOME / "daemon.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    profile, profile_path = load_profile(active_profile_path())
    device = DeviceConnection()

    stopping = False

    def stop(*_args: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    try:
        device.init()
        cpu, snapshot = read_cpu_percent(None)
        controller = PageController(device, profile)
        controller.draw_page(cpu)

        device.set_key_callback(controller.on_key)
        logging.info("ready: %s page(s), 3 right-side displays, profile %s on %s",
                     len(profile["pages"]), profile_path, device.path)
        next_refresh = time.monotonic() + 5
        while not stopping:
            if controller.redraw_pending:
                controller.redraw_pending = False
                controller.draw_page(cpu)
            if time.monotonic() >= next_refresh:
                cpu, snapshot = read_cpu_percent(snapshot)
                controller.refresh_side_displays(cpu)
                next_refresh = time.monotonic() + 5
            time.sleep(0.2)
    finally:
        device.close()
        logging.info("stopped")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        logging.exception("fatal bridge error")
        raise
