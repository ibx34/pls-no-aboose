from . import Mod, Reminders, Admin

def setup(pls):
    for cls in (Mod.Mod,Reminders.Reminder,Admin.Admin):
        pls.add_cog(cls(pls))
