import discord
from discord.ext import commands

from ... import Plugin, config


def on_cooldown(cooldown):
    async def predicate(ctx):
        if ctx.author.id in config.DEVS:
            return True

        cd = await ctx.bot.redis.pttl(
            f"{ctx.author.id}-{ctx.guild.id}-{ctx.command.qualified_name}"
        )
        if cd == -2:

            await ctx.bot.redis.execute(
                "SET",
                f"{ctx.author.id}-{ctx.guild.id}-{ctx.command.qualified_name}",
                "cooldown",
                "EX",
                cooldown,
            )
            return True

        raise commands.CommandOnCooldown(retry_after=cd / 1000, cooldown=None)

    return commands.check(predicate)


def is_dev():
    async def predicate(ctx):
        if ctx.author.id in ctx.bot.config.devs:
            return True

        raise NotADev()

    return commands.check(predicate)


class NotADev(commands.CommandError):
    def __init__(self):
        super().__init__(f"Only devs can use this command.")


class Error(Plugin):

    @Plugin.listener()
    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, "on_error"):
            return

        errors = (
            commands.NoPrivateMessage,
            commands.CommandInvokeError,
            commands.UserInputError,
        )
        custom_errors = NotADev

        if isinstance(error, errors):
            await ctx.send(error)
        elif isinstance(error, discord.Forbidden):
            pass
        elif isinstance(error, commands.NotOwner):
            await ctx.send("```css\n[This is an owner only command.]```")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"```css\n[Invalid argument. Did you type it correct?]```")
        elif isinstance(error, commands.TooManyArguments):
            await ctx.send(f"```css\n[Too many arguments. Try less?]```")
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(f"```css\n[{error}]```")
        elif isinstance(error, commands.DisabledCommand):
            await ctx.send(f"```css\n[{ctx.command} is disabled.]```")
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(
                f'```css\n[I need the permission {", ".replace(error.missing_perms)}. You can check my role or channel overrides to find permissions.]```'
            )
        elif isinstance(error, commands.CommandOnCooldown):
            seconds = error.retry_after
            seconds = round(seconds, 2)
            hours, remainder = divmod(int(seconds), 3600)
            minutes, seconds = divmod(remainder, 60)
            await ctx.send(
                f"You are on cooldown for **{hours}**h **{minutes}**m **{seconds}**sec"
            )
        elif isinstance(error, custom_errors):
            await ctx.send(error)
        else:
            print(error)