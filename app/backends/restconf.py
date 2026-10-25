"""
Part 3: RESTCONF Backend Adapter
"""
import ipaddress
import os
import requests

from app.backends.planning import plan_interface as generic_plan_interface

ROUTER_USER = os.getenv("ROUTER_USER", "admin")
ROUTER_PASS = os.getenv("ROUTER_PASS", "cisco")


def get_interface_state(
    router,
    interface_name,
    http_get=None,
):
    """
    อ่านสถานะ Interface โดยใช้ RESTCONF (IETF Interfaces Model)
    """
    url = f"https://{router}/restconf/data/ietf-interfaces:interfaces/interface={interface_name}"

    try:
        if http_get is not None:
            response = http_get(url)
        else:
            response = requests.get(
                url,
                auth=(ROUTER_USER, ROUTER_PASS),
                headers={"Accept": "application/yang-data+json"},
                verify=False,
                timeout=10,
            )
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, ConnectionError):
        return {"status": "error", "result": "connection_failed"}
    except PermissionError:
        return {"status": "error", "result": "authentication_failed"}
    except Exception:
        return {"status": "error", "result": "backend_failed"}

    status_code = getattr(response, "status_code", None)
    if status_code in (401, 403):
        return {"status": "error", "result": "authentication_failed"}
    if status_code == 404:
        return {"status": "ok", "result": "not_found", "interface": None}
    if status_code != 200:
        return {"status": "error", "result": "backend_failed"}

    try:
        data = response.json()
        iface = data.get("ietf-interfaces:interface") or data.get("interface")
        if not iface:
            return {"status": "ok", "result": "not_found", "interface": None}

        name = iface.get("name", interface_name)
        description = iface.get("description")
        enabled = iface.get("enabled", True)
        admin_state = "up" if enabled else "down"

        ipv4_info = iface.get("ietf-ip:ipv4", {}).get("address", [])
        if ipv4_info:
            first_addr = ipv4_info[0]
            ip = first_addr.get("ip")
            netmask = first_addr.get("netmask")
            prefix = ipaddress.IPv4Network(f"0.0.0.0/{netmask}").prefixlen
            ipv4 = f"{ip}/{prefix}"
        else:
            ipv4 = None

        return {
            "status": "ok",
            "result": "found",
            "interface": {
                "name": name,
                "ipv4": ipv4,
                "description": description,
                "admin_state": admin_state,
            },
        }
    except Exception:
        return {"status": "error", "result": "backend_failed"}


def plan_interface(
    router,
    desired_interface,
    http_get=None,
):
    """
    วางแผน Interface โดยใช้ RESTCONF status
    """
    def _getter(r, iface_name):
        return get_interface_state(r, iface_name, http_get=http_get)

    return generic_plan_interface(router, desired_interface, _getter)


def apply_interface(
    router,
    desired_interface,
    http_put=None,
):
    """
    นำ Desired State ไปตั้งค่าบนเราเตอร์ผ่าน HTTP PUT โมเดล Cisco Native
    """
    name = desired_interface["name"]
    loopback_num = int(name[len("Loopback"):])
    url = f"https://{router}/restconf/data/Cisco-IOS-XE-native:native/interface/Loopback={loopback_num}"

    interface_ipv4 = ipaddress.IPv4Interface(desired_interface["ipv4"])
    payload = {
        "Cisco-IOS-XE-native:Loopback": {
            "name": loopback_num,
            "description": desired_interface["description"],
            "ip": {
                "address": {
                    "primary": {
                        "address": str(interface_ipv4.ip),
                        "mask": str(interface_ipv4.network.netmask),
                    }
                }
            },
        }
    }

    if desired_interface.get("admin_state") == "down":
        payload["Cisco-IOS-XE-native:Loopback"]["shutdown"] = [None]

    try:
        if http_put is not None:
            response = http_put(url, json=payload)
        else:
            response = requests.put(
                url,
                auth=(ROUTER_USER, ROUTER_PASS),
                headers={
                    "Content-Type": "application/yang-data+json",
                    "Accept": "application/yang-data+json",
                },
                json=payload,
                verify=False,
                timeout=10,
            )
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, ConnectionError):
        return {"status": "error", "result": "connection_failed"}
    except PermissionError:
        return {"status": "error", "result": "authentication_failed"}
    except Exception:
        return {"status": "error", "result": "backend_failed"}

    status_code = getattr(response, "status_code", None)
    if status_code in (401, 403):
        return {"status": "error", "result": "authentication_failed"}
    if status_code in (200, 201, 204):
        return {"status": "ok", "result": "applied"}

    return {"status": "error", "result": "backend_failed"}
