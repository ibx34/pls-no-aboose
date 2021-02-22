import asyncio
import datetime
import json
import logging
from textwrap import shorten

import asyncpg
import discord
from discord.ext import commands
from unidecode import unidecode

import src.plugins.state.time as time
from ... import Plugin

log = logging.getLogger(__name__)


class Timer:

    __slots__ = ("event", "id", "created_at", "expires", "channel", "author", "message")

    def __init__(self, *, record):
        self.id = record["id"]

        self.created_at = record["created"]
        self.expires = record["expires"]
        self.channel = record["channel"]
        self.author = record["author"]
        self.message = record["message"]

    @classmethod
    def temporary(cls, *, expires, created, event, author, channel, message):
        pseudo = {
            "id": None,
            "event": event,
            "created": created,
            "expires": expires,
            "author": author,
            "channel": channel,
            "message": message,
        }
        return cls(record=pseudo)

    def __eq__(self, other):
        try:
            return self.id == other.id
        except AttributeError:
            return False

    def __hash__(self):
        return hash(self.id)

    @property
    def human_delta(self):
        return time.human_timedelta(self.created_at)

    def __repr__(self):
        return f"<Timer created={self.created_at} expires={self.expires} event={self.event}>"


class Reminder(Plugin):
    """
    Remind yourself to do that one thing after some time.
    """
    
    def __init__(self, bot):
        self.bot = bot
        self._have_data = asyncio.Event(loop=bot.loop)
        self._current_timer = None
        self._task = bot.loop.create_task(self.dispatch_timers())

    async def get_active_timer(self, days=7):
        query = "SELECT * FROM reminders WHERE expires < (CURRENT_DATE + $1::interval) ORDER BY expires LIMIT 1;"
        con = self.bot.pool

        record = await con.fetchrow(query, datetime.timedelta(days=days))
        return record

    async def wait_for_active_timers(self, days=7):
        async with self.bot.pool.acquire() as conn:
            timer = await self.get_active_timer(days=days)
            if timer is not None:
                self._have_data.set()
                return timer

            self._have_data.clear()
            self._current_timer = None
            await self._have_data.wait()
            return await self.get_active_timer(days=days)

    async def call_timer(self, timer):
        query = "DELETE FROM reminders WHERE id=$1;"
        await self.bot.pool.execute(query, timer["id"])

        event_name = f"{timer['event']}_timer_complete"
        self.bot.dispatch(event_name, timer)

    async def dispatch_timers(self):
        try:
            while not self.bot.is_closed():
                timer = self._current_timer = await self.wait_for_active_timers(days=40)
                now = datetime.datetime.utcnow()

                if timer["expires"] >= now:
                    to_sleep = (timer["expires"] - now).total_seconds()
                    await asyncio.sleep(to_sleep)

                await self.call_timer(timer)
        except asyncio.CancelledError:
            raise
        except (OSError, discord.ConnectionClosed, asyncpg.PostgresConnectionError):
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

    # async def short_timer_optimisation(self, seconds, timer):
    #     await asyncio.sleep(seconds)
    #     event_name = f"{timer['event']}_timer_complete"
    #     self.bot.dispatch(event_name, timer)

    async def create_timer(self, *args, **kwargs):
        when, event, *args = args

        connection = self.bot.pool
        now = datetime.datetime.utcnow()

        timer = Timer.temporary(
            event=event,
            expires=when,
            created=now,
            channel=args[1],
            author=args[0],
            message=args[2],
        )
        delta = (when - now).total_seconds()
        # if delta <= 60:
        #     # a shortcut for small timers
        #     self.bot.loop.create_task(self.short_timer_optimisation(delta, timer))
        #     return timer

        query = """INSERT INTO reminders (event, expires, created, channel, author, message, message_id)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   RETURNING id;
                """

        row = await connection.fetchrow(
            query, event, when, now, args[1], args[0], args[2], kwargs.get("message_id")
        )
        timer.id = row[0]

        # only set the data check if it can be waited on
        if delta <= (86400 * 40):  # 40 days
            self._have_data.set()

        # check if this timer is earlier than our currently run timer
        if self._current_timer and when < self._current_timer["expires"]:
            # cancel the task and re-run it
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

        return timer

    @commands.group(name="reminder", invoke_without_command=True)
    async def reminder(
        self,
        ctx,
        *,
        when: time.UserFriendlyTime(commands.clean_content, default="\u2026"),
    ):

        timer = await self.create_timer(
            when.dt,
            "reminder",
            ctx.author.id,
            ctx.channel.id,
            when.arg,
            created=ctx.message.created_at,
            message_id=ctx.message.id,
        )
        delta = time.human_timedelta(when.dt, source=timer.created_at)
        await ctx.send(
            f"{ctx.author.mention}, in {delta}: {when.arg}",
            allowed_mentions=discord.AllowedMentions(users=True),
        )

    @reminder.command(name="delete")
    async def reminder_delete(self, ctx, *, id: int):
        query = """DELETE FROM reminders
                   WHERE id=$1
                   AND event = 'reminder'
                   AND author = $2
                """

        status = await self.bot.pool.execute(query, id, ctx.author.id)
        if status == "DELETE 0":
            return await ctx.send("There was nothing to do delete with that id.")

        if self._current_timer and self._current_timer['id'] == id:
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

        await ctx.send("Deleted that reminder.")

    @reminder.command(name="list")
    async def reminder_list(self, ctx):
        query = """SELECT id, expires, message
                   FROM reminders
                   WHERE event = 'reminder'
                   AND author = $1
                   ORDER BY expires
                   LIMIT 10;
                """

        records = await self.bot.pool.fetch(query, ctx.author.id)

        if len(records) == 0:
            return await ctx.send("You have no reminders currently.")

        embed = discord.Embed()
        embed.title = "Recent Reminders"

        if len(records) == 10:
            embed.set_footer(text="Showing your 10 recent reminders")
        else:
            embed.set_footer(
                text=f'{len(records)} reminder{"s" if len(records) > 1 else ""}'
            )

        for _id, expires, message in records:
            embed.add_field(
                name=f"{_id}: In {time.human_timedelta(expires)}",
                value=shorten(message, width=512),
                inline=False,
            )

        await ctx.send(embed=embed)

    @Plugin.listener()
    async def on_reminder_timer_complete(self, timer):
        author_id = timer["author"]
        channel_id = timer["channel"]
        message = timer["message"]

        try:
            channel = self.bot.get_channel(channel_id) or (
                await self.bot.fetch_channel(channel_id)
            )
        except discord.HTTPException:
            return

        guild_id = (
            channel.guild.id if isinstance(channel, discord.TextChannel) else "@me"
        )
        message_id = timer["message_id"]
        msg = f"<@{author_id}>, {time.human_timedelta(timer['created'])}: {message}"

        if message_id:
            msg = f"{msg}\n\n<https://discordapp.com/channels/{guild_id}/{channel.id}/{message_id}>"

        try:
            await channel.send(
                msg, allowed_mentions=discord.AllowedMentions(users=True)
            )
        except discord.HTTPException:
            return
