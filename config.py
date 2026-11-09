"""Configuration loader and validator for the Telegram Forward Bot."""

import logging
import os
import re
import sys
from dataclasses import dataclass
from typing import Set

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _parse_chat_ids(raw: str) -> tuple[Set[int], Set[str]]:
    """Parse comma-separated chat IDs/usernames.

    Accepts integer IDs (e.g. -1001234567890) and usernames (e.g. @channel or channel).
    Returns (set_of_int_ids, set_of_lowercased_usernames_without_at).
    """
    int_ids: Set[int] = set()
    usernames: Set[str] = set()
    if not raw:
        return int_ids, usernames

    for item in raw.split(","):
        token = item.strip()
        if not token:
            continue
        try:
            int_ids.add(int(token))
        except ValueError:
            clean = token.lstrip("@").lower()
            if clean:
                usernames.add(clean)
    return int_ids, usernames


def _parse_single_chat(raw: str) -> int | str:
    """Parse a single target chat ID (integer) or username (e.g. @groupname)."""
    raw = raw.strip()
    try:
        return int(raw)
    except ValueError:
        return raw if raw.startswith("@") else f"@{raw}"


@dataclass(frozen=True)
class Config:
    bot_token: str
    source_chat_ids: Set[int]
    source_chat_usernames: Set[str]
    target_chat_id: int | str
    forward_silent: bool
    log_level: str

    def matches_source(self, chat_id: int, chat_username: str | None) -> bool:
        """Check if a given chat matches any configured source chat."""
        if chat_id in self.source_chat_ids:
            return True
        if chat_username and chat_username.lower() in self.source_chat_usernames:
            return True
        return False

    def is_target(self, chat_id: int, chat_username: str | None) -> bool:
        """Check if a given chat is the target chat (to avoid echo loops)."""
        if isinstance(self.target_chat_id, int):
            return chat_id == self.target_chat_id
        clean = self.target_chat_id.lstrip("@").lower()
        return bool(chat_username and chat_username.lower() == clean)


def load_config() -> Config:
    """Load configuration from environment variables (and .env file if present)."""
    load_dotenv()

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or ":" not in token:
        logger.error(
            "BOT_TOKEN is missing or invalid! Set it in your .env file or Railway variables. "
            "Get a token from @BotFather on Telegram."
        )
        sys.exit(1)

    source_raw = os.getenv("SOURCE_CHAT_IDS", "").strip()
    source_ids, source_names = _parse_chat_ids(source_raw)
    if not source_ids and not source_names:
        logger.error(
            "SOURCE_CHAT_IDS is missing or empty! Provide at least one chat ID/username, "
            "e.g. SOURCE_CHAT_IDS=-1001234567890,-1009876543210,@my_channel"
        )
        sys.exit(1)

    target_raw = os.getenv("TARGET_CHAT_ID", "").strip()
    if not target_raw:
        logger.error(
            "TARGET_CHAT_ID is missing! Provide the ID or username of the destination group, "
            "e.g. TARGET_CHAT_ID=-1001112223334 or TARGET_CHAT_ID=@my_group"
        )
        sys.exit(1)
    target_id = _parse_single_chat(target_raw)

    silent = os.getenv("FORWARD_SILENT", "false").strip().lower() in {"1", "true", "yes"}
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()

    return Config(
        bot_token=token,
        source_chat_ids=source_ids,
        source_chat_usernames=source_names,
        target_chat_id=target_id,
        forward_silent=silent,
        log_level=log_level,
    )
