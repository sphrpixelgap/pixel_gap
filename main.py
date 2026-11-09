"""Telegram Forward Bot - Automatically forwards messages from source channels/groups to a target group.

Runs 24/7 on Railway or any server with Python 3.10+.
"""

import asyncio
import logging
import sys

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, NetworkError, RetryAfter, TimedOut
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import Config, load_config

logging.basicConfig(
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("forward-bot")


# --------------------------------------------------------------------------- #
# Helpers & Commands
# --------------------------------------------------------------------------- #

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Help message in Persian explaining the bot and how to find chat IDs."""
    cfg: Config = context.application.bot_data["config"]
    sources = ", ".join(
        [str(i) for i in cfg.source_chat_ids] + [f"@{u}" for u in cfg.source_chat_usernames]
    ) or "(هنوز تنظیم نشده)"
    target = f"@{cfg.target_chat_id}" if isinstance(cfg.target_chat_id, str) and not cfg.target_chat_id.startswith("@") else str(cfg.target_chat_id)

    text = (
        "🤖 <b>ربات فوروارد خودکار تلگرام</b>\n\n"
        "این ربات تمام پیام‌های ارسالی در کانال‌ها/گروه‌های مبدأ مشخص‌شده را به گروه مقصد فوروارد می‌کند.\n\n"
        f"📌 <b>مبدأهای فعال:</b> <code>{sources}</code>\n"
        f"🎯 <b>مقصد:</b> <code>{target}</code>\n\n"
        "<b>راهنما:</b>\n"
        "• برای دریافت آیدی هر گروه/کانال، این ربات را در آنجا عضو کنید و دستور <code>/id</code> را ارسال کنید.\n"
        "• همچنین در پی‌وی ربات، می‌توانید هر پیامی از کانال مورد نظرتان را به این ربات فوروارد کنید تا آیدی آن کانال را به شما بگوید.\n"
        "• مطمئن شوید ربات در تمام کانال‌ها/گروه‌های مبدأ و گروه مقصد <b>ادمین</b> است."
    )
    if update.effective_message:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Replies with current chat ID and info. Works in groups, channels, and private."""
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not update.effective_message:
        return
    title = chat.title or (user.full_name if user else "نامشخص")
    text = (
        f"ℹ️ <b>اطلاعات گفتگو:</b>\n"
        f"• عنوان: <b>{title}</b>\n"
        f"• نوع: <code>{chat.type}</code>\n"
        f"• آیدی چت: <code>{chat.id}</code>\n"
    )
    if chat.username:
        text += f"• نام کاربری: @{chat.username}\n"
    if user:
        text += f"• آیدی شما: <code>{user.id}</code>"
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def private_forward_helper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """When a user forwards a message to the bot in private, tell them the source chat ID."""
    msg = update.effective_message
    if not msg:
        return

    origin = getattr(msg, "forward_origin", None)
    if not origin:
        return

    chat_id = None
    title = None
    otype = getattr(origin, "type", "")

    if otype == "channel":
        chat_id = origin.chat.id
        title = origin.chat.title
    elif otype == "chat":
        chat_id = origin.sender_chat.id
        title = origin.sender_chat.title
    elif otype == "user":
        chat_id = origin.sender_user.id
        title = origin.sender_user.full_name

    if chat_id is not None:
        await msg.reply_text(
            f"📢 پیام فورواردشده از:\n"
            f"• عنوان: <b>{title or 'نامشخص'}</b>\n"
            f"• آیدی عددی: <code>{chat_id}</code>\n"
            f"این عدد را می‌توانید در <code>SOURCE_CHAT_IDS</code> یا <code>TARGET_CHAT_ID</code> قرار دهید.",
            parse_mode=ParseMode.HTML,
        )


# --------------------------------------------------------------------------- #
# Forwarding Engine
# --------------------------------------------------------------------------- #

async def forward_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main message handler: forwards source chat messages to the target chat."""
    cfg: Config = context.application.bot_data["config"]
    msg = update.effective_message
    chat = update.effective_chat

    if not msg or not chat:
        return

    # Loop guard: never forward messages originating from the target chat itself
    if cfg.is_target(chat.id, chat.username):
        return

    # Only process configured source chats
    if not cfg.matches_source(chat.id, chat.username):
        return

    # Ignore service messages (new members, pinned message notices, etc.)
    # The filter (ALL & ~StatusUpdate.ALL) already handles most cases, but double-check
    if getattr(msg, "new_chat_members", None) or getattr(msg, "left_chat_member", None):
        return

    src_label = chat.title or (f"@{chat.username}" if chat.username else str(chat.id))

    async def _try_forward(attempt: int = 1) -> None:
        try:
            await context.bot.forward_message(
                chat_id=cfg.target_chat_id,
                from_chat_id=chat.id,
                message_id=msg.message_id,
                disable_notification=cfg.forward_silent,
            )
            logger.info(
                "Forwarded msg #%s from '%s' (%s) -> target %s",
                msg.message_id,
                src_label,
                chat.id,
                cfg.target_chat_id,
            )
        except RetryAfter as e:
            logger.warning("Telegram rate limit hit. Sleeping %s seconds...", e.retry_after)
            await asyncio.sleep(e.retry_after + 1)
            if attempt < 2:
                await _try_forward(attempt + 1)
        except BadRequest as e:
            msg_lower = str(e).lower()
            if "can't be forwarded" in msg_lower or "protected" in msg_lower:
                logger.info(
                    "Message #%s from '%s' cannot be forwarded (protected/restricted content by chat settings). Skipping.",
                    msg.message_id,
                    src_label,
                )
            elif "chat not found" in msg_lower:
                logger.error(
                    "TARGET CHAT NOT FOUND (%s). Check that TARGET_CHAT_ID is correct and the bot has joined that group/channel.",
                    cfg.target_chat_id,
                )
            else:
                logger.error("BadRequest forwarding msg #%s: %s", msg.message_id, e)
        except Forbidden as e:
            logger.error(
                "FORBIDDEN (%s): The bot does NOT have permission to send messages in the target "
                "chat (%s) or to read the source chat (%s). "
                "Fix: Add the bot as an administrator to both chats with full permissions!",
                e,
                cfg.target_chat_id,
                chat.id,
            )
        except (TimedOut, NetworkError) as e:
            logger.warning("Transient network error (%s). Retrying in 2s...", e)
            await asyncio.sleep(2)
            if attempt < 2:
                await _try_forward(attempt + 1)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("Unexpected error while forwarding msg #%s: %s", msg.message_id, e)

    await _try_forward()


# --------------------------------------------------------------------------- #
# Application Factory
# --------------------------------------------------------------------------- #

def build_application(cfg: Config) -> Application:
    """Build and wire the PTB Application."""
    app = ApplicationBuilder().token(cfg.bot_token).build()
    app.bot_data["config"] = cfg

    # Commands (registered first so they are not treated as regular messages)
    app.add_handler(CommandHandler(["start", "help"], cmd_start))
    app.add_handler(CommandHandler("id", cmd_id))

    # Helper in private chat: detect forwarded channel ID
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.FORWARDED & (~filters.COMMAND),
            private_forward_helper,
        )
    )

    # Core forwarder: all content messages from channels and groups (exclude status updates)
    content_filter = (
        filters.ALL
        & (~filters.StatusUpdate.ALL)
        & (~filters.COMMAND)
    )
    app.add_handler(MessageHandler(content_filter, forward_handler))

    return app


async def _run() -> None:
    cfg = load_config()
    logging.getLogger().setLevel(getattr(logging, cfg.log_level, logging.INFO))

    app = build_application(cfg)

    # Validate bot token and print identity
    async with app:
        me = await app.bot.get_me()
        logger.info("=" * 60)
        logger.info("Bot started successfully: @%s (id=%s)", me.username, me.id)
        logger.info(
            "Source chats (%d configured): %s",
            len(cfg.source_chat_ids) + len(cfg.source_chat_usernames),
            ", ".join([str(i) for i in cfg.source_chat_ids] + [f"@{u}" for u in cfg.source_chat_usernames]),
        )
        logger.info("Target chat: %s", cfg.target_chat_id)
        logger.info("Silent forwarding: %s", cfg.forward_silent)
        logger.info("Listening for messages... (Ctrl+C to stop)")
        logger.info("=" * 60)

    # run_polling runs forever until SIGINT/SIGTERM
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        close_loop=False,
    )


def main() -> None:
    try:
        asyncio.run(_run())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")


if __name__ == "__main__":
    main()
