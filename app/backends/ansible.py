"""
Part 3: Ansible Backend Adapter
"""
import ipaddress
import os
import subprocess


def apply_interface(
    router,
    desired_interface,
    run_playbook=None,
):
    """
    ตั้งค่า Interface โดยใช้ Ansible Playbook
    """
    ip, prefix = desired_interface["ipv4"].split("/")
    netmask = str(ipaddress.IPv4Network(f"0.0.0.0/{prefix}").netmask)

    variables = {
        "router": router,
        "interface_name": desired_interface["name"],
        "description": desired_interface["description"],
        "ipv4_address": ip,
        "netmask": netmask,
        "shutdown": desired_interface.get("admin_state") == "down",
    }

    try:
        if run_playbook is not None:
            run_playbook(variables)
        else:
            playbook_path = os.path.join("ansible", "apply_interface.yml")
            inventory_path = os.path.join("ansible", "inventory.ini")
            extra_vars = " ".join([f"{k}='{v}'" for k, v in variables.items()])
            cmd = [
                "ansible-playbook",
                "-i",
                inventory_path,
                playbook_path,
                "-e",
                extra_vars,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if res.returncode != 0:
                output = res.stderr + res.stdout
                if "Authentication failure" in output or "Permission denied" in output:
                    return {"status": "error", "result": "authentication_failed"}
                if "UNREACHABLE" in output or "Failed to connect" in output:
                    return {"status": "error", "result": "connection_failed"}
                return {"status": "error", "result": "backend_failed"}

        return {"status": "ok", "result": "applied"}
    except PermissionError:
        return {"status": "error", "result": "authentication_failed"}
    except ConnectionError:
        return {"status": "error", "result": "connection_failed"}
    except RuntimeError:
        return {"status": "error", "result": "backend_failed"}
    except Exception:
        return {"status": "error", "result": "backend_failed"}
