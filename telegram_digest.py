# /// script
# requires-python = ">=3.11"
# dependencies = ["telethon==1.45.0"]
# ///
"""Сводка непрочитанного в Telegram для «Пульта дня». Только чтение.

Команды:
  login               войти в аккаунт (ввод только в терминале)
  chats               показать чаты и их блокировку (для терминала, не для Claude)
  block <id|имя>      заблокировать чат
  unblock <id|имя>    снять блокировку
  block-private on|off  заблокировать все личные чаты
  digest              JSON со сводкой, его читает утренняя задача

Заблокированные чаты отсекаются до чтения сообщений и не попадают в вывод digest.
Секреты лежат в ~/.telegram-pult/, вне репозиториев. Файл сессии даёт полный доступ
к аккаунту: его нельзя никому передавать и коммитить.
"""
import asyncio
import getpass
import json
import sys
from pathlib import Path

from telethon import TelegramClient, functions

HOME = Path.home() / ".telegram-pult"
CONFIG = HOME / "config.json"
BLOCKLIST = HOME / "blocklist.json"
SESSION = HOME / "pult"

MAX_CHATS = 15
MAX_MESSAGES = 5
MAX_TEXT = 300


class BlocklistError(Exception):
    pass


def load_blocklist(path=BLOCKLIST):
    """Читает блокировки. Нет файла: блокируем все личные. Битый файл: ошибка."""
    if not path.exists():
        return {"block_private": True, "chats": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        block_private = data["block_private"]
        chats = data["chats"]
    except (ValueError, KeyError, TypeError) as exc:
        raise BlocklistError(str(path)) from exc
    if not isinstance(block_private, bool) or not isinstance(chats, list):
        raise BlocklistError(str(path))
    if not all(isinstance(chat_id, int) and not isinstance(chat_id, bool) for chat_id in chats):
        raise BlocklistError(str(path))
    return {"block_private": block_private, "chats": chats}


def save_blocklist(blocklist, path=BLOCKLIST):
    path.write_text(json.dumps(blocklist, indent=2), encoding="utf-8")


def is_blocked(dialog, blocklist):
    return dialog.id in blocklist["chats"] or (blocklist["block_private"] and dialog.is_user)


def is_muted(dialog):
    settings = dialog.dialog.notify_settings
    return bool(settings and settings.mute_until)


def wanted_dialogs(dialogs, blocklist):
    """Оставляет чаты для сводки: без блокировок, каналов, ботов и «Избранного»."""
    result = []
    for dialog in dialogs:
        if is_blocked(dialog, blocklist) or dialog.is_channel and not dialog.is_group:
            continue
        if dialog.is_user and (dialog.entity.bot or dialog.entity.is_self):
            continue
        if dialog.unread_mentions_count or (dialog.unread_count and not is_muted(dialog)):
            result.append(dialog)
    return result[:MAX_CHATS]


def message_view(message):
    sender = message.sender
    name = getattr(sender, "first_name", None) or getattr(sender, "title", None) or "?"
    text = message.message or "[медиа]"
    return {"from": name, "text": text[:MAX_TEXT]}


async def read_messages(client, dialog):
    """Личный чат: последние непрочитанные. Группа: только упоминания тебя."""
    if dialog.is_user:
        limit = min(dialog.unread_count, MAX_MESSAGES)
        messages = await client.get_messages(
            dialog.entity, limit=limit, min_id=dialog.dialog.read_inbox_max_id
        )
        return [message_view(m) for m in messages if not m.out]
    if not dialog.unread_mentions_count:
        return []
    result = await client(
        functions.messages.GetUnreadMentionsRequest(
            peer=dialog.entity, offset_id=0, add_offset=0, limit=MAX_MESSAGES, max_id=0, min_id=0
        )
    )
    ids = [m.id for m in result.messages]
    messages = await client.get_messages(dialog.entity, ids=ids)
    return [message_view(m) for m in messages if m]


def make_client():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    return TelegramClient(str(SESSION), config["api_id"], config["api_hash"])


async def digest():
    blocklist = load_blocklist()
    if not CONFIG.exists():
        return {"status": "not_connected"}
    client = make_client()
    await client.connect()
    try:
        if not await client.is_user_authorized():
            return {"status": "not_connected"}
        dialogs = wanted_dialogs(await client.get_dialogs(archived=False), blocklist)
        chats = []
        for dialog in dialogs:
            chats.append({
                "chat": dialog.name,
                "kind": "private" if dialog.is_user else "group",
                "unread": dialog.unread_count,
                "mentions": dialog.unread_mentions_count,
                "messages": await read_messages(client, dialog),
            })
        return {"status": "ok", "chats": chats}
    finally:
        await client.disconnect()


async def login():
    HOME.mkdir(exist_ok=True)
    if not CONFIG.exists():
        print("api_id и api_hash выдаются на https://my.telegram.org в разделе API development tools.")
        api_id = int(input("api_id: ").strip())
        api_hash = getpass.getpass("api_hash (ввод скрыт): ").strip()
        CONFIG.write_text(json.dumps({"api_id": api_id, "api_hash": api_hash}), encoding="utf-8")
    client = make_client()
    await client.start()
    me = await client.get_me()
    await client.disconnect()
    print(f"Вход выполнен: {me.first_name}")
    if not BLOCKLIST.exists():
        answer = input("Заблокировать все личные чаты? [Y/n]: ").strip().lower()
        save_blocklist({"block_private": answer not in ("n", "no", "н", "нет"), "chats": []})
    print("Дальше: команда chats покажет чаты, block <id|имя> заблокирует нужные.")


async def list_dialogs():
    client = make_client()
    await client.connect()
    try:
        if not await client.is_user_authorized():
            sys.exit("Сначала выполни login.")
        return await client.get_dialogs(archived=False)
    finally:
        await client.disconnect()


def find_dialogs(dialogs, query):
    if query.lstrip("-").isdigit():
        return [d for d in dialogs if d.id == int(query)]
    return [d for d in dialogs if query.casefold() in d.name.casefold()]


async def set_blocked(query, blocked):
    blocklist = load_blocklist()
    matches = find_dialogs(await list_dialogs(), query)
    if len(matches) != 1:
        print(f"Найдено чатов: {len(matches)}. Нужен ровно один, укажи id:")
        for dialog in matches:
            print(f"  {dialog.id}  {dialog.name}")
        sys.exit(1)
    dialog = matches[0]
    chats = set(blocklist["chats"])
    chats.add(dialog.id) if blocked else chats.discard(dialog.id)
    blocklist["chats"] = sorted(chats)
    save_blocklist(blocklist)
    print(f"{'Заблокирован' if blocked else 'Разблокирован'}: {dialog.name}")
    if not blocked and dialog.is_user and blocklist["block_private"]:
        print("Этот чат всё ещё закрыт: включена блокировка всех личных.")


async def show_chats():
    blocklist = load_blocklist()
    for dialog in await list_dialogs():
        mark = "закрыт " if is_blocked(dialog, blocklist) else "открыт "
        print(f"{mark} {dialog.id:>16}  {dialog.name}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    argument = " ".join(sys.argv[2:])
    if command == "digest":
        try:
            result = asyncio.run(digest())
        except Exception as exc:  # сводка не должна падать из-за Telegram
            result = {"status": "error", "detail": type(exc).__name__}
        print(json.dumps(result, ensure_ascii=False))
    elif command == "login":
        asyncio.run(login())
    elif command == "chats":
        asyncio.run(show_chats())
    elif command in ("block", "unblock") and argument:
        asyncio.run(set_blocked(argument, command == "block"))
    elif command == "block-private" and argument in ("on", "off"):
        blocklist = load_blocklist()
        blocklist["block_private"] = argument == "on"
        save_blocklist(blocklist)
        print(f"Блокировка всех личных: {argument}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
