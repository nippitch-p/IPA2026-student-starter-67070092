"""
Part 3: NETCONF Backend Adapter
"""
import ipaddress
import os
import xml.etree.ElementTree as ET
from ncclient import manager

from app.backends.planning import plan_interface as generic_plan_interface

ROUTER_USER = os.getenv("ROUTER_USER", "admin")
ROUTER_PASS = os.getenv("ROUTER_PASS", "cisco")

IETF_INTERFACES_NS = "urn:ietf:params:xml:ns:yang:ietf-interfaces"
IETF_IP_NS = "urn:ietf:params:xml:ns:yang:ietf-ip"
NETCONF_BASE_NS = "urn:ietf:params:xml:ns:netconf:base:1.0"
CISCO_NATIVE_NS = "http://cisco.com/ns/yang/Cisco-IOS-XE-native"


def get_interface_state(
    router,
    interface_name,
    netconf_get_config=None,
):
    """
    อ่านสถานะ Interface ผ่าน NETCONF Subtree Filter
    """
    filter_xml = (
        f'<interfaces xmlns="{IETF_INTERFACES_NS}">'
        f'  <interface>'
        f'    <name>{interface_name}</name>'
        f'  </interface>'
        f'</interfaces>'
    )

    try:
        if netconf_get_config is not None:
            xml_data = netconf_get_config(router, filter_xml)
        else:
            with manager.connect(
                host=router,
                port=830,
                username=ROUTER_USER,
                password=ROUTER_PASS,
                hostkey_verify=False,
                device_params={"name": "iosxe"},
                timeout=10,
            ) as m:
                res = m.get_config(source="running", filter=("subtree", filter_xml))
                xml_data = res.xml
    except (ConnectionError, Exception) as exc:
        err_msg = str(type(exc).__name__).lower() + str(exc).lower()
        if isinstance(exc, PermissionError) or "auth" in err_msg:
            return {"status": "error", "result": "authentication_failed"}
        if isinstance(exc, ConnectionError) or "timeout" in err_msg or "connect" in err_msg or "ssh" in err_msg:
            return {"status": "error", "result": "connection_failed"}
        return {"status": "error", "result": "backend_failed"}

    try:
        root = ET.fromstring(xml_data)
        iface_el = root.find(f".//{{{IETF_INTERFACES_NS}}}interface")
        if iface_el is None:
            return {"status": "ok", "result": "not_found", "interface": None}

        name = iface_el.findtext(f"{{{IETF_INTERFACES_NS}}}name")
        description = iface_el.findtext(f"{{{IETF_INTERFACES_NS}}}description")
        enabled_text = iface_el.findtext(f"{{{IETF_INTERFACES_NS}}}enabled")
        admin_state = "down" if enabled_text == "false" else "up"

        ip_el = iface_el.find(f".//{{{IETF_IP_NS}}}address/{{{IETF_IP_NS}}}ip")
        mask_el = iface_el.find(f".//{{{IETF_IP_NS}}}address/{{{IETF_IP_NS}}}netmask")

        if ip_el is not None and mask_el is not None and ip_el.text and mask_el.text:
            ip = ip_el.text.strip()
            mask = mask_el.text.strip()
            prefix = ipaddress.IPv4Network(f"0.0.0.0/{mask}").prefixlen
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
    netconf_get_config=None,
):
    """
    วางแผน Interface โดยใช้ NETCONF status
    """
    def _getter(r, iface_name):
        return get_interface_state(r, iface_name, netconf_get_config=netconf_get_config)

    return generic_plan_interface(router, desired_interface, _getter)


def apply_interface(
    router,
    desired_interface,
    netconf_edit_config=None,
):
    """
    นำ Desired State ไปตั้งค่าผ่าน NETCONF edit-config บนโมเดล Cisco Native
    """
    name = desired_interface["name"]
    loopback_num = name[len("Loopback"):]
    ip, prefix = desired_interface["ipv4"].split("/")
    netmask = str(ipaddress.IPv4Network(f"0.0.0.0/{prefix}").netmask)

    shutdown_tag = "\n            <shutdown/>" if desired_interface.get("admin_state") == "down" else ""

    config_xml = (
        f'<config xmlns="{NETCONF_BASE_NS}" xmlns:nc="{NETCONF_BASE_NS}">\n'
        f'  <native xmlns="{CISCO_NATIVE_NS}">\n'
        f'    <interface>\n'
        f'      <Loopback nc:operation="replace">\n'
        f'        <name>{loopback_num}</name>\n'
        f'        <description>{desired_interface["description"]}</description>\n'
        f'        <ip>\n'
        f'          <address>\n'
        f'            <primary>\n'
        f'              <address>{ip}</address>\n'
        f'              <mask>{netmask}</mask>\n'
        f'            </primary>\n'
        f'          </address>\n'
        f'        </ip>{shutdown_tag}\n'
        f'      </Loopback>\n'
        f'    </interface>\n'
        f'  </native>\n'
        f'</config>'
    )

    try:
        if netconf_edit_config is not None:
            netconf_edit_config(router, config_xml)
        else:
            with manager.connect(
                host=router,
                port=830,
                username=ROUTER_USER,
                password=ROUTER_PASS,
                hostkey_verify=False,
                device_params={"name": "iosxe"},
                timeout=10,
            ) as m:
                m.edit_config(target="running", config=config_xml)
        return {"status": "ok", "result": "applied"}
    except PermissionError:
        return {"status": "error", "result": "authentication_failed"}
    except ConnectionError:
        return {"status": "error", "result": "connection_failed"}
    except RuntimeError:
        return {"status": "error", "result": "backend_failed"}
    except Exception as exc:
        err_msg = str(type(exc).__name__).lower() + str(exc).lower()
        if "auth" in err_msg:
            return {"status": "error", "result": "authentication_failed"}
        if "timeout" in err_msg or "connect" in err_msg or "ssh" in err_msg:
            return {"status": "error", "result": "connection_failed"}
        return {"status": "error", "result": "backend_failed"}
