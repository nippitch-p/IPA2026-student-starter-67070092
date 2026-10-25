"""
Part 4: End-to-End Integration Processor
"""
import yaml
from app.core import validate_request
from app.dispatcher import dispatch_request
from app.request_handler import validate_webex_envelope


def process_request(mentioned_people, attachment_path, bot_person_id):
    """
    ตรวจสอบ Envelope -> อ่านไฟล์ YAML -> ตรวจสอบคำขอ -> ส่ง Dispatch ไปยัง Backend
    """
    envelope_error = validate_webex_envelope(
        mentioned_people, attachment_path, bot_person_id
    )
    if envelope_error is not None:
        return envelope_error

    try:
        with open(attachment_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return {"status": "error", "result": "invalid_yaml"}

    if data is None or not isinstance(data, dict):
        return {"status": "error", "result": "invalid_yaml"}

    val_res = validate_request(data)
    if val_res.get("status") == "error":
        return val_res

    return dispatch_request(data)
