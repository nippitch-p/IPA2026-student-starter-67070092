"""
Utility script to register or update Webex Webhooks with the current Tunnel URL.
Usage:
    python scripts/register_webhook.py https://<your-tunnel-url>.trycloudflare.com
"""
import os
import sys
import requests

def get_env():
    token = os.getenv("WEBEX_BOT_TOKEN")
    if not token and os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                if line.startswith("WEBEX_BOT_TOKEN="):
                    token = line.strip().split("=", 1)[1]
    return token

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/register_webhook.py <TUNNEL_BASE_URL>")
        print("Example: python scripts/register_webhook.py https://xxx.trycloudflare.com")
        sys.exit(1)

    base_url = sys.argv[1].rstrip("/")
    target_url = f"{base_url}/webhook"
    token = get_env()

    if not token:
        print("Error: WEBEX_BOT_TOKEN is not set in environment or .env")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 1. List existing webhooks
    res = requests.get("https://webexapis.com/v1/webhooks", headers=headers)
    res.raise_for_status()
    existing = res.json().get("items", [])

    print(f"Found {len(existing)} existing webhook(s).")
    for hook in existing:
        print(f"Deleting old webhook {hook['id']} ({hook.get('name')})...")
        requests.delete(f"https://webexapis.com/v1/webhooks/{hook['id']}", headers=headers)

    # 2. Register new webhook
    payload = {
        "name": "IPA2026-Bot-Webhook",
        "targetUrl": target_url,
        "resource": "messages",
        "event": "created",
    }
    create_res = requests.post("https://webexapis.com/v1/webhooks", headers=headers, json=payload)
    create_res.raise_for_status()
    created_hook = create_res.json()

    print(f"Successfully registered Webhook!")
    print(f"  ID: {created_hook['id']}")
    print(f"  Target URL: {created_hook['targetUrl']}")
    print(f"  Status: {created_hook.get('status')}")

if __name__ == "__main__":
    main()
