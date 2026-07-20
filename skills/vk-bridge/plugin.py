from __future__ import annotations

import os
import re
from typing import Any, Dict

import httpx
from starlette.responses import JSONResponse

from .lib.vk_client import VkClient
from .lib.vk_state import (
    _VK_COMMAND_MODE_FULL as COMMAND_MODE_FULL,
    _VK_COMMAND_MODE_SAFE as COMMAND_MODE_SAFE,
    _VK_COMMAND_MODE_STRICT as COMMAND_MODE_STRICT,
    _VALID_COMMAND_MODES,
    _host_headers,
    _load_offset,
    _load_settings,
    _save_offset,
    _save_settings_dict,
    _translate_command,
)

_SLASH_COMMAND_RE = re.compile(r"^\s*/[A-Za-z]")


def _setting_int(settings: Dict[str, Any], key: str, default: int, *, minimum: int = 1, maximum: int = 100) -> int:
    try:
        value = int(settings.get(key) or default)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _data_dir(api) -> str:
    base = os.path.join(str(api.skills_dir or "."), "vk-bridge")
    os.makedirs(base, exist_ok=True)
    return base


def _inject(api, payload: Dict[str, Any]) -> None:
    settings = _load_settings(api)
    pinned_chat = str(settings.get("VK_PEER_ID") or os.environ.get("VK_PEER_ID") or "").strip()
    if not pinned_chat:
        api.log("warning", "Host inject refused: VK_PEER_ID is not configured or bound.")
        return
    port = os.environ.get("OUROBOROS_HOST_SERVICE_PORT", "8767")
    try:
        r = httpx.post(
            f"http://127.0.0.1:{port}/chat/inject",
            headers=_host_headers(api),
            json=payload,
            timeout=60,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"Host inject returned HTTP {r.status_code}")
    except Exception as exc:
        api.log("error", f"VK inject failed: {exc}")


def _make_poller(api):
    def poller():
        protected = api.get_settings(["VK_GROUP_TOKEN"])
        local = _load_settings(api)
        token = (protected.get("VK_GROUP_TOKEN") or "").strip()
        group_id_str = (local.get("VK_GROUP_ID") or os.environ.get("VK_GROUP_ID") or "").strip()
        if not token or not group_id_str:
            api.log("warning", "VK bridge not configured: missing VK_GROUP_TOKEN or VK_GROUP_ID")
            return
        try:
            group_id = int(group_id_str)
        except ValueError:
            api.log("error", f"VK_GROUP_ID must be a number, got: {group_id_str}")
            return

        command_mode = local.get("VK_COMMAND_MODE", COMMAND_MODE_FULL)
        if command_mode not in _VALID_COMMAND_MODES:
            command_mode = COMMAND_MODE_FULL

        client = VkClient(token, group_id)
        try:
            if not client.connect():
                api.log("error", "VK connection failed")
                return
            api.log("info", "VK bridge connected, starting poller")
        except RuntimeError as exc:
            api.log("error", f"VK bridge auth failed: {exc}")
            return

        for event in client.listen():
            try:
                event_type = client.event_type(event)
                if event_type != "message_new":
                    continue

                raw = getattr(event, "raw", None) or getattr(event, "object", {})
                msg = raw.get("message") if isinstance(raw, dict) else {}
                if not msg:
                    continue

                peer_id = msg.get("peer_id", 0)
                from_id = msg.get("from_id", 0)
                text = (msg.get("text") or "").strip()

                if not text and not msg.get("attachments"):
                    continue

                pinned = local.get("VK_PEER_ID", "")
                if not pinned:
                    api.log("info", f"Binding VK peer {peer_id} as the owner chat")
                    local["VK_PEER_ID"] = str(peer_id)
                    _save_settings_dict(api, local)
                elif str(peer_id) != pinned:
                    api.log("info", f"Ignoring message from non-owner peer {peer_id}")
                    continue

                safe_text = _translate_command(text, command_mode)
                if safe_text is None:
                    client.send_message(peer_id, "Slash commands are blocked in current mode.")
                    continue

                sender_info = client.get_user_info(from_id)
                sender_name = sender_info.get("full_name", str(from_id))
                sender_label = f"VK ({sender_name})"

                image_b64 = ""
                image_mime = ""
                photo_info = client.extract_photo_info(msg)
                if photo_info:
                    ow_id, it_id = photo_info
                    image_b64, image_mime = client.download_photo(ow_id, it_id)

                if not safe_text and not image_b64:
                    client.send_message(peer_id, "Supported input: text and photos.")
                    continue

                client.send_typing(peer_id)

                _inject(api, {
                    "text": safe_text,
                    "chat_id": peer_id,
                    "user_id": from_id,
                    "source": "vk-bridge",
                    "sender_label": sender_label,
                    "transport": {
                        "kind": "vk",
                        "conversation_id": str(peer_id),
                        "sender_label": sender_label,
                    },
                    "image_base64": image_b64,
                    "image_mime": image_mime,
                })
            except Exception as exc:
                api.log("warning", f"VK poller error: {exc}")

    return poller


def _make_outbound(api):
    def handle(event: Dict[str, Any]) -> None:
        try:
            local = _load_settings(api)
            pinned = local.get("VK_PEER_ID", "")
            if not pinned:
                return
            peer_id = int(pinned)
            text = event.get("text", "")
            if not text:
                return
            protected = api.get_settings(["VK_GROUP_TOKEN"])
            token = (protected.get("VK_GROUP_TOKEN") or "").strip()
            group_id_str = (local.get("VK_GROUP_ID") or "").strip()
            if not token or not group_id_str:
                return

            client = VkClient(token, int(group_id_str))
            client.connect()
            client.send_typing(peer_id)

            photo_b64 = event.get("image_base64", "")
            photo_mime = event.get("image_mime", "")
            attachment = None
            if photo_b64 and photo_mime:
                import base64
                img_bytes = base64.b64decode(photo_b64)
                attachment = client.upload_photo(peer_id, img_bytes, photo_mime)

            client.send_message(peer_id, text, attachment=attachment)
        except Exception as exc:
            api.log("error", f"VK outbound error: {exc}")

    return handle


def _make_photo(api):
    def handle(event: Dict[str, Any]) -> None:
        try:
            local = _load_settings(api)
            pinned = local.get("VK_PEER_ID", "")
            if not pinned:
                return
            peer_id = int(pinned)
            photo_b64 = event.get("image_base64", "")
            photo_mime = event.get("image_mime", "")
            text = event.get("text", "")
            if not photo_b64 and not text:
                return
            protected = api.get_settings(["VK_GROUP_TOKEN"])
            token = (protected.get("VK_GROUP_TOKEN") or "").strip()
            group_id_str = (local.get("VK_GROUP_ID") or "").strip()
            if not token or not group_id_str:
                return

            client = VkClient(token, int(group_id_str))
            client.connect()
            attachment = None
            if photo_b64 and photo_mime:
                import base64
                img_bytes = base64.b64decode(photo_b64)
                attachment = client.upload_photo(peer_id, img_bytes, photo_mime)
            client.send_message(peer_id, text, attachment=attachment)
        except Exception as exc:
            api.log("error", f"VK photo outbound error: {exc}")

    return handle


def _make_document(api):
    def handle(event: Dict[str, Any]) -> None:
        try:
            local = _load_settings(api)
            pinned = local.get("VK_PEER_ID", "")
            if not pinned:
                return
            peer_id = int(pinned)
            doc_b64 = event.get("document_base64", "")
            doc_name = event.get("document_name", "file")
            if not doc_b64:
                return
            protected = api.get_settings(["VK_GROUP_TOKEN"])
            token = (protected.get("VK_GROUP_TOKEN") or "").strip()
            group_id_str = (local.get("VK_GROUP_ID") or "").strip()
            if not token or not group_id_str:
                return

            client = VkClient(token, int(group_id_str))
            client.connect()
            client.send_message(peer_id, f"[Document: {doc_name}]")
        except Exception as exc:
            api.log("error", f"VK document outbound error: {exc}")

    return handle


def _make_typing(api):
    def handle(event: Dict[str, Any]) -> None:
        try:
            local = _load_settings(api)
            pinned = local.get("VK_PEER_ID", "")
            if not pinned:
                return
            peer_id = int(pinned)
            protected = api.get_settings(["VK_GROUP_TOKEN"])
            token = (protected.get("VK_GROUP_TOKEN") or "").strip()
            group_id_str = (local.get("VK_GROUP_ID") or "").strip()
            if not token or not group_id_str:
                return
            client = VkClient(token, int(group_id_str))
            client.connect()
            client.send_typing(peer_id)
        except Exception:
            pass

    return handle


def _make_settings_save(api):
    def handle(request):
        try:
            body = request.json()
        except Exception:
            return JSONResponse({"error": "invalid JSON"}, status_code=400)

        local = _load_settings(api)

        if "VK_GROUP_ID" in body:
            local["VK_GROUP_ID"] = str(body["VK_GROUP_ID"]).strip()
        if "VK_COMMAND_MODE" in body:
            mode = str(body["VK_COMMAND_MODE"]).strip()
            if mode in _VALID_COMMAND_MODES:
                local["VK_COMMAND_MODE"] = mode
        if "VK_PEER_ID" in body:
            local["VK_PEER_ID"] = str(body["VK_PEER_ID"]).strip()

        _save_settings_dict(api, local)
        return JSONResponse({"ok": True})

    return handle


def register(api):
    api.register_supervised_task("vk_poller", _make_poller(api), restart_policy="on_failure", max_restarts=10)
    api.subscribe_event("chat.outbound", _make_outbound(api))
    api.subscribe_event("chat.typing", _make_typing(api))
    api.subscribe_event("chat.photo", _make_photo(api))
    try:
        api.subscribe_event("chat.document", _make_document(api))
    except Exception as exc:
        api.log("warning", f"Could not subscribe to chat.document: {exc}")
    api.register_route("vk/settings/save", handler=_make_settings_save(api), methods=("POST",))
    api.register_settings_section(
        "vk",
        title="VK Bridge",
        schema={
            "components": [
                {
                    "type": "markdown",
                    "text": (
                        "Set **VK_GROUP_TOKEN** in Settings → Secrets, grant it to this skill, "
                        "then configure the options below.\n\n"
                        "**How to get a VK group token:**\n"
                        "1. Create a VK Community at `vk.com/groups`\n"
                        "2. Enable Messages → Community messages → Enabled\n"
                        "3. Enable Messages → Bot capabilities → Enabled\n"
                        "4. Note the Group ID (numeric) from group URL or Settings\n"
                        "5. Manage → API usage → Create token → check `messages`\n"
                        "6. Copy the token into Settings → Secrets as `VK_GROUP_TOKEN`\n\n"
                        "**Command mode**: controls which slash commands can be sent from VK.\n\n"
                        "The first user who messages the bot becomes the bound peer. "
                        "Use `full_access` only for a community you trust as an owner channel."
                    ),
                },
                {
                    "type": "form",
                    "route": "vk/settings/save",
                    "method": "POST",
                    "fields": [
                        {
                            "name": "VK_GROUP_ID",
                            "label": "VK Group ID (numeric)",
                            "type": "text",
                            "placeholder": "123456789",
                        },
                        {
                            "name": "VK_COMMAND_MODE",
                            "label": "Command mode",
                            "type": "select",
                            "options": [
                                {"value": "full_access", "label": "Full access (default) — raw owner commands incl. /panic, /restart"},
                                {"value": "safe_commands", "label": "Safe — allow /status, /bg status only"},
                                {"value": "strict", "label": "Strict — block all slash commands"},
                            ],
                            "placeholder": "full_access",
                        },
                        {
                            "name": "VK_PEER_ID",
                            "label": "VK Peer ID (auto-bound on first message)",
                            "type": "text",
                            "placeholder": "auto-bound",
                        },
                    ],
                    "submit_label": "Save VK settings",
                },
            ]
        },
    )
