"""
Part 3: Shared Planning Wrapper for Backends
"""
from app.planner import build_plan


def plan_interface(
    router,
    desired_interface,
    get_interface_state,
):
    """
    ดึงสถานะปัจจุบันผ่าน get_interface_state แล้วส่งต่อให้ build_plan
    """
    status_response = get_interface_state(router, desired_interface["name"])

    # หากเกิดข้อผิดพลาดในการเชื่อมต่อหรือ Authenticate ให้ส่ง Error ต่อทันที
    if status_response.get("status") == "error":
        return status_response

    result_type = status_response.get("result")
    if result_type == "found":
        current_interface = status_response.get("interface")
    elif result_type == "not_found":
        current_interface = None
    else:
        return status_response

    return build_plan(desired_interface, current_interface)
