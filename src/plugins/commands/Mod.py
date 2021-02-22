import argparse
import datetime
import io
import logging
import re
import shlex
import typing
from textwrap import dedent
from typing import Union

import discord
import src.plugins.state.time as time
import unidecode
from discord.ext import commands
from src.plugins.state.formats import TabularData, prompt
from unidecode import unidecode

from ... import Plugin
from . import Reminders

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

    async def apply_mute(self, member, reason):
        config = self.pls.configs.get(member.guild.id)
        if not config:
            return
        if config.get("mute_role"):
            if member.id not in config.get("muted_members"):
                query = """INSERT INTO muted_members(id,guild) VALUES($1,$2)"""
                await self.pls.pool.execute(query,member.id,member.guild.id)

                await member.add_roles(discord.Object(id=config.get("mute_role")), reason=reason)
                config["muted_members"].append(member.id)
                return True
            return False

    async def remove_mute(self, member, reason):
        config = self.pls.configs.get(member.guild.id)
        if not config:
            return
        if config.get("mute_role"):
            if member.id in config.get("muted_members"):
                query = """DELETE FROM muted_members WHERE id = $1 AND guild = $2"""
                await self.pls.pool.execute(query,member.id,member.guild.id)

                await member.remove_roles(discord.Object(id=config.get("mute_role")), reason=reason)
                config["muted_members"].remove(member.id)
                return True
            return False

    @Plugin.listener()
    async def on_member_join(self, member):
        config = self.pls.configs.get(member.guild.id)
        if not config:
            return
        
        if member.id in config.get("muted_members"):
            if config.get("mute_role"):
                role = discord.Object(id=config.get("mute_role"))
                await member.add_roles(role,reason="[Automod#0000] Member previously muted.")

    @commands.group(name="ban",invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def ban(self,ctx,user: MemberID, *, reason: Reason=None):

        await  ctx.guild.ban(user=user,delete_message_days=7,reason=reason)
        await ctx.send(f"{ctx.author.mention} ➜ Successfully banned **{user}**")

    @ban.command(name="match")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def ban_match(self,ctx,term:str, limit:int=100,*, reason: Reason=None):
        failed = 0
        count = 0
        async for message in ctx.channel.history(limit=limit):
            if message.content == term:
                count += 1
                if not can_execute_action(ctx, ctx.author, message.member):
                    failed += 1
                    continue
                try:
                    await ctx.guild.ban(user=message.member,delete_message_days=7,reason=reason)
                except:
                    failed +=1 

        await ctx.send(f"{ctx.author.mention} ➜ Successfully banned **{count-failed}** of **{count}** users.")

    @commands.command(name="softban")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def softban(self,ctx,user: discord.Member, *, reason: Reason=None):
        
        if not can_execute_action(ctx, ctx.author, user):
            return await ctx.send(f"{ctx.author.mention} ➜ You cannot perform this action...")

        await ctx.guild.ban(user=user, reason=reason, delete_message_days=7)
        await ctx.guild.unban(user=user, reason=f"Softban via {ctx.author} ({ctx.author.id})")
        await ctx.send(f"{ctx.author.mention} ➜ Successfully soft-banned {user.mention}")

    @commands.command(name="multiban")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def multiban(self,ctx,users: commands.Greedy[MemberID], *, reason: Reason=None):

        failed = 0
        for user in users:
            try:
                await ctx.guild.ban(user=user,delete_message_days=7,reason=reason)
            except:
                failed += 1

        await ctx.send(f"{ctx.author.mention} ➜ Successfully banned **{len(users)-failed}** of **{len(users)}** users.")

    @commands.command(name="kick")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def kick(self,ctx,user: MemberID, *, reason: Reason=None):

        await  ctx.guild.kick(user=user,reason=reason)
        await ctx.send(f"{ctx.author.mention} ➜ Successfully kicked **{user}**")

    @commands.command(name="unban")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    async def unban(self,ctx,user: BannedMember, *, reason: Reason=None):

        await ctx.guild.unban(user.user,reason=reason)
        await ctx.send(f"{ctx.author.mention} ➜ Successfully unbanned **{user.user}**")

    @commands.command(name="tempmute")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True, manage_messages=True)
    async def tempmute(self, ctx, user: discord.Member, duration: time.FutureTime, *, reason: Reason=None):

        if Reminders.Reminder is None:
            return await ctx.send(f"{ctx.author.mention} ➜ Tempmutes are currently not available, sorry... Try again later.")

        role = discord.Object(id=self.pls.configs[ctx.guild.id]["mute_role"])
        role_id = self.pls.configs[ctx.guild.id]["mute_role"]
        confirm_muted = await self.apply_mute(user, reason)
        if confirm_muted is False:
            return await ctx.send(f"{ctx.author.mention} ➜  That user is already muted...")
        
        reminder = Reminders.Reminder(self.pls)
        timer = await reminder.create_timer(duration.dt, 'tempmute', ctx.guild.id,ctx.author.id,str(user.id),created=ctx.message.created_at,message_id=role_id)
        delta = time.human_timedelta(duration.dt, source=timer.created_at)
        await ctx.send(f"{ctx.author.mention} ➜ Successfully muted {user.mention} for {delta}.")


    @Plugin.listener()
    async def on_tempmute_timer_complete(self, timer):
        guild_id = timer["author"]
        mod_id = timer["channel"]
        member_id = timer["message"]
        role_id = timer["message_id"]

        await self.pls.wait_until_ready()

        guild = self.pls.get_guild(guild_id)
        if guild is None:
            return

        member = await self.pls.get_or_fetch_member(guild, member_id)
        if member is None or not member._roles.has(role_id):
            async with self._batch_lock:
                self._data_batch[guild_id].append((member_id, False))
            return

        if mod_id != member_id:
            moderator = await self.pls.get_or_fetch_member(guild, mod_id)
            if moderator is None:
                try:
                    moderator = await self.pls.fetch_user(mod_id)
                except: 
                    # request failed somehow
                    moderator = f'Mod ID {mod_id}'
                else:
                    moderator = f'{moderator} (ID: {mod_id})'
            else:
                moderator = f'{moderator} (ID: {mod_id})'

            reason = f'Automatic unmute from timer made on {timer["created"]} by {moderator}.'
        else:
            reason = f'Expiring self-mute made on {timer["created"]} by {member}'

        try:
            await member.remove_roles(discord.Object(id=role_id), reason=reason)
        except discord.HTTPException:
            # if the request failed then just do it manually
            async with self._batch_lock:
                self._data_batch[guild_id].append((member_id, False))

    @commands.command(name="tempban")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True, manage_messages=True)
    async def tempban(self, ctx, user: discord.Member, duration: time.FutureTime, *, reason: Reason=None):

        if Reminders.Reminder is None:
            return await ctx.send(f"{ctx.author.mention} ➜ Tempbans are currently not available, sorry... Try again later.")

        await user.ban(delete_message_days=7,reason=reason)

        reminder = Reminders.Reminder(self.pls)
        timer = await reminder.create_timer(duration.dt, 'tempban', ctx.guild.id,ctx.author.id,str(user.id),created=ctx.message.created_at)
        delta = time.human_timedelta(duration.dt, source=timer.created_at)
        await ctx.send(f"{ctx.author.mention} ➜ Successfully banned {user.mention} for {delta}.")


    @Plugin.listener()
    async def on_tempban_timer_complete(self, timer):
        print(timer)
        guild_id = timer["author"]
        mod_id = timer["channel"]
        member_id = timer["message"]
        await self.pls.wait_until_ready()

        guild = self.pls.get_guild(guild_id)
        if guild is None:
            # RIP
            return

        moderator = await self.pls.get_or_fetch_member(guild, mod_id)
        if moderator is None:
            try:
                moderator = await self.pls.fetch_user(mod_id)
            except:
                moderator = f'Mod ID {mod_id}'
            else:
                moderator = f'{moderator} (ID: {mod_id})'
        else:
            moderator = f'{moderator} (ID: {mod_id})'

        reason = f'Automatic unban from timer made on {timer["created"]} by {moderator}.'
        await guild.unban(discord.Object(id=member_id), reason=reason)

    @commands.group(invoke_without_command=True, name="mute")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True, manage_messages=True)
    async def mute(self, ctx, user: discord.Member, *, reason: Reason=None):
        
        if not can_execute_action(ctx, ctx.author, user):
            return await ctx.send(f"{ctx.author.mention} ➜ You cannot perform this action...")

        confirm_muted = await self.apply_mute(user, reason)

        if confirm_muted is False:
            return await ctx.send(f"{ctx.author.mention} ➜  That user is already muted...")

        await ctx.send(f"{ctx.author.mention} ➜  Successfully muted {user.mention}")

    @staticmethod
    async def update_channels(ctx,role):
        failure = 0
        success = 0
        skipped = 0
        reason = f"Mute role update by mod: {ctx.author} (ID: {ctx.author.id}"
        for channel in ctx.guild.text_channels:
            perms = channel.permissions_for(ctx.guild.me)
            if perms.manage_roles:
                overwrite = channel.overwrites_for(role)
                overwrite.send_messages = False
                overwrite.add_reactions = False
                try:
                    await channel.set_permissions(role,overwrite=overwrite, reason=reason)
                except discord.HTTPException:
                    failure += 1
                else:
                    success += 1
            else:
                skipped += 1
        return success, failure, skipped

    @mute.group(name="role", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def mute_role(self, ctx):

        config = self.pls.configs.get(ctx.guild.id)
        if not config:
            await self.update_guild_config(ctx)
        if not config.get("mute_role"):
            return await ctx.send(f"{ctx.author.mention} -> Your guild does not have a mute role.")
        
        role_id = config.get("mute_role")
        await ctx.send(f"{ctx.author.mention} -> Your mute role is set to <@&{role_id}>. [Muted Members: {len(config.get('muted_members'))}]")

    @mute_role.command(name="create")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def mute_role_create(self, ctx, *, name="Muted"):

        config = self.pls.configs.get(ctx.guild.id)
        if not config:
            await self.update_guild_config(ctx)

        if config.get("mute_role"):
            return await ctx.send(f"{ctx.author.mention} -> A mute role already exists.")

        permissions = discord.Permissions(send_messages=False, add_reactions=False, connect=False, attach_files=False)
        role = await ctx.guild.create_role(name=name,permissions=permissions,colour=discord.Color.red(),reason=f"Mute role create, mod: {ctx.author} (ID: {ctx.author.id}")

        query = """INSERT INTO guilds(id,muterole) VALUES($1,$2) ON CONFLICT(id) DO UPDATE SET muterole = EXCLUDED.muterole"""
        await self.pls.pool.execute(query,ctx.guild.id,role.id)
        config["mute_role"] = role.id

        confirm = await prompt(self=ctx,reacquire=False,message=f"{ctx.author.mention} -> Do you want me to add this role to every channel?")
        if not confirm:
            return await ctx.send(f"{ctx.author.mention} -> Mute role successfully created")

        async with ctx.typing():
            success, failure, skipped = await self.update_channels(ctx=ctx,role=role)
            await ctx.send(f"{ctx.author.mention} -> Mute role successfully created. Overwrite:\n[Updated: {success}, Failed: {failure}, Skipped: {skipped}]")

    @mute_role.command(name="update")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def mute_role_update(self, ctx, role:discord.Role):

        if not self.pls.configs.get(ctx.guild.id):
            await self.update_guild_config(ctx)
        

    @mute_role.command(name="set")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def mute_role_set(self, ctx, *, role: discord.Role):

        if not self.pls.configs.get(ctx.guild.id):
            await self.update_guild_config(ctx)
            
    @mute_role.command(name="unbind")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def mute_role_unbind(self, ctx, *, role: discord.Role):

        if not self.pls.configs.get(ctx.guild.id):
            await self.update_guild_config(ctx)

    @commands.command(name="unmute")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True, manage_messages=True)
    async def unmute(self, ctx, user: discord.Member, *, reason: Reason=None):
        
        if not can_execute_action(ctx, ctx.author, user):
            return await ctx.send(f"{ctx.author.mention} ➜ You cannot perform this action...")

        confirm_muted = await self.remove_mute(user,reason)
        if confirm_muted is False:
            return await ctx.send(f"{ctx.author.mention} ➜  That user is not muted...")

        await ctx.send(f"{ctx.author.mention} ➜  Successfully unmuted {user.mention}")

    @commands.command(name="cleanup")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def cleanup(self, ctx, amount: int, channel: discord.TextChannel = None):
        def is_me(m):
            return m.author.id == ctx.bot.user.id

        channel = channel or ctx.channel

        await channel.purge(limit=amount, check=is_me)

    @commands.command()
    @commands.guild_only()
    async def newusers(self, ctx, *, count=5):

        count = max(min(count, 25), 5)
        members = sorted(ctx.guild.members, key=lambda m: m.joined_at, reverse=True)[
            :count
        ]

        embed = discord.Embed()
        embed.title = "New Members"

        for member in members:
            body = f"Joined {time.human_timedelta(member.joined_at)}\nCreated {time.human_timedelta(member.created_at)}"
            embed.add_field(
                name=f"{member} (ID: {member.id})", value=body, inline=False
            )

        await ctx.send(embed=embed)

    @commands.command(name="sql")
    async def sql(self,ctx,type,*,statement):
        if ctx.author.id != 366649052357591044:
            return

        if type.lower() == "execute": 
            try:
                await self.pls.pool.execute(statement)
            except Exception as err:
                return await ctx.send(f"```css\n[{err}]```")
            await ctx.send(f"Done!")
        if type.lower() == "fetchval": 
            try:
                results = await self.pls.pool.fetchval(statement)
            except Exception as err:
                return await ctx.send(f"```css\n[{err}]```")
            await ctx.send(f"Done!```css\n[{results}]```")
        if type.lower() == "fetchrow": 
            try:
                results = await self.pls.pool.fetchrow(statement)
            except Exception as err:
                return await ctx.send(f"```css\n[{err}]```")
            await ctx.send(f"Done!```css\n[{results}]```")
