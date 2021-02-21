import argparse
import datetime
import io
import logging
import re
import shlex
import typing
from textwrap import dedent

import discord
import unidecode
from discord.ext import commands
from unidecode import unidecode
from typing import Union

from ... import Plugin

# from dapper.modules.state.formats import prompt, TabularData
# import dapper.modules.state.time as time


log = logging.getLogger(__name__)
def can_execute_action(ctx, user, target):
    return user.id == ctx.bot.owner_id or \
           user == ctx.guild.owner or \
           user.top_role > target.top_role

class BannedMember(commands.Converter):
    async def convert(self, ctx, argument):
        ban_list = await ctx.guild.bans()
        try:
            member_id = int(argument, base=10)
            entity = discord.utils.find(lambda u: u.user.id == member_id, ban_list)
        except ValueError:
            entity = discord.utils.find(lambda u: str(u.user) == argument, ban_list)
        if entity is None:
            raise commands.BadArgument(f"{ctx.author.mention} ➜ That user wasn't previously banned...")
        return entity

class MemberID(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            m = await commands.MemberConverter().convert(ctx, argument)
        except commands.BadArgument:
            try:
                member_id = int(argument, base=10)
            except ValueError:
                raise commands.BadArgument(f"{argument} is not a valid member or member ID.") from None
            else:
                m = await ctx.bot.get_or_fetch_member(ctx.guild, member_id)
                if m is None:
                    # hackban case
                    return type('_Hackban', (), {'id': member_id, '__str__': lambda s: f'Member ID {s.id}'})()

        if not can_execute_action(ctx, ctx.author, m):
            raise commands.BadArgument('You cannot do this action on this user due to role hierarchy.')
        return m


class Reason(commands.Converter):
    async def convert(self, ctx, argument):
        reason = f"[{ctx.author}] {argument}"
        if len(reason) > 520:
            raise Exception(f"{ctx.author.mention} ➜ Your reason is too long. ({len(reason)}/512)")
        return reason

class Mod(Plugin):

    @commands.command(name="ban")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def ban(self,ctx,user: MemberID, *, reason: Reason=None):

        await  ctx.guild.ban(user=user,delete_message_days=7,reason=reason)
        await ctx.send(f"{ctx.author.mention} ➜ Successfully banned **{user}**")

    @commands.command(name="unban")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def unban(self,ctx,user: BannedMember, *, reason: Reason=None):

        await ctx.guild.unban(user.user,reason=reason)
        await ctx.send(f"{ctx.author.mention} ➜ Successfully unbanned **{user.user}**")