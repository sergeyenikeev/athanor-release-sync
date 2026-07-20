from __future__ import annotations

import base64
import io
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.exceptions import ApiError

_VK_MAX_TEXT_LENGTH = 4096
_LINK_RE = re.compile(r"https?://\S+")


class VkClient:
    def __init__(
        self,
        token: str,
        group_id: int,
        *,
        max_photo_size: int = 20 * 1024 * 1024,
    ):
        self._token = token
        self._group_id = group_id
        self._max_photo_size = max_photo_size
        self._vk: Optional[vk_api.vk_api.VkApiMethod] = None
        self._longpoll: Optional[VkBotLongPoll] = None

    def connect(self) -> bool:
        try:
            session = vk_api.VkApi(token=self._token)
            self._vk = session.get_api()
            self._longpoll = VkBotLongPoll(session, self._group_id)
            group_info = self._vk.groups.getById(group_id=self._group_id)
            if group_info:
                return True
        except ApiError as e:
            raise RuntimeError(f"VK API auth failed: {e}") from e
        return False

    def listen(self):
        if self._longpoll is None:
            raise RuntimeError("VkClient not connected — call connect() first")
        for event in self._longpoll.listen():
            yield event

    def send_message(
        self,
        peer_id: int,
        text: str,
        *,
        attachment: Optional[str] = None,
        keyboard: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        if self._vk is None:
            return None
        chunks = self._chunk_text(text) if len(text) > _VK_MAX_TEXT_LENGTH else [text]
        last_msg_id = None
        for chunk in chunks:
            params: Dict[str, Any] = {
                "peer_id": peer_id,
                "message": chunk,
                "random_id": 0,
            }
            if attachment and chunk is chunks[-1]:
                params["attachment"] = attachment
            if keyboard and chunk is chunks[0]:
                params["keyboard"] = keyboard
            try:
                result = self._vk.messages.send(**params)
                last_msg_id = result
            except ApiError as e:
                raise RuntimeError(f"VK send message failed: {e}") from e
            if len(chunks) > 1:
                time.sleep(0.3)
        return last_msg_id

    def send_typing(self, peer_id: int) -> None:
        if self._vk is None:
            return
        try:
            self._vk.messages.setActivity(
                peer_id=peer_id,
                type="typing",
            )
        except ApiError:
            pass

    def download_photo(self, owner_id: int, item_id: int) -> Tuple[str, str]:
        if self._vk is None:
            return ("", "")
        try:
            photos = self._vk.messages.getById(
                peer_id=owner_id,
                message_ids=[item_id],
            )
            for photo in (photos or {}).get("items", []):
                sizes = photo.get("sizes", [])
                if not sizes:
                    continue
                largest = max(sizes, key=lambda s: s.get("width", 0) * s.get("height", 0))
                url = largest.get("url", "")
                if not url:
                    continue
                import httpx
                resp = httpx.get(url, timeout=30, follow_redirects=True)
                if resp.status_code == 200:
                    data = resp.content
                    mime = resp.headers.get("content-type", "image/jpeg")
                    b64 = base64.b64encode(data).decode("ascii")
                    return (b64, mime)
        except Exception:
            pass
        return ("", "")

    def upload_photo(self, peer_id: int, image_bytes: bytes, image_mime: str) -> Optional[str]:
        if self._vk is None:
            return None
        try:
            upload_url = self._vk.photos.getMessagesUploadServer(peer_id=peer_id)["upload_url"]
            ext = "jpg" if "jpeg" in image_mime else "png"
            import httpx
            files = {"photo": (f"image.{ext}", io.BytesIO(image_bytes), image_mime)}
            upload_resp = httpx.post(upload_url, files=files, timeout=30)
            upload_data = upload_resp.json()
            saved = self._vk.photos.saveMessagesPhoto(
                server=upload_data["server"],
                photo=upload_data["photo"],
                hash=upload_data["hash"],
            )
            if saved:
                item = saved[0]
                return f"photo{item['owner_id']}_{item['id']}"
        except Exception:
            pass
        return None

    def get_user_info(self, user_id: int) -> Dict[str, Any]:
        if self._vk is None:
            return {}
        try:
            users = self._vk.users.get(user_ids=user_id)
            if users:
                u = users[0]
                name_parts = [u.get("first_name", ""), u.get("last_name", "")]
                full_name = " ".join(p for p in name_parts if p)
                return {
                    "id": user_id,
                    "full_name": full_name,
                    "first_name": u.get("first_name", ""),
                    "last_name": u.get("last_name", ""),
                }
        except ApiError:
            pass
        return {"id": user_id, "full_name": str(user_id)}

    def extract_photo_info(self, event: Dict[str, Any]) -> Optional[Tuple[int, int]]:
        attachments = event.get("attachments") or event.get("attachments", [])
        for att in attachments:
            if att.get("type") == "photo":
                photo = att.get("photo", {})
                owner_id = photo.get("owner_id", 0)
                item_id = photo.get("id", 0)
                if owner_id and item_id:
                    return (owner_id, item_id)
        return None

    def _chunk_text(self, text: str) -> List[str]:
        if len(text) <= _VK_MAX_TEXT_LENGTH:
            return [text]
        chunks = []
        current = text
        while current:
            if len(current) <= _VK_MAX_TEXT_LENGTH:
                chunks.append(current)
                break
            split_at = _VK_MAX_TEXT_LENGTH
            newline = current.rfind("\n", 0, split_at)
            space = current.rfind(" ", 0, split_at)
            if newline > _VK_MAX_TEXT_LENGTH // 2:
                split_at = newline + 1
            elif space > _VK_MAX_TEXT_LENGTH // 2:
                split_at = space + 1
            chunks.append(current[:split_at])
            current = current[split_at:].lstrip()
        return chunks

    def extract_sender_info(self, event: Dict[str, Any]) -> Dict[str, Any]:
        message = event.get("message") or event.get("object", {}).get("message", {})
        from_id = message.get("from_id", 0)
        peer_id = message.get("peer_id", 0)
        return {"from_id": from_id, "peer_id": peer_id, "sender_info": self.get_user_info(from_id)}

    def event_type(self, event) -> str:
        return getattr(event, "type", None) or "unknown"
