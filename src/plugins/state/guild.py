import datetime as date
from datetime import datetime

import discord
from discord.ext import commands

from ... import Plugin, config, constants


class Guild(Plugin):

    @Plugin.listener()
    async def on_guild_join(self,guild):

        query = """INSERT INTO guilds(id) VALUES($1)"""
        await self.pls.pool.execute(query,guild.id)

        async with self.pls.pool.acquire() as conn:
            new_guild = await conn.fetchrow("SELECT * FROM guilds WHERE id = $1",guild.id)
            members = await conn.fetch("SELECT * FROM muted_members WHERE guild = $1",guild.id)
            muted_members = []
            
            if members:
                for member in members:
                    muted_members.append(member['id'])
            
            self.configs[new_guild["id"]] = {"mute_role": guild["muterole"],"modlogs": guild["modlogs"],"muted_members": muted_members}
            self.prefixes[new_guild["id"]] = [x for x in guild["prefix"]]        

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

            query = """UPDATE guilds SET muterole = $1 WHERE id = $2"""
            query2 = """DELETE FROM muted_members WHERE guild = $1"""
            await conn.execute(query,None,guild_id)
            await conn.execute(query2,guild_id)
            del config["muted_members"]
            del config['mute_role']

    @Plugin.listener()
    async def on_message_delete(self,message):
        if (message.author.bot):
            return

        config = self.pls.configs.get(message.guild.id)
        if config is None or not config.get("messagelogs"):
            return

        channel = message.guild.get_channel(config["messagelogs"])

        await channel.send(constants.FORMATS["message_logs"]["delete"].format(
                user=message.author,
                user_id=message.author.id,
                ascii_time=datetime.utcnow().strftime("%H:%M:%S"),
                content=message.content[:1700].replace("`", "\""),
                channel=message.channel.mention,
                channel_id=message.channel.id
            )
        )

    @Plugin.listener()
    async def on_message_edit(self,old,new):
        if (old.author.bot):
            return
        if (old.content == new.content):
            return
            
        config = self.pls.configs.get(old.guild.id)
        if config is None or not config.get("messagelogs"):
            return
        channel = old.guild.get_channel(config["messagelogs"])

        embed = discord.Embed()
        embed.add_field(name="Before",value=old.content[:1700].replace("`", "\""),inline=False)
        embed.add_field(name="After",value=new.content[:1700].replace("`", "\""),inline=False)

        await channel.send(constants.FORMATS["message_logs"]["edit"].format(
                user=new.author,
                user_id=new.author.id,
                ascii_time=datetime.utcnow().strftime("%H:%M:%S"),
                channel=new.channel.mention,
                channel_id=new.channel.id
            ),
            embed=embed
        )