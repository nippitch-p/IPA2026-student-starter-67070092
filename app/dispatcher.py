"""
Part 4: Request Dispatcher
"""
from app.backends import (
    ansible,
    netconf,
    netmiko_textfsm,
    restconf,
)


def dispatch_request(data):
    """
    ส่งต่อ Request ที่ผ่านการ Validate แล้วไปยัง Backend ที่ถูกต้อง
    """
    method = data["method"]
    action = data["action"]
    router = data["router"]
    interface_dict = data["desired"]["interface"]

    # สำหรับ status และ delete ส่งเพียง (router, interface_name)
    if action in ("status", "delete"):
        target_arg = interface_dict["name"]
    else:
        # สำหรับ plan และ apply ส่ง (router, desired_interface_dict)
        target_arg = interface_dict

    dispatch_table = {
        ("restconf", "status"): restconf.get_interface_state,
        ("restconf", "plan"): restconf.plan_interface,
        ("restconf", "apply"): restconf.apply_interface,
        ("netconf", "status"): netconf.get_interface_state,
        ("netconf", "plan"): netconf.plan_interface,
        ("netconf", "apply"): netconf.apply_interface,
        ("ansible", "apply"): ansible.apply_interface,
        ("netmiko-textfsm", "status"): netmiko_textfsm.get_interface_state,
        ("netmiko-textfsm", "delete"): netmiko_textfsm.delete_interface,
    }

    handler = dispatch_table.get((method, action))
    if handler is None:
        return {"status": "error", "result": "invalid_action"}

    return handler(router, target_arg)
