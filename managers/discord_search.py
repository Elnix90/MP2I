"""Native Discord search client.

Uses Discord's internal search API to find messages, members, channels,
threads, and roles without external dependencies.
"""

import asyncio
import logging
from typing import Any

import aiohttp
import discord

logger = logging.getLogger(__name__)

SEARCH_RETRIES = 3
SEARCH_CONCURRENCY = 2


class DiscordSearchClient:
    """Search Discord guilds using the internal search API."""

    def __init__(self, token: str, api_base: str = "https://discord.com/api/v10"):
        self._token = token
        self._api_base = api_base
        self._session: aiohttp.ClientSession | None = None
        self._search_slots = asyncio.Semaphore(SEARCH_CONCURRENCY)

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bot {self._token}",
            "Content-Type": "application/json",
        }

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def search_messages(
        self,
        guild_id: int,
        query: str,
        channel_id: int | None = None,
        author_id: int | None = None,
        author_type: str | None = None,
        has: str | None = None,
        pinned: bool | None = None,
        before: str | None = None,
        after: str | None = None,
        sort_by: str = "timestamp",
        sort_order: str = "desc",
        link_hostname: str | None = None,
        attachment_extension: str | None = None,
        limit: int = 25,
        offset: int = 0,
        accessible_channel_ids: set[int] | None = None,
    ) -> dict[str, Any]:
        session = await self.get_session()
        params: dict[str, str] = {"content": query[:1024]}

        if channel_id:
            params["channel_id"] = str(channel_id)
        if author_id:
            params["author_id"] = str(author_id)
        if author_type:
            params["author_type"] = author_type
        if has:
            params["has"] = has
        if pinned is not None:
            params["pinned"] = str(pinned).lower()
        if before:
            params["max_id"] = before
        if after:
            params["min_id"] = after
        if sort_by:
            params["sort_by"] = sort_by
        if sort_order:
            params["sort_order"] = sort_order
        if link_hostname:
            params["link_hostname"] = link_hostname
        if attachment_extension:
            params["attachment_extension"] = attachment_extension
        if limit:
            params["limit"] = str(min(limit, 25))
        if offset:
            params["offset"] = str(min(offset, 9975))
        params["include_nsfw"] = "false"

        url = f"{self._api_base}/guilds/{guild_id}/messages/search"

        for attempt in range(SEARCH_RETRIES):
            try:
                async with self._search_slots, session.get(url, headers=self.headers, params=params) as resp:
                    if resp.status == 200:
                        try:
                            data = await resp.json()
                        except (aiohttp.ContentTypeError, ValueError):
                            return {"error": "Invalid response from Discord search"}

                        raw_messages = data.get("messages")
                        if not isinstance(raw_messages, list):
                            return {"error": "Invalid response from Discord search"}

                        messages = self._format_messages(raw_messages, guild_id)

                        if accessible_channel_ids is not None:
                            messages = [m for m in messages if int(m.get("channel_id", 0)) in accessible_channel_ids]

                        return {
                            "success": True,
                            "returned": len(messages),
                            "has_more": bool(data.get("total_results", 0) > offset + min(limit, 25)) if accessible_channel_ids is None else None,
                            "messages": messages,
                            "scope": {"guild_id": str(guild_id), "channel_id": str(channel_id) if channel_id else None},
                        }

                    if resp.status in (202, 429):
                        retry_after = 2.0
                        try:
                            data = await resp.json()
                            retry_after = float(data.get("retry_after", retry_after))
                        except Exception:
                            header = resp.headers.get("Retry-After")
                            retry_after = float(header) if header else retry_after
                        if attempt < SEARCH_RETRIES - 1 and 0 <= retry_after <= 30:
                            await asyncio.sleep(retry_after)
                            continue
                        return {"error": "Discord search temporarily unavailable"}

                    if resp.status == 403:
                        return {"error": "No permission to search messages"}

                    logger.error("Message search failed: HTTP %s", resp.status)
                    return {"error": f"Search failed: {resp.status}"}

            except asyncio.CancelledError:
                raise
            except (aiohttp.ClientError, TimeoutError):
                return {"error": "Discord search temporarily unavailable"}
            except Exception as error:
                logger.exception("Unexpected search failure: %s", type(error).__name__)
                return {"error": "Search failed unexpectedly"}

        return {"error": "Search failed after retries"}

    def _format_messages(self, messages: list[list[dict]], guild_id: int) -> list[dict]:
        formatted = []
        for msg_group in messages:
            for msg in msg_group:
                formatted.append(
                    {
                        "id": msg.get("id"),
                        "content": msg.get("content", ""),
                        "author": msg.get("author", {}).get("username", "Unknown"),
                        "author_id": msg.get("author", {}).get("id"),
                        "channel_id": msg.get("channel_id"),
                        "timestamp": msg.get("timestamp"),
                        "attachments": len(msg.get("attachments", [])),
                        "embeds": len(msg.get("embeds", [])),
                        "jump_url": f"https://discord.com/channels/{guild_id}/{msg.get('channel_id')}/{msg.get('id')}",
                    }
                )
        return formatted

    async def search_members(
        self,
        guild: discord.Guild,
        query: str | None = None,
        user_id: int | None = None,
        role_id: int | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        try:
            members = []
            total: int | None = 0

            if user_id:
                member = guild.get_member(user_id)
                if not member:
                    try:
                        member = await guild.fetch_member(user_id)
                    except discord.NotFound:
                        return {"success": True, "returned": 0, "total": 0, "members": [], "note": f"User {user_id} not found"}
                members = [member]
                total = 1
            elif query:
                if role_id:
                    if not guild.chunked:
                        await guild.chunk(cache=True)
                    q = query.casefold()
                    members = [m for m in guild.members if any(r.id == role_id for r in m.roles) and q in m.name.casefold()][:limit]
                else:
                    members = await guild.query_members(query=query, limit=limit)
                total = None
            else:
                if not guild.chunked:
                    await guild.chunk(cache=True)
                if role_id:
                    role = guild.get_role(role_id)
                    if not role:
                        return {"error": f"Role {role_id} not found"}
                    total = len(role.members)
                    members = list(role.members)[:limit]
                else:
                    total = len(guild.members)
                    members = list(guild.members)[:limit]

            formatted = [
                {
                    "id": str(m.id),
                    "username": m.name,
                    "display_name": m.display_name,
                    "nickname": m.nick,
                    "roles": [r.name for r in m.roles if r.name != "@everyone"],
                    "joined_at": m.joined_at.isoformat() if m.joined_at else None,
                    "is_bot": m.bot,
                }
                for m in members
            ]
            return {"success": True, "returned": len(formatted), "total": total, "members": formatted}
        except Exception as error:
            logger.error("Member search failed: %s", type(error).__name__)
            return {"error": "Member search failed"}

    async def search_channels(
        self,
        guild: discord.Guild,
        query: str | None = None,
        channel_type: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        try:
            type_map = {
                "text": discord.ChannelType.text,
                "voice": discord.ChannelType.voice,
                "forum": discord.ChannelType.forum,
                "category": discord.ChannelType.category,
                "news": discord.ChannelType.news,
                "stage": discord.ChannelType.stage_voice,
            }
            channels = list(guild.channels)
            if channel_type and channel_type.lower() in type_map:
                channels = [c for c in channels if c.type == type_map[channel_type.lower()]]
            if query:
                q = query.lower()
                channels = [c for c in channels if q in c.name.lower()]
            channels = channels[:limit]
            formatted = [
                {
                    "id": str(c.id),
                    "name": c.name,
                    "type": str(c.type).split(".")[-1],
                    "category": c.category.name if c.category else None,
                    "position": c.position,
                    "mention": c.mention,
                }
                for c in channels
            ]
            return {"success": True, "count": len(formatted), "channels": formatted}
        except Exception as error:
            logger.error("Channel search failed: %s", type(error).__name__)
            return {"error": "Channel search failed"}

    async def search_threads(
        self,
        guild: discord.Guild,
        query: str | None = None,
        include_archived: bool = True,
        limit: int = 50,
    ) -> dict[str, Any]:
        try:
            threads = []
            seen_ids: set[int] = set()
            for t in guild.threads:
                threads.append(t)
                seen_ids.add(t.id)
            if include_archived:
                for channel in guild.text_channels:
                    try:
                        async for thread in channel.archived_threads(limit=50):
                            if thread.id not in seen_ids:
                                threads.append(thread)
                                seen_ids.add(thread.id)
                    except Exception:
                        logger.debug("Skipping inaccessible thread")
                        continue
            if query:
                q = query.lower()
                threads = [t for t in threads if q in t.name.lower()]
            threads = threads[:limit]
            formatted = [
                {
                    "id": str(t.id),
                    "name": t.name,
                    "parent_channel": t.parent.name if t.parent else None,
                    "owner_id": str(t.owner_id) if t.owner_id else None,
                    "archived": t.archived,
                    "locked": t.locked,
                    "message_count": t.message_count,
                    "member_count": t.member_count,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "jump_url": t.jump_url,
                }
                for t in threads
            ]
            return {"success": True, "count": len(formatted), "threads": formatted}
        except Exception as error:
            logger.error("Thread search failed: %s", type(error).__name__)
            return {"error": "Thread search failed"}

    async def search_roles(
        self,
        guild: discord.Guild,
        query: str | None = None,
        include_members: bool = False,
        limit: int = 50,
    ) -> dict[str, Any]:
        try:
            if not guild.chunked:
                await guild.chunk(cache=True)
            roles = [r for r in guild.roles if r.name != "@everyone"]
            if query:
                q = query.lower()
                roles = [r for r in roles if q in r.name.lower()]
            total = len(roles)
            roles = roles[:limit]
            formatted = []
            for r in roles:
                role_data = {
                    "id": str(r.id),
                    "name": r.name,
                    "color": str(r.color),
                    "position": r.position,
                    "member_count": len(r.members),
                    "mention": r.mention,
                }
                if include_members:
                    role_data["members"] = [{"id": str(m.id), "name": m.display_name} for m in r.members[:20]]
                formatted.append(role_data)
            return {"success": True, "returned": len(formatted), "total": total, "roles": formatted}
        except Exception as error:
            logger.error("Role search failed: %s", type(error).__name__)
            return {"error": "Role search failed"}

    async def get_channel_history(
        self,
        channel: discord.TextChannel,
        limit: int = 25,
        before: int | None = None,
        after: int | None = None,
    ) -> dict[str, Any]:
        try:
            limit = min(limit, 100)
            messages = []
            history_before = discord.Object(id=before) if before else None
            history_after = discord.Object(id=after) if after else None
            async for msg in channel.history(limit=limit, before=history_before, after=history_after):
                messages.append(
                    {
                        "id": str(msg.id),
                        "content": msg.content or "",
                        "author": msg.author.name,
                        "author_id": str(msg.author.id),
                        "timestamp": msg.created_at.isoformat(),
                        "attachments": len(msg.attachments),
                        "embeds": len(msg.embeds),
                        "jump_url": msg.jump_url,
                    }
                )
            return {
                "success": True,
                "channel": channel.name,
                "channel_id": str(channel.id),
                "count": len(messages),
                "messages": messages,
                "has_more": len(messages) == limit,
                "oldest_id": messages[-1]["id"] if messages else None,
            }
        except discord.Forbidden:
            return {"error": f"No permission to read #{channel.name}"}
        except Exception as error:
            logger.error("Channel history failed: %s", type(error).__name__)
            return {"error": "Channel history failed"}


discord_search_client: DiscordSearchClient | None = None


def init_discord_search(token: str) -> DiscordSearchClient:
    global discord_search_client
    discord_search_client = DiscordSearchClient(token)
    return discord_search_client
