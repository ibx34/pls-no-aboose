from . import error, guild, aboose, logging

def setup(pls):
    for cls in (error.Error,guild.Guild,aboose.Aboose,logging.Logger):
        pls.add_cog(cls(pls))
