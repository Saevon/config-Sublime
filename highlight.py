'''
Highlights searched text, allowing commands to

Commands:

 * highlight_all:           Highlights the word under the cursor
 * highlight_all_next:      Moves cursor to the next found word (If you have an active search)
     * backwards (bool)     Whether to go down (false) or up (true)
 * highlight_all_history    ?
 * ex_mode                  ?

Settings:

 * vimSearchPanel:        Set if the search panel is open
 * vimSearchPanelEmpty:   Set if the serach panel is currently empty
 * vimExPanel:            Set if the search panel is open
 * vimExPanelEmpty:       Set if the serach panel is currently empty

Keybindings:

 '*'        Search word
 '#'        Search word (backwards)
 ', '       Reset highlight + search
 'n'        Next word
 'N'        Prev word
 '*'        (Visual) Search selected text
 'g*'       Search word (no word boundaries)

Vim Ex Commands
   Note: Some commands auto-end parsing, so trailing text is ignored

 :w     Save file
 :q     Close File
 :99    (END)  Go to line
 :?     Search
 :/     Search
'''
import functools
import re

import sublime
import sublime_plugin

# TODO: Highlight
#    Autoupdate the search as you edit the file
#    Shortcut to Multiselect all highlighted items
#    Multifile search, and next?

#    BUG: Search by word doesn't escape regex chars (neither does search by selected)
#    BUG: undo re-highlights old searches (if you just cleared it)... but redo doesn't re-delete them
# DONE:
#    Move the screen as you search, returning to original location if not found
#    Find nearest word (in the correct direction), rather than starting at the top
#    BUG: search by word removes your cursor if nothing is found (e.g. search an empty space... aka not a word)
#    BUG: if you edit the file, then do 'nN' you go to the wrong positions

# NOTES:
#  *# should both update history

# TODO: VIM:
#  :%s
#  :'<,'>:s
#  :g
#  :gv   select last visual selection
#  :!


# -----------------------------------------------------------------------------


def with_view(func):
    ''' Requires the input view to exist, or else the method is skipped '''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        ''' Wrapper '''
        if not self.input_view:
            return None
        return func(self, *args, **kwargs)
    return wrapper


class InputPanelMixin(object):
    ''' Text input panel'''

    def open_panel(self, window, prompt, name, initial_text=''):
        ''' Creates the input panel '''
        self.__input_panel_name = name

        # The function opens a thread, so the variable assignment isn't
        # guaranteed to succeed first. Give it a starting value
        self.input_view = None
        self.input_view = window.show_input_panel(
            '  {prompt} '.format(prompt=prompt),
            initial_text,
            on_done=self.on_done,
            on_change=self.on_change,
            on_cancel=self.on_cancel,
        )

        self.input_view.settings().set(self.__input_panel_name, True)
        self.input_view.settings().set(self.__input_panel_name + 'Empty', True)

    @with_view
    def check_empty(self, text):
        ''' Updates the 'empty' status of the input panel '''
        is_empty = text == ''

        self.input_view.settings().set(self.__input_panel_name + 'Empty', is_empty)

    def clear_input(self):
        ''' Cleans up the panel '''

        # Settings are tied to the input_panel view, no need to reset
        # (Since its about to be deleted)
        self.input_view = None

    def on_change(self, text):
        ''' Event: User cancels input window '''
        self.check_empty(text)
        self._on_change(text)

    def on_cancel(self):
        ''' Event: User cancels input window '''
        self.clear_input()
        self._on_cancel()

    def on_done(self, text):
        ''' Event: Regex has been written (User input) '''
        # Ensure the panel is reset
        self.clear_input()
        self._on_done(text)

    def noop(self, *args, **kwargs):
        ''' Do Nothing Method '''

    # Users can overwrite these with their callbacks
    _on_done = _on_cancel = _on_change = noop


def valid_regex(string):
    ''' Whether the string is a valid regular expression'''
    try:
        re.compile(string)
    except re.error:
        return False
    return True


CAPS_RE = re.compile(r'[A-Z]')

LEFT_BRACKET_RE = re.compile(r'(?<!\\)\(')
RIGHT_BRACKET_RE = re.compile(r'(?<!\\)\)')


class RegexText(list):
    ''' Used to represent raw text '''
    def __str__(self):
        return '{}'.format(''.join(self))

    def complete(self):
        ''' Text has no children '''
        return str(self)


class RegexState(object):
    ''' Parser Helper '''

    # Sentinels
    Any = object()
    Self = object()
    End = object()

    ALLOWS = Any
    START_RE = END_RE = None
    START_CHAR = END_CHAR = None

    def __init__(self):
        self.children = []
        self.text_state = False

    def add_text(self, text):
        ''' Adds a text token '''
        if not self.text_state:
            self.children.append(
                RegexText()
            )

        self.children[-1].append(text)
        self.text_state = True

    def add_child(self, child):
        ''' Adds a child RegexState '''
        self.text_state = False
        self.children.append(child)

    def __str__(self):
        name = type(self).__name__

        children = []
        for child in self.children:

            if isinstance(child, RegexState):
                children.append(str(child))
            else:
                children.append(str(child))

        if len(children):
            return '<{} {}>'.format(name, ' '.join(children))
        return '<{}>'.format(name)

    @classmethod
    def allowed_states(cls):
        ''' Return the allowed states this can go too '''
        # Figure out which states we can go to
        allowed_states = cls.ALLOWS

        # Replace the special Any sentinel
        if allowed_states == RegexState.Any:
            allowed_states = [
                RegexSet,
                RegexNum,
                RegexGroup,
            ]

        allowed_states = set(allowed_states)

        # Replace the special Self sentinel
        if RegexState.Self in allowed_states:
            allowed_states.remove(RegexState.Self)
            allowed_states.add(cls)

        return allowed_states

    @classmethod
    def lookup(cls):
        ''' Returns the re lookup table '''
        # Create the regex lookup chart
        lookup = {}

        for state in cls.allowed_states():
            lookup[state.START_RE] = state

        return lookup

    def complete(self):
        ''' Returns an iterator of the completed regex '''
        children = []

        if self.START_CHAR is not None:
            children.append(self.START_CHAR)

        # Put in the child text
        for child in self.children:
            children.append(child.complete())

        if self.END_CHAR is not None:
            children.append(self.END_CHAR)

        return ''.join(children)


class RegexSet(RegexState):
    ''' [a-z] Sets '''
    ALLOWS = [
        RegexState.Self,
    ]
    START_RE = re.compile(r'\[')
    END_RE = re.compile(r'\]')
    START_CHAR = '['
    END_CHAR = ']'


class RegexNum(RegexState):
    ''' {0,3} multipliers '''
    ALLOWS = []
    START_RE = re.compile(r'\{')
    END_RE = re.compile(r'\}')
    START_CHAR = '{'
    END_CHAR = '}'


class RegexGroup(RegexState):
    ''' (...) Groups '''
    START_RE = re.compile(r'\(')
    END_RE = re.compile(r'\)')
    START_CHAR = '('
    END_CHAR = ')'


def _parse_completable_regex(text):
    ''' Helper that creates the ParsedTree of the regex '''
    top_state = RegexState()
    states = [top_state]

    while len(text):
        current_state = states[-1]

        if text[0] == '\\':
            # This drops the escape char + the next char
            current_state.add_text(text[:2])
            text = text[2:]
            continue

        # Check if this state just ended
        elif current_state.END_RE and current_state.END_RE.match(text) is not None:
            text = text[1:]
            states.pop()
        else:
            for next_re, result_state in current_state.lookup().items():
                if next_re.match(text):
                    # Start this new state
                    child = result_state()
                    current_state.add_child(child)
                    text = text[1:]

                    states.append(child)
                    break
            else:
                # Useless char, ignore it
                current_state.add_text(text[:1])
                text = text[1:]

    return top_state


def autocomplete_regex(text):
    ''' Tries to autocorrect user input (regex)

    Auto closes any constructs (braces, brackets, square brackets, etc)
    Best used when you want auto-updating search as the user types
        (so they can see their results as they type the group)
    '''
    parsed = _parse_completable_regex(text)

    # Now autocomplete
    corrected = parsed.complete()

    return corrected


WORD_BOUNDARY_RE = re.compile(r'^a\b')


def is_regex_word_boundary(char):
    ''' Returns whether this char breaks a word boundary

    aka if you can put \\b beside it

    '!' will make \\b always fail == False
    'a' will let \\b work == True
    '''
    match = WORD_BOUNDARY_RE.search('a' + char)
    return match is not None


# -----------------------------------------------------------------------------
# Sublime Helpers


class ViewBaseStoreMeta(type):
    ''' Metaclass that uses creates a view Factory '''

    def __init__(cls, name, bases, attrs, **kwargs):
        ''' Catches subclass creation, sets up the metaclass '''
        cls._ALL = {}

        super().__init__(name, bases, attrs, **kwargs)

    def __call__(cls, view, *args, **kwargs):
        ''' Returns the view unique object '''
        uniq_id = view.id()

        obj = cls._ALL.get(uniq_id)
        if obj is None:
            # It isn't stored, use the class constructor (as usual)
            obj = cls._ALL[uniq_id] = super().__call__(*args, view=view, **kwargs)
        else:
            # Its already stored, if the user is passing any arguments update theym
            obj._update(*args, **kwargs)  # pylint: disable=protected-access

        return obj


def sublime_select(view, region):
    ''' Selects the given region within the view '''
    cursor_start = region.begin()
    cursor = sublime.Region(cursor_start, cursor_start)

    view.sel().clear()
    view.sel().add(cursor)

    sublime_show_region(view, region)


def sublime_show_region(view, region):
    ''' Shows the region in the view (not moving if its already visible) '''
    if not view.visible_region().intersects(region):
        view.show_at_center(region)


def closest_visible(selection, visible_region=None, inverted=False):
    ''' Returns the first region which is fully visible.
    If nothing is visible, a random selection is returned
    '''
    if len(selection) == 0:
        # Nothing to choose from...
        return None

    if visible_region is None or len(selection) == 1:
        # Since nothing seems visible, then the very first selection
        # is our default 'closest'
        return selection[0]

    # Find the first region which is withing our viewport
    for region in selection:
        if visible_region.contains(region):
            # We found one inside the viewport!
            return region
        elif not inverted and visible_region.begin() <= region.begin():
            # We've Gone past the viewport, just take the next one
            return region
        elif inverted and visible_region.end() <= region.end():
            # We've gone past the viewport, just take the next one
            return region

    # We've hit the end... loop back to the first one
    return selection[0]


# -----------------------------------------------------------------------------
# Helper Commands


class CloseInputFieldCommand(sublime_plugin.TextCommand):
    ''' Closes any open Input Field '''

    # pylint: disable=too-few-public-methods,unused-argument
    def run(self, edit=None):
        ''' Closes the field '''
        window = self.view.window()
        window.run_command('hide_panel')


# -----------------------------------------------------------------------------
# Plugin Starts here


# Name of the region group when highlighting
HIGHLIGHT_SCOPE = 'vimhighlight'
HIGHLIGHT_GROUP = 'Saevon-HighlightAllPlugin'

HIGHLIGHT_GROUP_TEMP = HIGHLIGHT_GROUP + 'Temp'


class VisibleMatch(object):
    ''' Subclass used to show that this region is special (is the one the viewport should jump to '''
    # pylint: disable=too-few-public-methods

    def __init__(self, region):
        ''' Stores a region '''
        self.region = region


class Search(object):
    ''' Search, Highlight, and Goto for Sublime '''

    def __init__(self, view, group_name, inverted=False):
        ''' Preps the search '''
        self.inverted = inverted
        self.__group_name = group_name

        # Used to figure out the current search location
        self.__current = None

        self.__view = view

    def reset(self):
        ''' Clears the search (highlight + selected?)'''

        # Reset regions
        self.__view.erase_regions(self.__group_name)

    def current_matches(self):
        ''' Returns the current matches (saved) '''
        # Load existing regions
        regions = self.__view.get_regions(self.__group_name)
        return regions

    def add_matches(self, regions):
        ''' Appends the given regions to this search (as a jump + highlight point) '''

        self.__view.add_regions(
            self.__group_name,
            regions + self.current_matches(),
            scope=HIGHLIGHT_SCOPE,
            icon='',
            flags=sublime.DRAW_NO_OUTLINE,
        )

    def remove_matches(self, cursor, subtract=False):
        '''Removes the highligh under the cursor

        difference    Whether to subtract from the match, or remove incompletly

        If the cursor is selecting text, then just clears that part (potentially halving a selection)
        If the cursor is size 0 then clears any match it overlaps
        '''
        matches = self.current_matches()
        kept_matches = []

        for match in matches:
            if cursor.contains(match):
                # Any engulfed matches are always gone
                continue
            if not cursor.intersects(match):
                # auto-keep ones which don't overlap
                kept_matches.append(match)
                continue

            if not subtract:
                # Reset Mode means the entire match is cleared
                # (Default if we don't use subtract mode)

                if match.contains(cursor):
                    # Discard the match under the cursor
                    continue
                kept_matches.append(match)
            else:
                # Subtract Mode means we cut partial matches into pieces

                # Case 1: Cursor is engulfed... Split the match into 2
                if cursor.begin() >= match.begin() and cursor.end() <= match.end():
                    kept_matches += [
                        sublime.Region(match.begin(), cursor.begin()),
                        sublime.Region(cursor.end(), match.end()),
                    ]
                    continue
                # Case 2: Cursor is before (and slightly overlapping the match)
                elif cursor.begin() < match.begin():
                    kept_matches.append(sublime.Region(
                        cursor.end(),
                        match.end(),
                    ))
                # Case 2: Cursor is after (but slightly overlapping the match)
                elif cursor.end() > match.end():
                    kept_matches.append(sublime.Region(
                        match.begin(),
                        cursor.begin(),
                    ))

        # Replace the current set of matches
        self.reset()
        self.add_matches(kept_matches)

    def _find_matches(self, regex, search_zone=None):
        '''
        Finds matches within the view

        search_zone     The zone to limit the search to (optional)
        '''
        # Regex Flags
        flags = 0
        flags |= re.DOTALL

        # Ignore case unless there are capitals
        match = CAPS_RE.search(regex)
        if match is None:
            flags |= re.IGNORECASE

        matched_regions = self.__view.find_all(regex, flags)

        # Filter out empty matches
        matched_regions = list(filter(lambda region: region.end() != region.begin(), matched_regions))

        # If the user wants to limit it to the current selection... we only search within there
        if search_zone:
            # Filter out things that aren't in the given zone
            matched_regions = [region for region in matched_regions if search_zone.contains(region)]

        return matched_regions

    def find_words(self, words, in_selection=False, word_boundary=True):
        ''' Finds the given words'''
        boundary_char = r'\b' if word_boundary else ''

        word_regex = [re.escape(word) for word in words]

        regex = '{boundary_char}({word}){boundary_char}'.format(
            word='|'.join(word_regex),
            boundary_char=boundary_char,
        )

        return self.find(regex, in_selection=in_selection)


    def find(self, regex, autocorrect=False, in_selection=False):
        ''' Finds the given regex

        regex:          Regular Expression to Find
        autocorrect:    Whether to auto-add missing end characters
        in_selection:   Whether to limit the search to the given location
                        Note: If no character is selected (0 size zone) this is ignored
        '''
        search_zone = None
        if in_selection:
            selected = list(self.__view.sel())

            # There must be at least one char to search within...
            # Otherwise we ignore the in_selection option
            selection_size = sum([cursor.size() for cursor in selected])
            if selection_size >= 1:
                search_zone = selected

        # Now autocorrect the user input
        if autocorrect:
            regex = autocomplete_regex(regex)

        # Find the new cursors
        return self._find_matches(
            regex=regex,
            search_zone=search_zone,
        )

    def forwards(self, viewport=None, update_cursors=True):
        ''' Jumps to the subsequent match (based on inversion preferences) '''
        return self.next(inverted=self.inverted, viewport=viewport, update_cursors=update_cursors)

    def backwards(self, viewport=None, update_cursors=True):
        ''' Jumps to the antecedent match (based on inversion preferences) '''
        return self.next(inverted=not self.inverted, viewport=viewport, update_cursors=update_cursors)

    def prev(self, viewport=None, update_cursors=True):
        ''' Jumps to the prev (left and up) match after the cursor '''
        return self.next(inverted=True, viewport=viewport, update_cursors=update_cursors)

    def next(self, inverted=False, viewport=None, update_cursors=True):
        ''' Jumps to the next (right and down) match after the cursor '''
        current_matches = self.current_matches()
        if len(current_matches) == 0:
            # If we don't have anywhere to jump to...
            return

        # Allow the user to have a custom viewport
        # But use the sublime default otherwise
        if viewport is None:
            viewport = self.__view.visible_region()

        # Warning! this is a generator, it won't run the code until the for loop (later)
        #   is finished... don't mutate any of its state/args
        new_cursor_gen = self._next(
            matches=current_matches,
            inverted=inverted,
            viewport=viewport,
            find_visible_only=not update_cursors,
        )

        # Locate the visible cursor
        new_cursors = []
        new_visible = None
        for cursor in new_cursor_gen:
            if isinstance(cursor, VisibleMatch):
                new_visible = cursor.region
                cursor = cursor.region

            new_cursors.append(sublime.Region(cursor.begin(), cursor.begin()))

        if update_cursors:
            # Now swap the cursors to the new ones
            self.__view.sel().clear()
            for cursor in new_cursors:
                self.__view.sel().add(cursor)

        # Show the result of the jump
        if new_visible is not None:
            self.__view.show(new_visible)

    def _next(self, *, matches, inverted, viewport, find_visible_only):
        ''' Loops through and generates a new set of cursors to jump to
        a VisibleMatch() is yielded if that is the best region to show the user
        '''
        matches = list(matches)
        if len(matches) == 0:
            # There is no such thing as 'next'
            return

        # We'll be messing with the list, duplicate it
        cursors = list(self.__view.sel())

        # Invert our jump
        if inverted:
            # Sublime merges adjacent regions, so they cannot overlap
            # THUS inverting it results in a sorted (backwards) list
            cursors = [cursor for cursor in cursors[::-1]]
            matches = matches[::-1]

        # Find the closest cursor to the visible regions
        if len(cursors) == 0:
            # There is no cursor to jump from?
            # Just go to a visible match
            new_visible = closest_visible(matches, viewport, inverted=inverted)

            # And theres no cursors to 'jump'... finish off
            yield VisibleMatch(new_visible)
            return

        # Find the first cursor that is visible
        visible_cursor = closest_visible(cursors, viewport, inverted=inverted)

        # If we just want the visible cursor only (aka only the new viewport focus)
        # Then pretend we only have one cursor... the closest visible one
        if find_visible_only:
            cursors = [visible_cursor]

        # Used when cursors no longer see a match after them
        # They all loop around to the first one
        loop_match = matches[0]

        # The search has Multiple Stages, this ensures we keep circling through them
        # until we're done

        limit = 10000
        while len(matches) and len(cursors) and limit:
            limit -= 1

            # Stage 1: Drop matches that are before ANY Cursors
            while len(matches) and (
                    # Normal means we're going forwards (compare the starts)
                    (not inverted and cursors[0].begin() >= matches[0].begin())
                    # Inverted means we're going backwards (compare the ends)
                    or (inverted and cursors[0].end() <= matches[0].end())
            ):
                # Drop elements before the cursor
                matches.pop(0)

            # Stage 2: Early Abort (no Matches left!)
            if len(matches) == 0:
                # We've exhausted the search
                # Replace all remaining cursors with the looped match

                if visible_cursor in cursors:
                    yield VisibleMatch(loop_match)
                else:
                    yield loop_match
                return

            # Stage 3: Jump cursors that are before the next match (with that match)
            was_visible = False
            while len(cursors) and (
                    (not inverted and cursors[0].begin() <= matches[0].begin())
                    or (inverted and cursors[0].end() >= matches[0].end())
            ):
                # We found the 'visible cursor' note that down
                if cursors[0] == visible_cursor:
                    was_visible = True

                # Replace cursors before the cursor
                cursors.pop(0)

            # All the cursors we just dropped go to this match
            if was_visible:
                yield VisibleMatch(matches[0])
            else:
                yield matches[0]

        # Check for bugs
        assert limit != 0, (
            'Overflowed the search, either there were too many items (over 10000), '
            'or there is an infinite loop bug'
        )


class ViewSearch(Search, metaclass=ViewBaseStoreMeta):
    ''' An individual view gets one unique search that is currently active '''
    def __init__(self, *args, **kwargs):
        super().__init__(*args, group_name=HIGHLIGHT_GROUP, **kwargs)

    def _update(self, inverted=None):
        ''' Updates the search defaults '''
        if inverted is not None:
            self.inverted = inverted


class HighlightNextCommand(sublime_plugin.TextCommand):
    ''' Jumps forward/backward to the next match '''

    # pylint: disable=too-few-public-methods,unused-argument
    def run(self, edit=None, backwards=False):
        ''' Runs the command '''
        search = ViewSearch(self.view)

        # Jump each cursor
        if backwards:
            search.backwards()
        else:
            search.forwards()


class HighlightSelectionCommand(sublime_plugin.TextCommand):
    ''' Highlights the current selection

    auto_boundary   Whether to force a word boundary around each cursor (if possible)
    '''

    # pylint: disable=too-few-public-methods,unused-argument
    def run(self, edit=None, append=False, backwards=False, auto_boundary=False):
        ''' Runs the command '''
        search = ViewSearch(self.view, inverted=backwards)

        if not append:
            search.reset()

        cursors = list(self.view.sel())
        if len(cursors) == 0:
            # Nothing to find...
            return

        selected_chunks = []
        for cursor in cursors:
            text = self.view.substr(cursor)
            escaped = re.escape(text)
            print(escaped)

            # See if we want to do a 'word-based' search
            if auto_boundary:
                # If the char already breaks the boundary, ignore the option
                pre_boundary = r'\b' if not is_regex_word_boundary(text[0]) else ''
                post_boundary = r'\b' if not is_regex_word_boundary(text[-1]) else ''

                escaped = '{pre_boundary}{word}{post_boundary}'.format(
                    word=re.escape(text),
                    pre_boundary=pre_boundary,
                    post_boundary=post_boundary,
                )

            selected_chunks.append(escaped)

        regex = '|'.join(selected_chunks)

        matches = search.find(
            # Search for any of the selected chunks
            regex=regex,
            in_selection=False,
        )

        search.add_matches(matches)


class HighlightWordCommand(sublime_plugin.TextCommand):
    ''' Highlights the word under the cursors

    auto_boundary:  Whether to auto-add \b boundary breaks around the word
    '''

    # pylint: disable=too-few-public-methods,unused-argument
    def run(self, edit=None, append=False, backwards=False, word_boundary=True):
        ''' Runs the command '''
        search = ViewSearch(self.view, inverted=backwards)

        if not append:
            search.reset()

        cursors = list(self.view.sel())
        if len(cursors) == 0:
            # Nothing to find...
            return

        words = []
        for cursor in cursors:
            word_boundary = self.view.word(cursor)
            word = self.view.substr(word_boundary)
            words.append(word)

        # Find the words
        matches = search.find_words(words, word_boundary=word_boundary)

        # Highlight these regions
        search.add_matches(matches)


class ClearAllHighlightCommand(sublime_plugin.TextCommand):
    ''' Clears all the highlights '''

    # pylint: disable=too-few-public-methods,unused-argument
    def run(self, edit=None):
        ''' Runs the command '''
        ViewSearch(self.view).reset()


class ClearHighlightCommand(sublime_plugin.TextCommand):
    ''' Clears the matches under the cursor

    If the cursor is selecting text, then just clears that part (potentially halving a selection)
    If the cursor is size 0 then clears any match it overlaps
    '''

    # pylint: disable=too-few-public-methods,unused-argument
    def run(self, edit=None):
        ''' Runs the command '''
        search = ViewSearch(self.view)

        cursors = list(self.view.sel())

        for cursor in cursors:
            subtract_mode = True
            if cursor.size() == 0:
                subtract_mode = False
                # Always act like we're selecting one char
                # or else its hard to remove 1 char matches
                cursor = sublime.Region(cursor.begin(), cursor.begin() + 1)

            search.remove_matches(cursor, subtract=subtract_mode)


class HighlightPanelCommand(sublime_plugin.TextCommand, InputPanelMixin):
    ''' Creates the Search Input Panel '''

    def _on_change(self, text):
        ''' Event: User typing '''
        # Ignore typing if we aren't autoupdating
        if self.search is None:
            return

        # Reset the original view
        # So the search will center consistently
        self.view.set_viewport_position(self.viewport)

        # Clear temporary searches
        self.search.reset()

        # Now perform the new search
        matches = self.search.find(text, self.autocorrect)

        self.search.add_matches(matches)

        # Jump to the found data
        self.search.forwards(update_cursors=False, viewport=self.visible_region)

    def _on_done(self, text):
        ''' Event: user Input'''

        # Clean up the temporary search
        if self.search:
            self.search.reset()

        # Perform the final search
        search = ViewSearch(
            view=self.view,
            inverted=self.backwards,
        )

        matches = search.find(text, autocorrect=self.autocorrect)

        # Reset the search if we want a clean one
        if not self.append:
            search.reset()

        # Show the items we found
        search.add_matches(matches)

        # Jump to the found data
        # Note: use the saved visible region, since our temporary search moves the viewport around
        search.forwards(viewport=self.visible_region)

    def _on_cancel(self):
        ''' Event: user abort'''

        # Without the temporary search this doesn't change state
        # No need to reset
        if not self.search:
            return

        # Reset the temporary search
        self.search.reset()

        # Reset the original view
        self.view.set_viewport_position(self.viewport)

    # pylint: disable=too-few-public-methods,unused-argument, too-many-arguments
    def run(self, edit=None, backwards=False, autoupdate=True, autocorrect=True, append=True):
        ''' The actual command for sublime to run '''

        # pylint: disable=attribute-defined-outside-init

        # This defines the input menu symbol, showing the direction
        direction_key = '?' if backwards else '/'

        self.backwards = backwards
        self.append = append
        self.autocorrect = autocorrect

        # Store the original state
        self.viewport = self.view.viewport_position()
        self.visible_region = self.view.visible_region()

        self.search = None
        if autoupdate:
            self.search = Search(
                view=self.view,
                # Create a temporary group so we can add it to the full search if needed
                group_name=HIGHLIGHT_GROUP_TEMP,
                inverted=backwards,
            )

        self.open_panel(
            name='vimSearchPanel',
            window=self.view.window(),
            prompt=direction_key,
        )


# TODO: Catch modifications to re-search? (live_update=True)
# class HighlightListener(sublime_plugin.EventListener):

#     def on_modified(self, view):
#         view.run_command('highlight_all', args={
#             'runPrevious': True,
#         })


LINE_RE = re.compile(r'(?P<row>[0-9]+)(:(?P<col>[0-9]+))?')


class ExModeCommand(sublime_plugin.TextCommand, InputPanelMixin):
    ''' Creates the ExMode Input Panel '''

    def _on_done(self, text):
        ''' Event: User Input '''

        # ':row:column' command
        match = LINE_RE.match(text)
        if match:
            col = match.group('col')
            if col is None:
                col = 0
            else:
                col = int(col) - 1
            # cursors in sublime are zero based, but line numbers are 1 based
            line_num = int(match.group('row')) - 1

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

            return None

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

    # pylint: disable=too-few-public-methods,unused-argument
    def run(self, edit=None):
        ''' The actual command for sublime to run '''
        self.open_panel(
            name='vimExPanel',
            window=self.view.window(),
            prompt=':',
        )
