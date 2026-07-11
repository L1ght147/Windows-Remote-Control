from win_tg_pc_controller.status import format_status


def test_format_status_supports_no_battery() -> None:
    text = format_status(
        {
            "online": "yes",
            "cpu": "10%",
            "ram": "1.0 GB / 8.0 GB",
            "disk_c": "20.0 GB / 100.0 GB",
            "uptime": "1h 2m",
            "battery": "нет",
            "lan_ip": "192.168.1.10",
        }
    )

    assert "Battery: нет" in text
    assert "LAN IP: 192.168.1.10" in text
