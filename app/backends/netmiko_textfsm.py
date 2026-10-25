"""
Part 3: Netmiko + TextFSM Backend Adapter
"""
import os
from netmiko import ConnectHandler

ROUTER_USER = os.getenv("ROUTER_USER", "admin")
ROUTER_PASS = os.getenv("ROUTER_PASS", "cisco")


def get_interface_state(
    router,
    interface_name,
    netmiko_get=None,
):
    """
    อ่านสถานะ Interface โดยใช้ Netmiko และ TextFSM Templates
    """
    try:
        if netmiko_get is not None:
            ip_info, descriptions = netmiko_get(router, interface_name)
        else:
            device = {
                "device_type": "cisco_ios",
                "host": router,
                "username": ROUTER_USER,
                "password": ROUTER_PASS,
                "fast_cli": False,
                "timeout": 10,
            }
            with ConnectHandler(**device) as net_connect:
                ip_info = net_connect.send_command(
                    f"show ip interface {interface_name}",
                    use_textfsm=True,
                )
                descriptions = net_connect.send_command(
                    "show interfaces description",
                    use_textfsm=True,
                )
    except PermissionError:
        return {"status": "error", "result": "authentication_failed"}
    except ConnectionError:
        return {"status": "error", "result": "connection_failed"}
    except RuntimeError:
        return {"status": "error", "result": "backend_failed"}
    except Exception as exc:
        err = str(type(exc).__name__).lower() + str(exc).lower()
        if "auth" in err:
            return {"status": "error", "result": "authentication_failed"}
        if "timeout" in err or "connect" in err:
            return {"status": "error", "result": "connection_failed"}
        return {"status": "error", "result": "backend_failed"}

    # ถ้าไม่พบข้อมูล ip_info แสดงว่า interface ไม่มีอยู่
    if not ip_info or not isinstance(ip_info, list):
        return {"status": "ok", "result": "not_found", "interface": None}

    info = ip_info[0]
    link_status = str(info.get("link_status", "")).lower()
    admin_state = "down" if "admin" in link_status else "up"

    ip_addresses = info.get("ip_address", [])
    prefix_lengths = info.get("prefix_length", [])
    if ip_addresses and prefix_lengths:
        ipv4 = f"{ip_addresses[0]}/{prefix_lengths[0]}"
    else:
        ipv4 = None

    # ดึง Description โดยจับคู่ทั้งชื่อเต็มและชื่อย่อ เช่น Loopback123 <-> Lo123
    target_full = interface_name.lower()
    target_abbr = (
        "lo" + interface_name[len("Loopback"):]
        if interface_name.lower().startswith("loopback")
        else target_full
    ).lower()

    description = None
    if isinstance(descriptions, list):
        for item in descriptions:
            port = str(item.get("port", "")).lower()
            if port in (target_full, target_abbr):
                description = item.get("description")
                break

    return {
        "status": "ok",
        "result": "found",
        "interface": {
            "name": interface_name,
            "ipv4": ipv4,
            "description": description,
            "admin_state": admin_state,
        },
    }


def delete_interface(
    router,
    interface_name,
    netmiko_delete=None,
):
    """
    ลบ Loopback Interface โดยใช้คำสั่ง Cisco IOS 'no interface'
    """
    try:
        if netmiko_delete is not None:
            del_result = netmiko_delete(router, interface_name)
            if del_result == "deleted":
                return {"status": "ok", "result": "deleted"}
            if del_result == "not_found":
                return {"status": "ok", "result": "not_found", "interface": None}
            return {"status": "error", "result": "backend_failed"}

        # ในการรันจริง: อ่านสถานะก่อนลบ
        state = get_interface_state(router, interface_name)
        if state.get("status") == "error":
            return state
        if state.get("result") == "not_found":
            return {"status": "ok", "result": "not_found", "interface": None}

        device = {
            "device_type": "cisco_ios",
            "host": router,
            "username": ROUTER_USER,
            "password": ROUTER_PASS,
            "fast_cli": False,
            "timeout": 10,
        }
        with ConnectHandler(**device) as net_connect:
            net_connect.send_config_set([f"no interface {interface_name}"])

        # ตรวจสอบซ้ำว่าถูกลบเรียบร้อยแล้ว
        verify_state = get_interface_state(router, interface_name)
        if verify_state.get("result") == "not_found":
            return {"status": "ok", "result": "deleted"}

        return {"status": "error", "result": "backend_failed"}
    except PermissionError:
        return {"status": "error", "result": "authentication_failed"}
    except ConnectionError:
        return {"status": "error", "result": "connection_failed"}
    except RuntimeError:
        return {"status": "error", "result": "backend_failed"}
    except Exception as exc:
        err = str(type(exc).__name__).lower() + str(exc).lower()
        if "auth" in err:
            return {"status": "error", "result": "authentication_failed"}
        if "timeout" in err or "connect" in err:
            return {"status": "error", "result": "connection_failed"}
        return {"status": "error", "result": "backend_failed"}
