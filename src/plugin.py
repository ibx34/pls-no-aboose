from discord.ext import commands


class Plugin(commands.Cog):
    def __init__(self, pls):
        self.pls = pls
