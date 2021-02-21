import collections
import pathlib

import aiohttp
import discord
from discord.ext import commands


from . import config
from .sql import init_db

async def get_extensions():

    found = ["jishaku"]
    base = pathlib.Path("./src/plugins")

    for path in base.glob("*/__init__.py"):
        found.append(str(path.parent).replace("\\", ".").replace("/", "."))

    return found


def mentions():

    return discord.AllowedMentions(everyone=False, roles=False, users=True)


def intents():

    needed = [
        "messages",
        "guilds",
        "members",
        "guild_messages",
        "reactions",
        "dm_messages",
        "dm_reactions",
        "voice_states",
        "presences",
        "bans",
    ]

    intents = discord.Intents.none()

    for name in needed:
        setattr(intents, name, True)

    return intents


async def get_pre(pls, message):

    return commands.when_mentioned_or(config.PREFIX)(pls, message)
    # if not message.guild:
    #     return commands.when_mentioned_or(*dapper.config['prefixes'])(dapper, message)
    # try:
    #     guild_prefix = dapper.prefixes[message.guild.id]
    #     if guild_prefix:
    #         return commands.when_mentioned_or(*guild_prefix)(dapper, message)
    # except KeyError:
    #     return commands.when_mentioned_or(*dapper.config['prefixes'])(dapper, message)


def start_session(pls):

    return aiohttp.ClientSession(loop=pls.loop)


class Pls(commands.AutoShardedBot):
    def __init__(self):
        super().__init__(
            command_prefix=get_pre,
            case_insensitive=True,
            reconnect=True,
            status=discord.Status.online,
            intents=intents(),
            allowed_mentions=mentions(),
            shard_id=0,
            shard_count=1,
        )

        self.pool = None
        self.session = None
        self.redis = None
        self.config = config
        self.yellow = discord.Color.gold()
        self.configs = {}
        self.cases = collections.defaultdict(lambda: 0)
        self.prefixes = {}
        # self.remove_command("help")

    async def start(self):
        self.session = start_session(self)
        self.pool = await init_db(db_config=config.DATABASE, size=150)

        for name in await get_extensions():
            self.load_extension(name)

        await super().start(config.TOKEN)

    async def process_commands(self, message):

        ctx = await self.get_context(message, cls=commands.Context)
        if ctx.command is None:
            return

        await self.invoke(ctx)

    async def get_or_fetch_member(self, guild, member_id):
        member = guild.get_member(member_id)
        if member is not None:
            return member

        shard = self.get_shard(guild.shard_id)
        if shard.is_ws_ratelimited():
            try:
                member = await guild.fetch_member(member_id)
            except discord.HTTPException:
                return None
            else:
                return member

        members = await guild.query_members(limit=1, user_ids=[member_id], cache=True)
        if not members:
            return None
        return members[0]

if __name__ == "__main__":
    Pls().run()
