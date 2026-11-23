import sys

try:
    import curses
except ImportError:
    curses = None


class Back(Exception):
    pass


def terminal_text(value):
    return ''.join(ch if ch.isprintable() else repr(ch)[1:-1] for ch in str(value))


class Menu:
    def __init__(self, screen=None):
        self.screen = screen
        self.accent = 0
        if screen is not None and curses.has_colors():
            try:
                curses.start_color()
                curses.use_default_colors()
                curses.init_pair(1, curses.COLOR_CYAN, -1)
                self.accent = curses.color_pair(1)
            except curses.error:
                pass

    def draw(self, title, detail, lines, footer):
        screen = self.screen
        screen.erase()
        height, width = screen.getmaxyx()
        def write(y, label, style=0):
            if y < height - 1 and width > 2:
                try:
                    screen.addnstr(y, 1, terminal_text(label), width - 2, style)
                except curses.error:
                    pass
        write(0, ' REPORT WIZARD ', curses.A_REVERSE | curses.A_BOLD | self.accent)
        write(2, title, curses.A_BOLD | self.accent)
        write(3, detail)
        for y, (label, selected) in enumerate(lines, 5):
            write(y, label, curses.A_REVERSE if selected else 0)
        write(height - 2, footer, curses.A_DIM)
        screen.refresh()

    def choose(self, title, detail, options):
        query, position = '', 0
        while True:
            matches = [i for i, label in enumerate(options) if query.casefold() in label.casefold()]
            position = min(position, max(0, len(matches) - 1))
            if self.screen is None:
                print(f'\n{title}\n{detail}')
                print('\n'.join(f' {j + 1:>3}  {terminal_text(options[i])}' for j, i in enumerate(matches[:30])))
                answer = input('Number, /search to filter, or :back > ').strip()
                if answer == ':back':
                    raise Back
                if answer.startswith('/'):
                    query = answer[1:]
                if answer.isdecimal() and 1 <= int(answer) <= min(30, len(matches)):
                    return matches[int(answer) - 1]
                continue
            page = max(1, self.screen.getmaxyx()[0] - 8)
            first = max(0, position - page + 1)
            visible = [(options[i], j == position) for j, i in enumerate(matches[first:first+page], first)]
            if not visible:
                visible = [('No matching options', False)]
            self.draw(title, detail, [('Search: ' + query, False)] + visible,
                      f'{len(matches)}/{len(options)}   ↑↓ move   Enter select   Type to filter   Esc back')
            key = self.screen.get_wch()
            if key in ('\n', '\r', curses.KEY_ENTER) and matches:
                return matches[position]
            if key in ('\x1b', '\x03'):
                raise Back
            if key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_PPAGE, curses.KEY_NPAGE):
                move = {curses.KEY_UP:-1, curses.KEY_DOWN:1, curses.KEY_PPAGE:-page, curses.KEY_NPAGE:page}
                position = max(0, position + move[key])
            elif key in (curses.KEY_BACKSPACE, '\x7f', '\b'):
                query, position = query[:-1], 0
            elif key == '\x15':
                query, position = '', 0
            elif isinstance(key, str) and key.isprintable():
                query += key
                position = 0

    def ask(self, title, detail, default=''):
        if self.screen is None:
            print(f'\n{title}\n{detail}')
            value = input(f'[{terminal_text(default)}] (:back to cancel) > ')
            if value == ':back':
                raise Back
            return value or default
        value = ''
        while True:
            width = max(12, self.screen.getmaxyx()[1] - 8)
            self.draw(title, detail, [('Suggested: ' + default, False), ('> ' + value[-width:], True)],
                      'Enter accept   Ctrl-U clear   Esc back')
            key = self.screen.get_wch()
            if key in ('\n', '\r', curses.KEY_ENTER):
                return value or default
            if key in ('\x1b', '\x03'):
                raise Back
            if key in (curses.KEY_BACKSPACE, '\x7f', '\b'):
                value = value[:-1]
            elif key == '\x15':
                value = ''
            elif isinstance(key, str) and key.isprintable():
                value += key

    def message(self, title, detail):
        self.choose(title, '', [detail])

    def review(self, title, detail, lines, action='Apply changes'):
        return self.choose(title, detail, [action, 'Cancel', *lines]) == 0


def interactive(callback, plain):
    if plain or curses is None or not sys.stdin.isatty() or not sys.stdout.isatty():
        return callback(Menu())
    def run(screen):
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        screen.keypad(True)
        return callback(Menu(screen))
    return curses.wrapper(run)
