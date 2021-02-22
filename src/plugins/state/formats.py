import asyncio

class plural:
    def __init__(self, value):
        self.value = value
    def __format__(self, format_spec):
        v = self.value
        singular, sep, plural = format_spec.partition('|')
        plural = plural or f'{singular}s'
        if abs(v) != 1:
            return f'{v} {plural}'
        return f'{v} {singular}'

def human_join(seq, delim=', ', final='or'):
    size = len(seq)
    if size == 0:
        return ''

    if size == 1:
        return seq[0]

    if size == 2:
        return f'{seq[0]} {final} {seq[1]}'

    return delim.join(seq[:-1]) + f' {final} {seq[-1]}'

class TabularData:
    def __init__(self):
        self._widths = []
        self._columns = []
        self._rows = []

    def set_columns(self, columns):
        self._columns = columns
        self._widths = [len(c) + 2 for c in columns]

    def add_row(self, row):
        rows = [str(r) for r in row]
        self._rows.append(rows)
        for index, element in enumerate(rows):
            width = len(element) + 2
            if width > self._widths[index]:
                self._widths[index] = width

    def add_rows(self, rows):
        for row in rows:
            self.add_row(row)

    def render(self):
        """Renders a table in rST format.
        Example:
        +-------+-----+
        | Name  | Age |
        +-------+-----+
        | Alice | 24  |
        |  Bob  | 19  |
        +-------+-----+
        """

        sep = '+'.join('-' * w for w in self._widths)
        sep = f'+{sep}+'

        to_draw = [sep]

        def get_entry(d):
            elem = '|'.join(f'{e:^{self._widths[i]}}' for i, e in enumerate(d))
            return f'|{elem}|'

        to_draw.append(get_entry(self._columns))
        to_draw.append(sep)

        for row in self._rows:
            to_draw.append(get_entry(row))

        to_draw.append(sep)
        return '\n'.join(to_draw)

async def prompt(self,message, *, timeout=60.0, delete_after=True, reacquire=True, author_id=None):
    if not self.channel.permissions_for(self.me).add_reactions:
        raise RuntimeError('Bot does not have Add Reactions permission.')

    fmt = f'{message}\n\nReact with \N{WHITE HEAVY CHECK MARK} to confirm or \N{CROSS MARK} to deny.'

    author_id = author_id or self.author.id
    msg = await self.send(fmt)

    confirm = None

    def check(payload):
        nonlocal confirm

        if payload.message_id != msg.id or payload.user_id != author_id:
            return False

        codepoint = str(payload.emoji)

        if codepoint == '\N{WHITE HEAVY CHECK MARK}':
            confirm = True
            return True
        elif codepoint == '\N{CROSS MARK}':
            confirm = False
            return True

        return False

    for emoji in ('\N{WHITE HEAVY CHECK MARK}', '\N{CROSS MARK}'):
        await msg.add_reaction(emoji)

    if reacquire:
        await self.release()

    try:
        await self.bot.wait_for('raw_reaction_add', check=check, timeout=timeout)
    except asyncio.TimeoutError:
        confirm = None

    try:
        if reacquire:
            await self.acquire()

        if delete_after:
            await msg.delete()
    finally:
            return confirm