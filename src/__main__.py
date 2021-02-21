import discord

from . import Pls, setup_logging

discord.VoiceClient.warn_nacl = False

with setup_logging():
    Pls().run()