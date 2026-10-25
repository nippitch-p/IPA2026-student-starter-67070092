"""
Part 4: Webhook Server & Event Handler
"""
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from app.integration import process_request
from app.webex_client import WebexClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebexEventHandler:
    def __init__(self, client, bot_person_id, processor=None):
        self.client = client
        self.bot_person_id = bot_person_id
        self.processor = processor or process_request

    def handle_event(self, event):
        """
        ประมวลผล Webhook Event จาก Webex
        """
        if not isinstance(event, dict):
            return None

        # 1. กรองเฉพาะ messages created event
        if event.get("resource") != "messages" or event.get("event") != "created":
            return None

        data = event.get("data")
        if not isinstance(data, dict):
            return None

        msg_id = data.get("id")
        if not msg_id:
            return None

        # 2. ป้องกันข้อความจากตัวบอตเองตั้งแต่ event เพื่อกัน Reply Loop
        event_person_id = data.get("personId")
        if event_person_id and event_person_id == self.bot_person_id:
            return None

        # 3. ดึงข้อความจริงจาก Webex API
        try:
            message = self.client.get_message(msg_id)
        except Exception as exc:
            logger.error("Failed to fetch message %s: %s", msg_id, exc)
            return None

        if not isinstance(message, dict):
            return None

        # ตรวจสอบคนส่งข้อความซ้ำอีกครั้ง
        if message.get("personId") == self.bot_person_id:
            return None

        room_id = message.get("roomId")
        files = message.get("files") or []
        mentioned_people = message.get("mentionedPeople") or []

        # 4. กรณีมีไฟล์แนบมากกว่า 1 ไฟล์
        if len(files) > 1:
            result = {"status": "error", "result": "multiple_attachments"}
            if room_id:
                self.client.send_message(room_id, json.dumps(result))
            return result

        # 5. กรณีไม่ได้แนบไฟล์
        if len(files) == 0:
            result = self.processor(mentioned_people, None, self.bot_person_id)
            if room_id:
                self.client.send_message(room_id, json.dumps(result))
            return result

        # 6. กรณีแนบ 1 ไฟล์: ดาวน์โหลดลงไฟล์ชั่วคราวและลบทิ้งหลังประมวลผลเสมอ
        with TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / "request.yaml"
            try:
                content = self.client.download_file(files[0])
                temp_path.write_bytes(content)
                result = self.processor(mentioned_people, temp_path, self.bot_person_id)
            except Exception as exc:
                logger.error("Error processing file attachment: %s", exc)
                result = {"status": "error", "result": "invalid_yaml"}

        if room_id:
            self.client.send_message(room_id, json.dumps(result))

        return result


def make_http_handler(submit_event):
    """
    สร้าง HTTP Handler สำหรับรับคำขอ GET /health และ POST /webhook
    """
    class WebhookHTTPHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                response_data = json.dumps({"status": "ok", "result": "healthy"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response_data)))
                self.end_headers()
                self.wfile.write(response_data)
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            if self.path == "/webhook":
                content_length_header = self.headers.get("Content-Length")
                if not content_length_header or not content_length_header.isdigit():
                    self._send_error_response(400, "invalid_event")
                    return

                length = int(content_length_header)
                if length < 1 or length > 1_000_000:
                    self._send_error_response(400, "invalid_event")
                    return

                body = self.rfile.read(length)
                try:
                    event = json.loads(body)
                    if not isinstance(event, dict):
                        raise ValueError()
                except Exception:
                    self._send_error_response(400, "invalid_event")
                    return

                # ส่ง event เข้า Background Task
                submit_event(event)

                # ตอบรับ HTTP 200 ทันที
                response_data = json.dumps({"status": "ok", "result": "accepted"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response_data)))
                self.end_headers()
                self.wfile.write(response_data)
            else:
                self.send_response(404)
                self.end_headers()

        def _send_error_response(self, code, result_msg):
            response_data = json.dumps({"status": "error", "result": result_msg}).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_data)))
            self.end_headers()
            self.wfile.write(response_data)

        def log_message(self, format, *args):
            # ลดทอน Log สแปมบนหน้าจอ
            return

    return WebhookHTTPHandler


def main():
    host = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    port = int(os.getenv("WEBHOOK_PORT", 8000))

    client = WebexClient()
    try:
        me_info = client.get_me()
        bot_person_id = me_info.get("id")
        logger.info("Bot authenticated as: %s (ID: %s)", me_info.get("displayName"), bot_person_id)
    except Exception as exc:
        logger.warning("Could not resolve bot identity at startup: %s", exc)
        bot_person_id = ""

    # คิวประมวลผลคำสั่งแบบตามลำดับ (Sequential) เพื่อป้องกันคอนฟิกเราเตอร์ชนกัน
    executor = ThreadPoolExecutor(max_workers=1)
    event_handler = WebexEventHandler(client, bot_person_id, process_request)

    def submit_event(evt):
        executor.submit(event_handler.handle_event, evt)

    server = ThreadingHTTPServer((host, port), make_http_handler(submit_event))
    logger.info("Webhook server listening on http://%s:%d", host, port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        executor.shutdown(wait=True)


if __name__ == "__main__":
    main()
