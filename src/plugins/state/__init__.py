from . import error, guild, aboose

def setup(pls):
    for cls in (error.Error,guild.Guild,aboose.Aboose):
        pls.add_cog(cls(pls))
