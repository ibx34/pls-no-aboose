from . import error

def setup(pls):
    for cls in (error.Error,):
        pls.add_cog(cls(pls))
