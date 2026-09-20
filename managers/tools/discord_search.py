"""Discord search tool handler.

Uses a module-level guild reference set during bot startup.
"""

import json

from managers.discord_search import discord_search_client

_guild = None
_bot = None


def set_guild(guild) -> None:
    global _guild
    _guild = guild


def set_bot(bot) -> None:
    global _bot
    _bot = bot


async def discord_search(
    action: str,
    query: str | None = None,
    channel_id: str | None = None,
    author_id: str | None = None,
    has: str | None = None,
    pinned: bool | None = None,
    sort_order: str = "desc",
    top_n: int = 5,
    user_id: str | None = None,
    role_id: str | None = None,
    channel_type: str | None = None,
    include_archived: bool = True,
    include_members: bool = False,
    limit: int = 25,
    before: str | None = None,
    after: str | None = None,
) -> str:
    if discord_search_client is None:
        return json.dumps({"error": "Discord search not initialized"}, ensure_ascii=False)

    if action == "messages":
        if not query:
            return json.dumps({"error": "query is required for message search"}, ensure_ascii=False)
        result = await discord_search_client.search_messages(
            guild_id=_guild.id if _guild else 0,
            query=query,
            channel_id=int(channel_id) if channel_id else None,
            author_id=int(author_id) if author_id else None,
            has=has,
            pinned=pinned,
            sort_order=sort_order,
            limit=min(top_n, 25),
            before=before,
            after=after,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    if _guild is None:
        return json.dumps({"error": "Guild not available"}, ensure_ascii=False)

    if action == "members":
        result = await discord_search_client.search_members(
            guild=_guild,
            query=query,
            user_id=int(user_id) if user_id else None,
            role_id=int(role_id) if role_id else None,
            limit=min(top_n, 100),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    if action == "channels":
        result = await discord_search_client.search_channels(
            guild=_guild,
            query=query,
            channel_type=channel_type,
            limit=min(top_n, 50),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    if action == "threads":
        result = await discord_search_client.search_threads(
            guild=_guild,
            query=query,
            include_archived=include_archived,
            limit=min(top_n, 50),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    if action == "roles":
        result = await discord_search_client.search_roles(
            guild=_guild,
            query=query,
            include_members=include_members,
            limit=min(top_n, 50),
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    if action == "history":
        ch = _guild.get_channel(int(channel_id)) if channel_id else None
        if ch is None:
            return json.dumps({"error": f"Channel {channel_id} not found"}, ensure_ascii=False)
        result = await discord_search_client.get_channel_history(
            channel=ch,
            limit=min(limit, 100),
            before=int(before) if before else None,
            after=int(after) if after else None,
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    return json.dumps({"error": f"Unknown action: {action}"}, ensure_ascii=False)
