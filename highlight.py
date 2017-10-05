import sublime
import sublime_plugin
import re

# TODO: when doing *# in Visual mode the cursor should select everything from the previously selected area
#     to the new word position
# TODO: find nearest word, rather than starting at the top
# TODO: if you edit the file, then do 'nN' you go to the wrong positions
# TODO: move the screen as you search, returning to original location if not found

# NOTES:
#  *# both update history

# TODO: VIM:
#  :91 go to line
#  :wq
#  :%s
#  :'<,'>:s
#  :g
#  :!


# Name of the region group when highlighting
HIGHLIGHT_GROUP = 'Saevon-HighlightAllPlugin'

# Flags for RE that need to be put at the beginning of the RE
# Used when you can't provide RE flags from the sublime package
# TODO: see if re.DOTALL, re.IGNORECASE etc work instead
RE_FLAGS = {
    'DOTALL': r'(?s)',
    'IGNORECASE': r'(?i)',
    'MULTILINE': r'(?m)',
}


class Selections(object):

    __ALL = {}

    @classmethod
    def create(_class, id):
        obj = _class.__ALL.get(id)
        if obj is None:
            obj = _class(id)

        return obj

    def __init__(self, id):
        self.id = id

        self.clear()

        self.__ALL[id] = self

    def to_valid_index(self, index):
        if len(self.selections) == 0:
            return 0

        # Loop the index around
        return index % len(self.selections)

    def get(self, index=None, default=None):
        obj = None

        if index is None:
            index = self.index
        index = self.to_valid_index(index)

        try:
            return self.selections[index]
        except IndexError:
            return default

    def cur(self):
        return self.get()

    def prev(self):
        if self.inverted:
            return self._next()
        else:
            return self._prev()

    def next(self):
        if self.inverted:
            return self._prev()
        else:
            return self._next()

    def _next(self):
        self.index += 1
        self.index = self.to_valid_index(self.index)
        return self.get()

    def _prev(self):
        self.index -= 1
        self.index = self.to_valid_index(self.index)
        return self.get()

    def push(self, *args):
        self.selections += args

    def clear(self):
        self.inverted = False
        self.selections = []
        self.index = 0


class SearchHistory(Selections):

    __ALL = {}


def sublime_select(view, region):
    cursor_start = region.begin()
    cursor = sublime.Region(cursor_start, cursor_start)

    view.sel().clear()
    view.sel().add(cursor)

    if not view.visible_region().intersects(region):
        view.show_at_center(cursor)


class HighlightAllNextCommand(sublime_plugin.TextCommand):
    def run(self, edit=None, **kwargs):
        selections = Selections.create(self.view.id())
        next = selections.prev() if kwargs.get('backwards', False) else selections.next()

        if next is not None:
            sublime_select(self.view, next)


class HighlightAllHistoryCommand(sublime_plugin.TextCommand):
    def run(self, edit=None):
        print('!!')

        cur_line = self.view.substr(
            self.view.line(sublime.Region(0, 0))
        )
        print('!!' + cur_line)


class HighlightAllCommand(sublime_plugin.TextCommand):

    CAPS_RE = re.compile(r'[A-Z]')

    def on_change(self, data):
        pass

    def on_done(self, data):
        self.view.settings().set('vimSearchPanel', False)
        self.search(data)

    def search(self, data):
        flags = ''
        flags += RE_FLAGS['DOTALL']

        # Ignore case unless there are capitals
        if HighlightAllCommand.CAPS_RE.match(data) is None:
            # TODO this fails I think...
            flags += RE_FLAGS['IGNORECASE']

        selection = self.view.sel()

        regions = self.view.find_all(data, sublime.IGNORECASE)

        # Filter out things that haven't been selected
        if len(selection) >= 2 or selection[0].size() >= 1:
            regions = list(filter(lambda region: selection.contains(region), regions))

        # Keep any old highlights
        regions += self.view.get_regions(HIGHLIGHT_GROUP)

        self.view.add_regions(HIGHLIGHT_GROUP, regions, 'vimhighlight')

        # TODO: merge already searched regions
        selections = Selections.create(self.view.id())
        selections.push(*regions)

        if selections.cur() is not None:
            sublime_select(self.view, selections.cur())

    def on_cancel(self):
        self.view.settings().set('vimSearchPanel', False)

    def run(self, edit=None, **kwargs):
        if kwargs is None:
            kwargs = {}

        # Save whether we need the search to be inverted
        selections = Selections.create(self.view.id())
        selections.inverted = kwargs.get('backwards', False)

        # You can also specify exactly what to search
        regex = kwargs.get('regex', False)
        if regex is not False:
            return self.search(regex)

        # Don't show a menu if we're trying to just find the word under the cursor
        if kwargs.get('word', False):
            # Always reset to continue the search properly
            # TODO: Cache results? in case the word is the same
            selections.clear()

            cursor_end = self.view.sel()[0].end()
            word = self.view.substr(self.view.word(cursor_end))

            # Make sure to ignorecase
            word = word.lower()

            # Make the search only match exact words
            return self.search('\<{0}\>'.format(word))

        # This defines the input menu symbol, showing the direction
        direction_key = '?' if selections.inverted else '/'

        # Show a menu to type the search into
        self.view.settings().set('vimSearchPanel', True)
        self.view.window().show_input_panel(
            '  {0} '.format(direction_key),
            '',
            on_done=self.on_done,
            on_change=self.on_change,
            on_cancel=self.on_cancel,
        )


class ClearAllHighlightsCommand(sublime_plugin.TextCommand):
    def run(self, edit=None):
        selections = Selections.create(self.view.id())
        selections.clear()

        self.view.erase_regions(HIGHLIGHT_GROUP)


class HighlightListener(sublime_plugin.EventListener):

    def on_modified(self, view):
        view.run_command('highlight_all', args={
            'runPrevious': True,
        })




import re


LINE_RE = re.compile(r'[0-9]+')


class CloseInputFieldCommand(sublime_plugin.TextCommand):
    def run(self, edit=None):
        window = self.view.window()
        window.run_command('hide_panel')

        # TODO: this doesn't change mode, should go back to the original one
        # window.run_command('exit_insert_mode')


class ExModeCommand(sublime_plugin.TextCommand):

    def check_empty(self, text):
        # This can be called before the panel has been "created"
        # so we need to cover that case
        if not self.input_view:
            return

        is_empty = text == ''

        self.input_view.settings().set('vimExPanelEmpty', is_empty)

    def clear_input(self):
        pass

    def on_change(self, text):
        self.check_empty(text)

    def on_cancel(self):
        self.clear_input()

    def on_done(self, text):
        # Ensure the panel is reset
        self.clear_input()

        if LINE_RE.match(text):
            # cursors in sublime are zero based, but line numbers are 1 based
            line_num = int(text) - 1

            cursor = self.view.text_point(line_num, 0)

            self.view.sel().clear()
            self.view.sel().add(sublime.Region(cursor))
            self.view.show(cursor)
            return

        while len(text):
            char, text = text[0], text[1:]

            if char == "w" and self.view.is_dirty():
                self.view.run_command('save')
            elif char == "q":
                self.view.window().run_command('close')
            elif char == "?":
                return self.view.run_command(
                    'highlight_all',
                    args={
                        "backwards": True,
                        "regex": text,
                    }
                )
            elif char == "/":
                return self.view.run_command(
                    'highlight_all',
                    args={
                        "regex": text,
                    }
                )

    def run(self, edit=None, **kwargs):
        self.input_view = self.view.window().show_input_panel(
            '  : ',
            '',
            on_done=self.on_done,
            on_change=self.on_change,
            on_cancel=self.on_cancel,
        )
        self.input_view.settings().set('vimExPanel', True)
        self.input_view.settings().set('vimExPanelEmpty', True)


