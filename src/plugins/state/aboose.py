from datetime import datetime,timedelta

import discord
from discord.ext import commands
from .time import human_timedelta,HumanTime 

from ... import Plugin, config

class Guild():
    def __init__(self):
        self.actions = []

    async def set_entry(self,entry,guild):
        self.actions.append({
            "action": entry.action,
            "mod": entry.user.id,
            "action": entry.action,
            "guild": guild.id,
            "time": entry.created_at
        })

        search_time = datetime.utcnow() - timedelta(hours=1)
        actions = []
        for action in self.actions:
            if action["action"] == entry.action and action["guild"] == guild.id and entry.user.id == action["mod"]:
                if action["time"] > search_time:
                    actions.append(action)

        if len(actions) == config.LIMIT:
            channel = guild.get_channel(config.ABOOSE_LOGS)
            await channel.send(f"❗ **Aboose detected**\n\nMod: {entry.user} (ID: {entry.user.id})\nTarget: {entry.target.id}\nReason: {entry.reason}\nTime: {human_timedelta(entry.created_at)} (Raw: {entry.created_at})\nCategory: {entry.category}\nEntry ID: {entry.id}\nAction: {entry.action}")
            for action in self.actions:
                if action["guild"] == guild.id and action["mod"] == entry.user.id and action["action"] == entry.action:
                    actions.pop(actions.index(action))
                    self.actions.pop(self.actions.index(action))
                    
        return len(actions)

class Aboose(Plugin):
    def __init__(self, pls):
        super().__init__(pls)
        self.guild_data = Guild()

    async def search_audit_logs(self, guild, action, limit=1,role=None,target=None):
        _actions = {
            "ban": discord.AuditLogAction.ban,
            "unban": discord.AuditLogAction.unban,
            "kick": discord.AuditLogAction.kick,
            "role_create": discord.AuditLogAction.role_create,
            "role_delete": discord.AuditLogAction.role_delete,
            "role_update": discord.AuditLogAction.role_update,
        }
        return_entry = await guild.audit_logs(limit=limit,after=datetime.utcnow(),action=_actions[action]).flatten()
        if return_entry is None:
            return

        if action in ["role_create","role_delete","role_update"]:
            if return_entry[0].target.id != role:
                return
        if action in ["ban","kick","unban"]:
            if return_entry[0].target.id != target:
                return
        
        await self.guild_data.set_entry(entry=return_entry[0],guild=guild)
        return return_entry[0]

    @Plugin.listener()
    async def on_guild_role_delete(self, role):

        channel = role.guild.get_channel(config.ABOOSE_LOGS)
        entry = await self.search_audit_logs(guild=role.guild,action="role_delete",role=role.id)

    @Plugin.listener()
    async def on_guild_role_create(self, role):

        channel = role.guild.get_channel(config.ABOOSE_LOGS)
        entry = await self.search_audit_logs(guild=role.guild,action="role_create",role=role.id)