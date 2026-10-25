"""
Part 1: YAML Request Validation Core
"""
import yaml

ALLOWED_ROUTERS = {
    "10.0.29.101",
    "10.0.29.102",
    "10.0.29.103",
    "10.0.29.104",
    "10.0.29.105",
}

ALLOWED_METHODS = {
    "restconf",
    "netconf",
    "ansible",
    "netmiko-textfsm",
}

METHOD_ACTIONS = {
    "restconf": {"status", "plan", "apply"},
    "netconf": {"status", "plan", "apply"},
    "ansible": {"apply"},
    "netmiko-textfsm": {"status", "delete"},
}


def validate_request(data):
    """
    ตรวจสอบความถูกต้องของข้อมูล YAML Request ตาม Validation Precedence
    คืนค่าเป็น Dictionary ตอบกลับตาม response-spec-v1.md
    """
    # 1. ตรวจสอบ Root Type ว่าต้องเป็น Mapping / Dictionary
    if not isinstance(data, dict):
        return {"status": "error", "result": "invalid_yaml"}

    # 2. ตรวจสอบ Version: ต้องเป็น YAML Integer ค่า 1 เท่านั้น
    # ข้อควรระวัง: ใน Python True เป็น subclass ของ int ดังนั้นต้องใช้ type() is int
    version = data.get("version")
    if "version" not in data or type(version) is not int or version != 1:
        return {"status": "error", "result": "invalid_version"}

    # 3. ตรวจสอบ Router: ต้องมีอยู่และเป็นหนึ่งในไอพีที่อนุญาต
    router = data.get("router")
    if "router" not in data or router is None or router == "":
        return {"status": "error", "result": "missing_router"}
    if router not in ALLOWED_ROUTERS:
        return {"status": "error", "result": "invalid_router"}

    # 4. ตรวจสอบ Method: ต้องมีอยู่และเป็นค่าที่ระบบรู้จัก
    method = data.get("method")
    if "method" not in data or method is None or method == "":
        return {"status": "error", "result": "missing_method"}
    if method not in ALLOWED_METHODS:
        return {"status": "error", "result": "invalid_method"}

    # 5. ตรวจสอบ Action: ต้องมีอยู่และสอดคล้องกับ Capability Matrix ของ Method นั้น
    action = data.get("action")
    if "action" not in data or action is None or action == "":
        return {"status": "error", "result": "missing_action"}
    if action not in METHOD_ACTIONS.get(method, set()):
        return {"status": "error", "result": "invalid_action"}

    # 6. ตรวจสอบ desired และโครงสร้าง desired.interface.name
    desired = data.get("desired")
    if "desired" not in data or not isinstance(desired, dict):
        return {"status": "error", "result": "missing_desired"}

    interface = desired.get("interface")
    if "interface" not in desired or not isinstance(interface, dict):
        return {"status": "error", "result": "missing_interface"}

    if "name" not in interface or not interface.get("name"):
        return {"status": "error", "result": "missing_interface_name"}

    # 7. ตรวจสอบฟิลด์เฉพาะสำหรับ Action 'plan' และ 'apply' เท่านั้น
    if action in ("plan", "apply"):
        if "ipv4" not in interface or not interface.get("ipv4"):
            return {"status": "error", "result": "missing_ipv4"}

        if "description" not in interface or interface.get("description") is None:
            return {"status": "error", "result": "missing_description"}

        admin_state = interface.get("admin_state")
        if "admin_state" not in interface or admin_state is None or admin_state == "":
            return {"status": "error", "result": "missing_admin_state"}
        if admin_state not in ("up", "down"):
            return {"status": "error", "result": "invalid_admin_state"}

    return {"status": "ok", "result": "accepted"}


def process_request_file(path):
    """
    อ่านไฟล์ YAML และส่งเข้ากระบวนการตรวจสอบ
    """
    if path is None:
        return {"status": "error", "result": "no_yaml"}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return {"status": "error", "result": "invalid_yaml"}

    if data is None or not isinstance(data, dict):
        return {"status": "error", "result": "invalid_yaml"}

    return validate_request(data)