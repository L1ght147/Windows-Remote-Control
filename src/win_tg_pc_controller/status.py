from __future__ import annotations

import datetime as dt
import socket

import psutil

from .windows_session import collect_windows_session_info, format_windows_session


def _format_bytes(num_bytes: int) -> str:
    gib = num_bytes / (1024**3)
    return f"{gib:.1f} GB"


def _format_uptime(boot_timestamp: float) -> str:
    delta = dt.datetime.now() - dt.datetime.fromtimestamp(boot_timestamp)
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    return f"{hours}h {minutes}m"


def get_lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        pass

    try:
        hostname = socket.gethostname()
        for address in socket.gethostbyname_ex(hostname)[2]:
            if not address.startswith("127."):
                return address
    except OSError:
        pass
    return "unknown"


def collect_status() -> dict[str, str]:
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    battery = psutil.sensors_battery()

    return {
        "online": "yes",
        "cpu": f"{psutil.cpu_percent(interval=0.5):.0f}%",
        "ram": f"{_format_bytes(memory.used)} / {_format_bytes(memory.total)}",
        "disk_c": f"{_format_bytes(disk.used)} / {_format_bytes(disk.total)}",
        "uptime": _format_uptime(psutil.boot_time()),
        "battery": "нет" if battery is None else f"{battery.percent:.0f}%",
        "lan_ip": get_lan_ip(),
        "windows_session": format_windows_session(collect_windows_session_info()),
    }


def format_status(status: dict[str, str]) -> str:
    return "\n".join(
        [
            "PC status",
            f"Online: {status['online']}",
            f"CPU: {status['cpu']}",
            f"RAM: {status['ram']}",
            f"Disk C: {status['disk_c']}",
            f"Uptime: {status['uptime']}",
            f"Battery: {status['battery']}",
            f"LAN IP: {status['lan_ip']}",
            "",
            status.get("windows_session", "Windows session: unknown"),
        ]
    )
