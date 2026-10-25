"""
Part 2: Declarative State Planner
"""

MANAGED_FIELDS = ("ipv4", "description", "admin_state")


def build_plan(desired_interface, current_interface):
    """
    เปรียบเทียบ Desired State กับ Normalized Current State
    และสร้างผลลัพธ์การวางแผนแบบ Deterministic & Idempotent
    """
    # กรณีที่ 1: บนเราเตอร์ยังไม่มี Interface นี้ (current_interface เป็น None)
    if current_interface is None:
        changes = {}
        for field in MANAGED_FIELDS:
            if field in desired_interface:
                changes[field] = {"to": desired_interface[field]}
        return {
            "status": "ok",
            "result": "planned",
            "operation": "create",
            "changes": changes,
        }

    # กรณีที่ 2 & 3: มี Interface อยู่แล้ว ให้ตรวจเช็คค่าที่ต่างกัน
    changes = {}
    for field in MANAGED_FIELDS:
        cur_val = current_interface.get(field)
        des_val = desired_interface.get(field)
        if cur_val != des_val:
            changes[field] = {
                "from": cur_val,
                "to": des_val,
            }

    if not changes:
        return {
            "status": "ok",
            "result": "planned",
            "operation": "no_change",
            "changes": {},
        }

    return {
        "status": "ok",
        "result": "planned",
        "operation": "update",
        "changes": changes,
    }
