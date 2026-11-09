"""Unit tests for the Telegram Forward Bot."""

import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram import Chat, Message, Update
from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter

from config import Config, _parse_chat_ids, _parse_single_chat, load_config
from main import (
    build_application,
    cmd_id,
    cmd_start,
    forward_handler,
    private_forward_helper,
)


class ConfigTests(unittest.TestCase):
    def test_parse_chat_ids(self):
        raw = "-1001234567890, 12345, @channel_one, channel_two,   -100999 "
        ids, usernames = _parse_chat_ids(raw)
        self.assertEqual(ids, {-1001234567890, 12345, -100999})
        self.assertEqual(usernames, {"channel_one", "channel_two"})

    def test_parse_chat_ids_empty(self):
        ids, usernames = _parse_chat_ids("")
        self.assertEqual(ids, set())
        self.assertEqual(usernames, set())

    def test_parse_single_chat(self):
        self.assertEqual(_parse_single_chat("-1001112223334"), -1001112223334)
        self.assertEqual(_parse_single_chat("123456"), 123456)
        self.assertEqual(_parse_single_chat("@my_group"), "@my_group")
        self.assertEqual(_parse_single_chat("my_group"), "@my_group")

    def test_load_config_valid(self):
        env = {
            "BOT_TOKEN": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
            "SOURCE_CHAT_IDS": "-1001234567890, @alpha",
            "TARGET_CHAT_ID": "-1009999999999",
            "FORWARD_SILENT": "true",
            "LOG_LEVEL": "DEBUG",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = load_config()
            self.assertEqual(cfg.bot_token, env["BOT_TOKEN"])
            self.assertIn(-1001234567890, cfg.source_chat_ids)
            self.assertIn("alpha", cfg.source_chat_usernames)
            self.assertEqual(cfg.target_chat_id, -1009999999999)
            self.assertTrue(cfg.forward_silent)
            self.assertEqual(cfg.log_level, "DEBUG")

    def test_load_config_missing_token_exits(self):
        with patch.dict(os.environ, {"BOT_TOKEN": ""}, clear=True):
            with self.assertRaises(SystemExit):
                load_config()

    def test_load_config_missing_source_exits(self):
        with patch.dict(os.environ, {"BOT_TOKEN": "123:ABC"}, clear=True):
            with self.assertRaises(SystemExit):
                load_config()

    def test_matches_source_by_id(self):
        cfg = Config(
            bot_token="t:ok",
            source_chat_ids={-1001234567890},
            source_chat_usernames={"alpha"},
            target_chat_id=-1009999999999,
            forward_silent=False,
            log_level="INFO",
        )
        self.assertTrue(cfg.matches_source(-1001234567890, None))
        self.assertFalse(cfg.matches_source(-1001111111111, None))

    def test_matches_source_by_username(self):
        cfg = Config(
            bot_token="t:ok",
            source_chat_ids={-1001234567890},
            source_chat_usernames={"alpha"},
            target_chat_id=-1009999999999,
            forward_silent=False,
            log_level="INFO",
        )
        self.assertTrue(cfg.matches_source(-1, "Alpha"))
        self.assertFalse(cfg.matches_source(-1, "beta"))
        self.assertFalse(cfg.matches_source(-1, None))

    def test_is_target_guard(self):
        cfg_int = Config("t:ok", {1}, set(), -1009999999999, False, "INFO")
        self.assertTrue(cfg_int.is_target(-1009999999999, None))
        self.assertFalse(cfg_int.is_target(1, None))

        cfg_user = Config("t:ok", {1}, set(), "@target_group", False, "INFO")
        self.assertTrue(cfg_user.is_target(-1, "Target_Group"))
        self.assertFalse(cfg_user.is_target(-1, "other"))


def _make_update(chat_id: int, username: str | None, title: str, message_id: int = 42) -> Update:
    chat = Chat(id=chat_id, type="supergroup", title=title, username=username)
    msg = Message(message_id=message_id, date=None, chat=chat, text="hello")
    return Update(update_id=1, message=msg)


class ForwardHandlerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.cfg = Config(
            bot_token="t:ok",
            source_chat_ids={-1001234567890},
            source_chat_usernames={"alpha"},
            target_chat_id=-1009999999999,
            forward_silent=False,
            log_level="INFO",
        )

    def _ctx(self):
        ctx = MagicMock()
        ctx.application.bot_data = {"config": self.cfg}
        ctx.bot = AsyncMock()
        return ctx

    async def test_forwards_when_source_matches_by_id(self):
        ctx = self._ctx()
        up = _make_update(-1001234567890, None, "Source Channel", message_id=55)

        await forward_handler(up, ctx)

        ctx.bot.forward_message.assert_awaited_once_with(
            chat_id=-1009999999999,
            from_chat_id=-1001234567890,
            message_id=55,
            disable_notification=False,
        )

    async def test_forwards_when_source_matches_by_username(self):
        ctx = self._ctx()
        up = _make_update(-1008888888888, "ALPHA", "Source Channel 2", message_id=77)

        await forward_handler(up, ctx)

        ctx.bot.forward_message.assert_awaited_once()

    async def test_ignores_non_source_chats(self):
        ctx = self._ctx()
        up = _make_update(-1005555555555, "random_channel", "Random")

        await forward_handler(up, ctx)

        ctx.bot.forward_message.assert_not_awaited()

    async def test_loop_guard_ignores_target_chat(self):
        ctx = self._ctx()
        up = _make_update(-1009999999999, None, "Target Group")

        await forward_handler(up, ctx)

        ctx.bot.forward_message.assert_not_awaited()

    async def test_retry_after_retries_once(self):
        ctx = self._ctx()
        ctx.bot.forward_message.side_effect = [
            RetryAfter(1),
            AsyncMock(),
        ]
        up = _make_update(-1001234567890, None, "Source")

        with patch("asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
            await forward_handler(up, ctx)

        self.assertEqual(ctx.bot.forward_message.await_count, 2)
        sleep_mock.assert_awaited_with(2)

    async def test_network_error_retries_once(self):
        ctx = self._ctx()
        ctx.bot.forward_message.side_effect = [
            NetworkError("timeout"),
            AsyncMock(),
        ]
        up = _make_update(-1001234567890, None, "Source")

        with patch("asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
            await forward_handler(up, ctx)

        self.assertEqual(ctx.bot.forward_message.await_count, 2)
        sleep_mock.assert_awaited_with(2)

    async def test_forbidden_logged_gracefully(self):
        ctx = self._ctx()
        ctx.bot.forward_message.side_effect = Forbidden("bot was kicked from the supergroup")
        up = _make_update(-1001234567890, None, "Source")

        # Must not raise
        await forward_handler(up, ctx)

    async def test_bad_request_content_restricted_skipped(self):
        ctx = self._ctx()
        ctx.bot.forward_message.side_effect = BadRequest("message can't be forwarded")
        up = _make_update(-1001234567890, None, "Source")

        # Must not raise and must not retry
        await forward_handler(up, ctx)
        self.assertEqual(ctx.bot.forward_message.await_count, 1)

    async def test_forwards_channel_posts(self):
        chat = Chat(id=-1001234567890, type="channel", title="Channel Alpha")
        post = Message(message_id=99, date=None, chat=chat, text="channel post text")
        up = Update(update_id=1, channel_post=post)

        ctx = self._ctx()
        await forward_handler(up, ctx)

        ctx.bot.forward_message.assert_awaited_once_with(
            chat_id=-1009999999999,
            from_chat_id=-1001234567890,
            message_id=99,
            disable_notification=False,
        )


class CommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_cmd_start_replies(self):
        cfg = Config("t:ok", {-1001234567890}, {"alpha"}, -1009999999999, False, "INFO")
        ctx = MagicMock()
        ctx.application.bot_data = {"config": cfg}

        chat = Chat(id=1, type="private")
        msg = Message(message_id=1, date=None, chat=chat, text="/start")
        up = Update(update_id=1, message=msg)

        with patch.object(Message, "reply_text", new_callable=AsyncMock) as reply_mock:
            await cmd_start(up, ctx)
            reply_mock.assert_awaited_once()
            sent = reply_mock.await_args[0][0]
            self.assertIn("-1001234567890", sent)
            self.assertIn("@alpha", sent)

    async def test_cmd_id_replies(self):
        ctx = MagicMock()
        chat = Chat(id=-1009999999999, type="supergroup", title="My Group", username="my_group")
        msg = Message(message_id=1, date=None, chat=chat, text="/id")
        up = Update(update_id=1, message=msg)

        with patch.object(Message, "reply_text", new_callable=AsyncMock) as reply_mock:
            await cmd_id(up, ctx)
            reply_mock.assert_awaited_once()
            sent = reply_mock.await_args[0][0]
            self.assertIn("-1009999999999", sent)
            self.assertIn("My Group", sent)


class AppBuilderTests(unittest.TestCase):
    def test_build_application_handlers(self):
        cfg = Config("123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789", {-1001234567890}, {"alpha"}, -1009999999999, False, "INFO")
        app = build_application(cfg)
        self.assertIs(app.bot_data["config"], cfg)
        self.assertGreater(len(app.handlers[0]), 0)


class PrivateForwardHelperTests(unittest.IsolatedAsyncioTestCase):
    async def test_detects_channel_forward(self):
        ctx = MagicMock()
        origin = MagicMock()
        origin.type = "channel"
        origin.chat.id = -1001234567890
        origin.chat.title = "News Channel"

        msg = Message(message_id=1, date=None, chat=Chat(id=1, type="private"))
        object.__setattr__(msg, "forward_origin", origin)
        up = Update(update_id=1, message=msg)

        with patch.object(Message, "reply_text", new_callable=AsyncMock) as reply_mock:
            await private_forward_helper(up, ctx)
            reply_mock.assert_awaited_once()
            sent = reply_mock.await_args[0][0]
            self.assertIn("-1001234567890", sent)
            self.assertIn("News Channel", sent)


if __name__ == "__main__":
    unittest.main()
