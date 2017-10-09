import sublime
import sublime_plugin
import re

# TODO: when doing *# in Visual mode the cursor should select everything from the previously selected area
#     to the new word position
# TODO: find nearest word, rather than starting at the top
# TODO: if you edit the file, then do 'nN' you go to the wrong positions
# DONE: move the screen as you search, returning to original location if not found

# NOTES:
#  *# both update history

# TODO: VIM:
#  :91 go to line/col
#  :wq
#  :%s
#  :'<,'>:s
#  :g
#  :!


def valid_regex(string):
    try:
        re.compile(string)
    except re.error:
        return False

    return True


# Name of the region group when highlighting
HIGHLIGHT_GROUP = 'Saevon-HighlightAllPlugin'


def find_relevant_selection(selection, visible_region=None):
    # See if we can find the first region which is fully visible
    if visible_region is not None:
        for region in selection:
            if visible_region.contains(region):
                return region

    # Default is the first selection we find
    return selection[0]


class Selections(object):

    _ALL = {}

    @classmethod
    def create(cls, uniq_id):
        obj = cls._ALL.get(uniq_id)
        if obj is None:
            obj = cls(uniq_id)

        return obj

    def __init__(self, uniq_id):
        self.uniq_id = uniq_id

        self.clear()
        self.inverted = False

        self._ALL[uniq_id] = self

    def to_valid_index(self, index):
        if len(self.selections) == 0:
            return 0

        # Loop the index around
        return index % len(self.selections)

    def get(self, index=None, default=None):
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
        self.selections = []
        self.index = 0


class SearchHistory(Selections):

    _ALL = {}


def sublime_select(view, region):
    cursor_start = region.begin()
    cursor = sublime.Region(cursor_start, cursor_start)

    view.sel().clear()
    view.sel().add(cursor)

    sublime_show_region(view, region)


def sublime_show_region(view, region):
    if not view.visible_region().intersects(region):
        view.show_at_center(region)


class HighlightAllNextCommand(sublime_plugin.TextCommand):
    def run(self, edit=None, **kwargs):
        selections = Selections.create(self.view.id())
        next_sel = selections.prev() if kwargs.get('backwards', False) else selections.next()

        if next_sel is not None:
            return sublime_select(self.view, next_sel)

        # See if instead there was a previous search
        history = SearchHistory.create(self.view.id())
        regex = history.cur()
        if regex is not None:
            # TODO: do previous search
            return

        # See if theres an old set of regions
        # So we can recover any old highlights
        regions = self.view.get_regions(HIGHLIGHT_GROUP)
        if len(regions) == 0:
            return


        # Recover old regions
        # TODO:



class HighlightAllHistoryCommand(sublime_plugin.TextCommand):
    def run(self, edit=None):
        print('!!')

        cur_line = self.view.substr(
            self.view.line(sublime.Region(0, 0))
        )
        print('!!' + cur_line)


class HighlightAllCommand(sublime_plugin.TextCommand):

    CAPS_RE = re.compile(r'[A-Z]')
    LEFT_BRACKET_RE = re.compile(r'(?<!\\)\(')
    RIGHT_BRACKET_RE = re.compile(r'(?<!\\)\)')


    def on_change(self, data):
        if not self.autoupdate:
            return

        self.view.run_command('clear_all_highlights')
        found = self.search(data)
        if len(found) == 0:
            self.restore()
        else:
            self.highlight(found)
            self.view.show_at_center(found[0])

    def on_done(self, data):
        self.full_search(data)

    def on_cancel(self):
        if self.autoupdate:
            self.restore()
            self.view.run_command('clear_all_highlights')

    def full_search(self, regex):
        # Use the previous search if there was one
        if not regex:
            history = SearchHistory.create(self.view.id())
            regex = history.cur()
            print(regex)

        # If there isn't a search... abort
        if not regex:
            return

        found = self.search(regex)

        self.highlight(found)
        self.select(found)

        # Save any actual searches
        self.save_search(regex)

    def search(self, regex):
        # Validate and try to autocorrect regex
        regex = self.correct_regex(regex)

        # Regex Flags
        flags = 0
        flags |= re.DOTALL

        # Ignore case unless there are capitals
        match = HighlightAllCommand.CAPS_RE.search(regex)
        if match is None:
            flags |= re.IGNORECASE

        selected = self.view.sel()

        matched_regions = self.view.find_all(regex, flags)

        # Filter out empty matches
        matched_regions = list(filter(lambda region: region.end() != region.begin(), matched_regions))

        # TODO: highlight only selected text should be an option passed in
        #   Since '*' should not care about selection

        # Filter out things that haven't been selected
        # Only do this if we have selected multiple characters
        if len(selected) >= 2 or (len(selected) == 1 and selected[0].size() >= 1):
            matched_regions = list(filter(lambda region: selected.contains(region), matched_regions))

        return matched_regions

    def correct_regex(self, regex):
        left_brackets = len(HighlightAllCommand.LEFT_BRACKET_RE.findall(regex))
        right_brackets = len(HighlightAllCommand.RIGHT_BRACKET_RE.findall(regex))

        while not valid_regex(regex) and left_brackets > right_brackets:
            right_brackets += 1
            regex += ')'

        # Now correct trailing escape chars
        escapes = len(regex) - len(regex.rstrip('\\'))
        if escapes % 2 == 1:
            regex += '\\'

        return regex

    def highlight(self, matched_regions):
        # Keep any old highlights
        matched_regions += self.view.get_regions(HIGHLIGHT_GROUP)

        self.view.add_regions(HIGHLIGHT_GROUP, matched_regions, 'vimhighlight', '', sublime.DRAW_NO_OUTLINE)

    def update_jump_points(self, matched_regions):
        selections = Selections.create(self.view.id())
        # TODO: merge already searched regions
        selections.clear()
        selections.push(*matched_regions)

    def select(self, matched_regions):
        selections = Selections.create(self.view.id())
        self.update_jump_points(matched_regions)

        if selections.cur() is not None:
            sublime_select(self.view, selections.cur())

    def clear(self):
        self.view.erase_regions(HIGHLIGHT_GROUP)

    def run_previous(self):
        history = SearchHistory.create(self.view.id())
        regex = history.cur()

        if regex is not None:
            found = self.search(regex)
            self.clear()
            self.highlight(found)
            self.update_jump_points(found)

    def save_search(self, data):
        history = SearchHistory.create(self.view.id())
        history.clear()
        history.push(data)

    def restore(self):
        '''
        Restores the original cursor and state to the one right before the search
        '''
        selections = Selections.create(self.view.id())
        selections.clear()

        # Restore the Viewpoint
        self.view.set_viewport_position(self.original_view)

    def run(self, edit=None, **kwargs):
        if kwargs is None:
            kwargs = {}

        # Save whether we need the search to be inverted
        selections = Selections.create(self.view.id())
        selections.inverted = kwargs.get('backwards', False)

        # You can also specify exactly what to search
        regex = kwargs.get('regex', False)
        if regex is not False:
            return self.full_search(regex)

        # Update as you type
        self.autoupdate = kwargs.get('autoupdate', True)
        if self.autoupdate:
            selections.clear()
            self.original_view = self.view.viewport_position()

        # We could also be trying to rerun a search
        if kwargs.get('runPrevious', False):
            return self.run_previous()

        # Don't show a menu if we're trying to just find the word under the cursor
        if kwargs.get('word', False):
            # VIM CHANGE: If the user is in visual mode, then we want to search for that instead
            is_visual = False
            for cursor in self.view.sel():
                if len(cursor) >= 1:
                    is_visual = True
                    break

            # TODO: figure out where the cursor is to go to closest position?
            # TODO: Cache results? in case the word is the same
            selections.clear()

            words = []
            for cursor in self.view.sel():
                if is_visual:
                    # In visual mode we just take what the user selected
                    word_region = cursor
                else:
                    # Otherwise we grab the word under the cursor
                    word_region = self.view.word(cursor.end())


                word = self.view.substr(word_region)
                words.append(word)

            # TODO: for now we take just the wo
            word = words[0]

            if is_visual:
                # TODO: escape special chars
                regex = '|'.join([r'\<{0}\>'.format(word) for word in words])
            else:
                regex = '|'.join([r'\<{0}\>'.format(word) for word in words])

            # Also reset the selections or else we'll only search within them
            self.view.sel().clear()

            # Make the search only match exact words
            return self.full_search(regex)

        # This defines the input menu symbol, showing the direction
        direction_key = '?' if selections.inverted else '/'

        # Show a menu to type the search into
        view = self.view.window().show_input_panel(
            '  {0} '.format(direction_key),
            '',
            on_done=self.on_done,
            on_change=self.on_change,
            on_cancel=self.on_cancel,
        )
        view.settings().set('vimSearchPanel', True)


class ClearAllHighlightsCommand(sublime_plugin.TextCommand):
    def run(self, edit=None):
        selections = Selections.create(self.view.id())
        selections.clear()

        history = SearchHistory.create(self.view.id())
        history.clear()

        self.view.erase_regions(HIGHLIGHT_GROUP)


# class HighlightListener(sublime_plugin.EventListener):

#     def on_modified(self, view):
#         view.run_command('highlight_all', args={
#             'runPrevious': True,
#         })




import re


LINE_RE = re.compile(r'(?P<row>[0-9]+)(:(?P<col>[0-9]+))?')


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

        # ':row:column' command
        match = LINE_RE.match(text)
        if match:
            # cursors in sublime are zero based, but line numbers are 1 based
            line_num = int(match.group('row')) - 1
            col = int(match.group('col')) - 1

            cursor = self.view.text_point(line_num, 0)

            # set the Column
            line = self.view.line(cursor)
            cursor = cursor + col
            if cursor > line.end():
                # Vintage mode needs this -1 or else it would be past the end
                cursor = line.end() - 1

            self.view.sel().clear()
            self.view.sel().add(sublime.Region(cursor))

            self.view.show_at_center(cursor)

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


