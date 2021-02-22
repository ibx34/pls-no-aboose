import logging
import re
import typing

import discord
from discord.ext import commands
from unidecode import unidecode
import src.plugins.state.time as time

from ... import Plugin

log = logging.getLogger(__name__)

class Admin(Plugin):

    # async def check_raid(self, config, guild_id, member, message):
    #     if config.raid_mode != RaidMode.strict.value:
    #         return

    #     checker = self._spam_check[guild_id]
    #     if not checker.is_spamming(message):
    #         return

    #     try:
    #         await member.ban(reason='Auto-ban from spam (strict raid mode ban)')
    #     except discord.HTTPException:
    #         log.info(f'[Raid Mode] Failed to ban {member} (ID: {member.id}) from server {member.guild} via strict mode.')
    #     else:
    #         log.info(f'[Raid Mode] Banned {member} (ID: {member.id}) from server {member.guild} via strict mode.')

    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.group(aliases=["remove", "purge"], name="clear")
    async def clear(self, ctx):
        return
        
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @clear.command(name="bots", aliases=["bot"])
    async def clear_bots(self, ctx, prefix=None, search=100):

        def predicate(m):
            return (m.webhook_id is None and m.author.bot) or (
                prefix and m.content.startswith(prefix)
            )

        await ctx.channel.purge(limit=search, check=predicate)

    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @clear.command(name="stickers")
    async def clear_stickers(self, ctx, search=100):

        def predicate(m):
            return m.stickers

        await ctx.channel.purge(limit=search, check=predicate)

    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @clear.command(name="embeds")
    async def clear_embeds(self, ctx, search=100):

        def predicate(m):
            return len(m.embeds)

        await ctx.channel.purge(limit=search, check=predicate)

    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @clear.command(name="files")
    async def clear_files(self, ctx, search=100):

        def predicate(m):
            return len(m.attachments)

        await ctx.channel.purge(limit=search, check=predicate)

    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @clear.command(name="attachments")
    async def clear_attachments(self, ctx, search=100):

        def predicate(m):
            return m.embeds or m.attachments

        await ctx.channel.purge(limit=search, check=predicate)

    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @clear.command(name="user")
    async def clear_user(self, ctx, user: discord.Member, search=100):

        def predicate(m):
            return m.author.id == user.id

        await ctx.channel.purge(limit=search, check=predicate)

    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @clear.command(name="emoji")
    async def clear_emoji(self, ctx, search=100):

        custom_emoji = re.compile(r"<a?:[a-zA-Z0-9\_]+:([0-9]+)>")

        def predicate(m):
            return custom_emoji.search(m.content)

        await ctx.channel.purge(limit=search, check=predicate)

    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @clear.command(name="reactions")
    async def clear_reactions(self, ctx, search=100):

        total_reactions = 0
        async for message in ctx.history(limit=search, before=ctx.message):
            if len(message.reactions):
                total_reactions += sum(reaction.count for reaction in message.reactions)
                await message.clear_reactions()

        await ctx.send(f"Removed {total_reactions} reactions.")

    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @clear.command(name="contains")
    async def clear_contains(self, ctx, search=100, *, string:str=None):

        if string is None:
            return await ctx.send("Provide a string to search for.")
            
        if len(string) < 3:
            return await ctx.send("Your string must be over 3 characters.")

        def predicate(m):
            return string.lower in m.content.lower()

        await ctx.channel.purge(limit=search, check=predicate)
    
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @clear.command(name="all")
    async def clear_all(self, ctx, search=100):   

        await ctx.channel.purge(limit=search)