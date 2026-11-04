import json
import sys
from datetime import datetime, timezone
from types import SimpleNamespace as NS

import pytest

import telegram_digest as td



def dlg(id, kind="user", unread=1, mentions=0, muted=False, bot=False, me=False):
    return NS(
        id=id, name=f"c{id}", is_user=kind == "user", is_group=kind == "group",
        is_channel=kind in ("channel", "group"), unread_count=unread, unread_mentions_count=mentions,
        entity=NS(bot=bot, is_self=me),
        dialog=NS(notify_settings=NS(mute_until=datetime.now(timezone.utc) if muted else None)),
    )


def ids(ds, block_private=False, chats=()):
    return [d.id for d in td.wanted_dialogs(ds, {"block_private": block_private, "chats": list(chats)})]


def test_blocked_id_dropped_even_with_mentions():
    assert ids([dlg(1), dlg(2, "group", mentions=3)], chats=[2]) == [1]


def test_block_private_keeps_groups():
    assert ids([dlg(1), dlg(2, "group")], block_private=True) == [2]


def test_channel_bot_self_skipped():
    assert ids([dlg(1, "channel"), dlg(2, bot=True), dlg(3, me=True)]) == []


def test_muted_only_with_mentions():
    assert ids([dlg(1, "group", muted=True), dlg(2, "group", muted=True, mentions=1)]) == [2]


def test_missing_file_blocks_private(tmp_path):
    assert td.load_blocklist(tmp_path / "x.json")["block_private"] is True


@pytest.mark.parametrize("raw", ["{", "[]", '{"chats": []}', '{"block_private": "no", "chats": []}', '{"block_private": false, "chats": ["1"]}'])
def test_bad_file_fails_closed(tmp_path, raw):
    p = tmp_path / "b.json"
    p.write_text(raw, encoding="utf-8")
    with pytest.raises(td.BlocklistError):
        td.load_blocklist(p)


def test_digest_broken_blocklist_is_error(tmp_path, monkeypatch, capsys):
    p = tmp_path / "b.json"
    p.write_text("{", encoding="utf-8")
    monkeypatch.setattr(td.load_blocklist, "__defaults__", (p,))
    monkeypatch.setattr(sys, "argv", ["x", "digest"])
    td.main()
    assert json.loads(capsys.readouterr().out)["status"] == "error"
