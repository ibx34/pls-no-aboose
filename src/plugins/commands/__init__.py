from . import Mod

def setup(dapper):
    for cls in (Mod.Mod,):
        dapper.add_cog(cls(dapper))
