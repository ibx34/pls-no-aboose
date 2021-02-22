import discord
from discord.ext import commands

from ... import Plugin, config

class Guild(Plugin):

    @Plugin.listener()
    async def on_guild_join(self,guild):

        query = """INSERT INTO guilds(id) VALUES($1)"""
        await self.pls.pool.execute(query,guild.id)

        async with self.pls.pool.acquire() as conn:
            guild = await conn.fetchrow("SELECT * FROM guilds WHERE id = $1",guild.id)

            muted_members = []
            for member in await conn.fetch("SELECT * FROM muted_members WHERE guild = $1",guild.id):
                muted_members.append(member['id'])

            self.configs[guild["id"]] = {"mute_role": guild["muterole"],"modlogs": guild["modlogs"],"muted_members": muted_members}
            self.prefixes[guild["id"]] = [x for x in guild["prefix"]]        

    @Plugin.listener()
    async def on_guild_remove(self,guild):

        del self.pls.prefixes[guild.id]
        del self.pls.configs[guild.id]

    @Plugin.listener()
    async def on_guild_role_delete(self, role):
        async with self.pls.pool.acquire() as conn:
            guild_id = role.guild.id
            config = self.pls.configs.get(guild_id)
            if config is None or config.get("mute_role") != role.id:
                return

            query = """UPDATE guilds SET mute_role = $1 WHERE id = $2 UNION DELETE FROM muted_members WHERE guild = $1"""
            query2 = """DELETE FROM muted_members WHERE guild = $1"""
            await conn.execute(query,guild_id)
            await conn.execute(query2,guild_id)
            del config["muted_members"]