import argparse
import io
import logging
import shlex
import typing
from datetime import datetime
from textwrap import dedent

import discord
from discord.ext import commands
from unidecode import unidecode

from ... import Plugin, constants
from src.constants import FORMATS

log = logging.getLogger(__name__)

class BetterAuditLogs():
    def __init__(self,bot):
        self.bot = bot

    async def search_audit_logs(self,guild,**kwargs):
        action = kwargs.get("action")
        target = kwargs.get("target")
        time = kwargs.get("time")

        _actions = {
            "ban": discord.AuditLogAction.ban,
            "unban": discord.AuditLogAction.unban,
            "kick": discord.AuditLogAction.kick,
            "role_diff": discord.AuditLogAction.member_role_update,
        }
        
        try_and_find_entry = await guild.audit_logs(limit=1,after=time,action=_actions[action]).flatten()

        if try_and_find_entry is not None:
            if try_and_find_entry[0].target.id == target:
                return try_and_find_entry[0]

    async def add_case(self,**kwargs):
        guild = kwargs.get("guild")

        if guild is not None:
            async with self.bot.pool.acquire() as conn:
                query = """INSERT INTO cases(guild,moderator,reason,target,role,id,modlog,type) VALUES($1,$2,$3,$4,$5,$6,$7,$8)"""
                await conn.execute(query,
                    guild,
                    kwargs.get("moderator"),
                    kwargs.get("reason"),
                    kwargs.get("target"),
                    kwargs.get("role"),
                    kwargs.get("id"),
                    kwargs.get("modlog"),
                    kwargs.get("type")
                )

    async def send_logs(self,guild,entry,role:discord.Role=None):
        config = self.bot.configs[guild.id]
        if config.get("modlogs"):
            channel = guild.get_channel(config["modlogs"])
            self.bot.cases[guild.id] += 1

            message = await channel.send(
                FORMATS[entry.action].format(
                user=entry.target,
                user_id=entry.target.id,
                reason=entry.reason,
                moderator=entry.user,
                case=self.bot.cases[guild.id],
                ascii_time=datetime.utcnow().strftime("%H:%M:%S"),         
                role=f"<@&{role}>",          
                )
            )
            try:
                await self.add_case(guild=guild.id,reason=entry.reason,target=entry.target.id,moderator=entry.user.id,id=self.bot.cases[guild.id],type=entry.action,modlog=message.id)
            except Exception as err:
                print(err)

class Logger(Plugin):
    def __init__(self,Plugin):
        self.BetterAuditLogs = BetterAuditLogs(Plugin)
        self.pls = Plugin

    @Plugin.listener()
    async def on_member_ban(self, guild, user):
        entry = await self.BetterAuditLogs.search_audit_logs(guild=guild,target=user.id,action="ban",time=datetime.utcnow())
        setattr(entry, 'action', "ban")
        await self.BetterAuditLogs.send_logs(guild=guild,entry=entry)

    @Plugin.listener()
    async def on_member_unban(self, guild, user):
        entry = await self.BetterAuditLogs.search_audit_logs(guild=guild,target=user.id,action="unban",time=datetime.utcnow())
        setattr(entry, 'action', "unban")
        await self.BetterAuditLogs.send_logs(guild=guild,entry=entry)

    @Plugin.listener()
    async def on_member_remove(self, user):
        entry = await self.BetterAuditLogs.search_audit_logs(guild=user.guild,target=user.id,action="kick",time=datetime.utcnow())
        setattr(entry, 'action', "kick")
        await self.BetterAuditLogs.send_logs(guild=user.guild,entry=entry)

    @Plugin.listener()
    async def on_member_update(self,before,after):

        if after.roles or before.roles:
            if after.roles == before.roles:
                if before.roles != after.roles:
                    pass
                return

            entry = await self.BetterAuditLogs.search_audit_logs(guild=before.guild,target=before.id,action="role_diff",time=datetime.utcnow())
            if entry:
                            
                role = entry.after
                if entry.before.roles == [] and entry.after:
                    setattr(entry, 'action', "mute")
                elif entry.before and entry.after.roles == []:
                    setattr(entry, 'action', "unmute")
                    role = entry.before
                
                if self.pls.configs.get(before.guild.id):
                    if role.roles[0].id == self.pls.configs[before.guild.id]['mute_role']:
                        await self.BetterAuditLogs.send_logs(guild=before.guild,entry=entry,role=role.roles[0].id)
                    