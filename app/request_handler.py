"""
Part 1: Webex Envelope Validation
"""
from app.core import process_request_file


def validate_webex_envelope(
    mentioned_people,
    attachment_path,
    bot_person_id,
):
    """
    ตรวจสอบความถูกต้องของ Mention และไฟล์แนบ
    คืนค่า Error Dict หากไม่ถูกต้อง หรือคืน None หากผ่าน
    """
    if not isinstance(bot_person_id, str) or not bot_person_id:
        return {"status": "error", "result": "missing_bot_mention"}

    if not isinstance(mentioned_people, list) or bot_person_id not in mentioned_people:
        return {"status": "error", "result": "missing_bot_mention"}

    if attachment_path is None:
        return {"status": "error", "result": "no_yaml"}

    return None


def handle_webex_request(
    mentioned_people,
    attachment_path,
    bot_person_id,
):
    """
    ตรวจสอบ Envelope ก่อน หากผ่านจึงตรวจสอบเนื้อหาไฟล์ YAML
    """
    envelope_error = validate_webex_envelope(
        mentioned_people, attachment_path, bot_person_id
    )
    if envelope_error is not None:
        return envelope_error

    return process_request_file(attachment_path)