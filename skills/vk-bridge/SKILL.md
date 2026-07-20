---
name: vk-bridge
description: VK/Max Messenger bridge for Ouroboros with VkBotLongPoll, configurable command modes, and media delivery.
version: 1.0.0
type: extension
entry: plugin.py
runtime: python3
permissions: [net, read_settings, widget, route, supervised_task, subscribe_event, inject_chat]
env_from_settings: [VK_GROUP_TOKEN, VK_GROUP_ID]
subscribe_events: [chat.outbound, chat.typing, chat.photo, chat.document]
when_to_use: User wants to communicate with Ouroboros through VK/Max Messenger.
timeout_sec: 60
---

# VK/Max Messenger Bridge

Bidirectional VK/Max Messenger bridge for Ouroboros. Uses VK Bots Long Poll
to receive inbound messages and mirrors host chat output back to VK/Max.

## Command Modes

| Mode | Allowed commands | Blocked |
|------|-----------------|---------|
| **strict** | None — all slash commands blocked | Everything with `/` |
| **safe_commands** | `/status`, `/bg`, `/bg status` | Mutating commands |
| **full_access** (default) | Raw owner commands including `/panic`, `/restart`, `/review`, `/evolve`, `/bg` | Unknown commands only |

## Setup

1. Create a VK Community (group) at `vk.com/groups`
2. Enable **Messages** → **Community messages** → **Enabled**
3. Enable **Messages** → **Bot capabilities** → **Enabled**
4. Copy the **Group ID** (numeric, from group URL or Settings)
5. Go to **Manage** → **API usage** → **Create token** with `messages` permission
6. Set `VK_GROUP_TOKEN` in Ouroboros Settings → Secrets
7. Set `VK_GROUP_ID` in Ouroboros Settings → VK Bridge
8. Configure command mode and other options in Settings → VK Bridge
9. Toggle the skill on

**Important:** The group token must have the `messages` (offline) permission.
Write access is granted after the token is created — no additional confirmation
needed. Use `full_access` only for a community you trust as an owner channel.

## Files and Media

When Ouroboros delivers a file via `chat.document`, the bridge forwards it
as a VK document attachment. Photos and videos are mirrored with inline
attachments. Supported inbound: text and photos. Voice messages would require
an OpenAI Whisper API key (`OPENAI_API_KEY` in Settings → Secrets).

Long text replies are automatically split into multiple VK messages (VK's
limit is 4096 characters per message).
