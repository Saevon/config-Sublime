#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
'''
Shows all the vi marks that exist

Part of the VIE packages: VintageExtended

* Can load bookmarks (across views)
* Can show all bookmarks (across views)
* Can use Vintage Bookmarks
* Works with Split Panes (but can't preview properly)
* Works with visual selections

Commands

 * vie_show_all_bookmarks
 * vie_delete_bookmark
 * vie_create_bookmark
 * vie_select_bookmark
 * vie_clear_bookmarks

 ⌘p VieMarks: Show
   * Shows any defined items

TODO: This is broken for split screen
  (You can't seem to preview across panes)

TODO: This should work as a motion command, so you could do:
      d`m to delete to a mark
      v`m to delete to select to a mark
      c`m    y`m
      :marks

TODO: add ' which is linewise marks
      'a   go to line of the mark 'a'
      d'a   go to line of the mark 'a'
TODO: go to next/prev mark
      ]'  Next
      ['  Prev
TODO: If you're "at" a mark then showing the list pre-selects the current mark
TODO:
     `` Jump Back to last mark (charwise)
     '' Jump Back to last mark (linewise)
 TODO: Survive sublime_exit
'''


import itertools
import functools
import string

import sublime
import sublime_plugin

from User.sublime_helpers import MetaWindowFactory, MetaViewFactory, Viewport, sublime_is_visual, sublime_is_multiselect, pairwise, QuickPanelFinder


# --------------------------------------------------------------------------------------------------
# Commands

class VieShowAllBookmarks(sublime_plugin.TextCommand):
    ''' Shows a panel with all the names marks '''
    def run(self, edit=None):
        ''' Runs the command '''
        bookmarker = VieMarkPanel(view=self.view)
        bookmarker.open_marks_panel(self.view)


class VieDeleteBookmark(sublime_plugin.TextCommand):
    ''' Deletes the chosen mark under the panel '''
    def run(self, edit=None):
        ''' Runs the command '''
        bookmarker = VieMarkPanel(view=self.view)
        bookmarker.delete_selected()


class VieCreateBookmark(sublime_plugin.TextCommand):
    ''' Creates a new bookmark from the selection '''
    def run(self, edit=None, character=None):
        ''' Runs the command '''
        selection_regions = [selection for selection in self.view.sel()]

        bookmarker = VieBookmarker(view=self.view)
        bookmarker.add_mark(
            character=character,
            view=self.view,
            regions=selection_regions,
        )


class VieSelectBookmark(sublime_plugin.TextCommand):
    ''' Re-Selects a bookmark '''
    def run(self, edit=None, character=None, select=True):
        ''' Runs the command '''
        bookmarker = VieBookmarker(view=self.view)

        bookmarker.go_to_mark(character=character, select=select)


class VieClearBookmarks(sublime_plugin.TextCommand):
    ''' Deletes all marks ever '''
    def run(self, edit=None):
        ''' Runs the command '''
        bookmarker = VieBookmarker(view=self.view)
        bookmarker.delete_all_marks()


# --------------------------------------------------------------------------------------------------


class VieMarkPanel(metaclass=MetaViewFactory):
    ''' Panel allowing the user to select and preview existing marks '''

    def __init__(self):
        self.current_selection = None
        self.viewport = None
        self.choices = []
        self.panel = None
        self.line_preview = True

        self.bookmarker = VieBookmarker(view=self.view)

    def reset(self):
        ''' Reset the entire bookmarks panel '''
        self.current_selection = None
        self.viewport = None
        self.panel = None

        for view in self.view.window().views():
            view.erase_regions("vi_bookmarks_highlight")

    def open_marks_panel(self, view):
        '''
        Opens the bookmark panel

        @public
        '''
        self.reset()
        self.viewport = Viewport(view=self.view)

        self.choices = list(self.bookmarker.iter_marks())

        # Show all the bookmarks in a panel
        self.current_selection = 0

        QuickPanelFinder(view=self.view).listen(self.on_open_panel)
        self.view.window().show_quick_panel(  # pylint: disable=no-member
            # items
            [mark.pretty(full_line=self.line_preview) for mark in self.choices],
            # on_done
            self.on_done,
            # flags
            sublime.MONOSPACE_FONT | sublime.KEEP_OPEN_ON_FOCUS_LOST,
            # selected_index
            0,
            # on_highlighted
            self.on_highlighted,
        )

    def on_open_panel(self, view):
        ''' When the quickpanel is finally opened '''
        self.panel = view

    def delete_selected(self):
        '''
        Deletes the selected region in the quickpanel
        Does nothing if the quickpanel isn't open

        @public
        '''
        if self.current_selection is None:
            return

        mark = self.choices[self.current_selection]

        self.bookmarker.delete_mark(mark=mark)
        self.close_panel()

    def close_panel(self):
        '''
        Closes the input panel if its not there

        @public
        '''
        self.view.window().run_command("hide_overlay", {"cancel": True})  # pylint: disable=no-member

    #------------------------------------
    # Events: Quickpanel

    def on_done(self, selected_index):
        ''' Event: user selected / aborted '''
        if selected_index == -1:
            # aborted
            self.viewport.load()
        else:
            # selected
            mark = self.choices[selected_index]
            self.bookmarker.go_to_mark(mark=mark, select=True)

        # Reset everything
        self.reset()

    def on_highlighted(self, selected_index):
        ''' Event: User moved to a new entry '''
        self.current_selection = selected_index

        # Selected Item was Changed
        mark = self.choices[selected_index]
        self.bookmarker.go_to_mark(mark=mark, select=False, full_line=self.line_preview)

        # Since this is a preview, we need to refocus the quickpanel
        self.panel.window().focus_view(self.panel)



#
# ---------------------------------------------------------
#
#


def mark_or_character(func):
    '''
    Allows a method to accept either a character, or an internal mark
    '''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        mark = kwargs.get('mark', None)
        if not mark:
            try:
                character = kwargs.pop('character')
            except KeyError:
                raise ValueError("You need either a 'mark' or 'character' kwarg") from None
            kwargs['mark'] = self.get_mark(character)

        return func(self, *args, **kwargs)

    return wrapper


class VieBookmarker(metaclass=MetaWindowFactory):
    '''
    Bookmarks API
    '''

    ALLOWED_MARKS = list(itertools.chain(
        string.ascii_lowercase,
        string.ascii_uppercase,
        string.whitespace,
        (
            set(string.punctuation)
            # Those two are used for special commands
            #   Thus are invalid mark registers
            - set("`'")
        ),

        # You can use these, but they're also
        #  used by the visual stack
        # "1234567890",
    ))

    #------------------------------------------------------------------------------------------------
    # Public API

    def get_mark(self, character):
        ''' Gets info about the mark under the character '''
        if character is None:
            return

        # Only allow a mark to be in one view
        # Otherwise multiselect really weird
        view = None
        for view in self.window.views():
            regions = view.get_regions("bookmark_" + character)

            if len(regions) >= 1:
                break
        else:
            # No Mark Found
            return

        return VieMark(
            name=character,
            view=view,
            regions=regions,
        )

    def iter_marks(self, choices=None):
        ''' Returns all the marks '''
        if choices is None:
            choices = self.ALLOWED_MARKS

        for char in choices:
            mark = self.get_mark(char)
            if mark is not None:
                yield mark

    def add_mark(self, character, view, regions):
        ''' Creates a new mark (overwriting existing ones) '''
        self.delete_mark(character=character)
        view.add_regions("bookmark_" + character, regions)

    @mark_or_character
    def extend_to_mark(self, view):
        viewport = self.__view.visible_region()
        # inverted =


        # cursors =
        #         new_cursor_gen = cursor_to_matches(
        #     cursors=list(self.__view.sel()),
        #     matches=current_matches,
        #     inverted=inverted,
        #     viewport=viewport,
        #     find_visible_only=not update_cursors and not next_only,
        # )


    @mark_or_character
    def go_to_mark(self, mark=None, select=False, full_line=True):
        '''
        Jumps to a mark. Pass in either a mark or a character

        mark (Mark): Internal mark type, to jump to
        character (str): Name of the mark to jump to
        select (bool): whether to also select the mark (or just show it)
        full_line (bool): Whether to highlight the line of the match, or the exact match
            (select=False only)
        '''
        if mark is None:
            return

        if select:
            mark.select()
        else:
            mark.show()

            mark.view.add_regions(
                # Region Name
                "vi_bookmarks_highlight",
                # Area to highlight
                mark.full_lines if full_line else mark.regions,
                # scope
                "wordhighlight",
                # icon
                "bookmark",
                # Flags
                sublime.DRAW_SOLID_UNDERLINE | sublime.DRAW_EMPTY | sublime.DRAW_NO_FILL,
            )

    @mark_or_character
    def delete_mark(self, mark=None):
        ''' Erases a VI bookmark '''
        if mark is None:
            return

        mark.view.erase_regions("bookmark_" + mark.name)

    def delete_all_marks(self):
        ''' Erases all Vi bookmarks '''
        for mark in self.iter_marks():
            self.delete_mark(mark=mark)


class VieStack(VieBookmarker):
    ''' A stack of marks, keeping the latest N values '''

    def push(self, view, regions, inverted=False):
        ''' Pushes a new item on. This assumes a full stack'''
        self._shift_stack(inverted=inverted)

        # Now add the item on top
        self.add_mark(
            character=self.ALLOWED_MARKS[
                -1 if inverted else 0
            ],
            view=view,
            regions=regions,
        )

    def shift(self, view, regions):
        ''' Pushes a new item on to the other side. This assumes a full stack '''
        self.push(view, regions, inverted=True)

    def _shift_stack(self, inverted=False):
        ''' Helper for moving the items in the stack left/right'''
        stack = list(pairwise(self.ALLOWED_MARKS))
        if not inverted:
            stack = reversed(stack)

        # Push all the characters back (erasing any overflow)
        for cur_char, next_char in stack:
            if inverted:
                cur_char, next_char = next_char, cur_char

            # Some of these could be deleted
            mark = self.get_mark(character=cur_char)
            if mark is None:
                continue

            self.add_mark(
                character=next_char,
                view=mark.view,
                regions=mark.regions,
            )

    def peek(self, inverted=False):
        ''' Returns the top item. Assumes a full stack '''
        return self.get_mark(character=(
            self.ALLOWED_MARKS[-1 if inverted else 0]
        ))

    def pop(self):
        ''' Grabs the top item '''
        result = self.peek()
        if result is None:
            # Empty Stack
            return None

        self._shift_stack(inverted=True)
        # The mark is gone after the stack shift, so technically it isn't named anymore
        result.name = None

        # Now find the last item in the stack
        # Since we shifted everything down by one
        # That item is the duplicated (copy)
        for cur_char, next_char in pairwise(reversed(self.ALLOWED_MARKS), include_tail=True):
            mark = self.get_mark(character=cur_char)

            if mark is not None:
                # This is the duplicate, kill it
                self.delete_mark(mark=mark)
                break

        return result

    def update(self, view, regions, inverted=False):
        ''' Updates the top item in the stack '''
        self.add_mark(character=self.ALLOWED_MARKS[
            -1 if inverted else 0
        ], view=view, regions=regions)


class VieMark:
    ''' Saved cursor position '''

    def __init__(self, view, regions=None, name=None, pretty_name=None):
        self.name = name
        self.pretty_name = pretty_name
        self.regions = regions or []
        self.view = view

    @property
    def start_region(self):
        ''' First region with this mark '''
        return self.regions[0]

    @property
    def full_lines(self):
        ''' Expanded regions around the cursor, "line-mode" '''
        lines = []
        for region in self.regions:
            lines.append(self.view.line(region))
        return lines

    def pretty(self, full_line=False):
        ''' Pretty pritns this mark as a string '''
        row, col = self.view.rowcol(self.start_region.begin())

        return "{mark}: #{line_num}: {sample_text}".format(
            mark='{} "{}"'.format(self.pretty_name, self.name) if self.pretty_name else '"{}"'.format(self.name),
            line_num=row + 1,
            sample_text=self.view.substr(self.full_lines[0] if full_line else self.start_region),
        )

    def select(self):
        ''' Selects the mark with the cursors '''
        if not self.regions:
            return

        self.show()

        selection = self.view.sel()

        selection.clear()
        for region in self.regions:
            selection.add(region)

    def show(self):
        ''' shows the mark on screen '''
        if not self.regions:
            return

        self.view.window().focus_view(self.view)  # pylint: disable=no-member
        self.view.show(self.start_region)






































# --------------------------------------------------------------------------------------------------
'''
Commands

vie_push_userstack
vie_pop_userstack
vie_push_definition

vie_show_userstack

",j"   Goes down into the definition (pushes onto the stack)
",k"   Goes up a definition (popping it)

⌘p VieMarks: Visual Stack
  * Shows the current stack
'''
class ViePushBookmark(sublime_plugin.TextCommand):
    ''' Pushes a mark on to a work stack '''
    def run(self, edit=None):
        ''' Runs the command '''
        selection_regions = [selection for selection in self.view.sel()]

        bookmarker = VieUserStack(view=self.view)
        bookmarker.push(
            view=self.view,
            regions=selection_regions,
        )


class ViePushDefinition(sublime_plugin.TextCommand):
    ''' Goes down a definition, then saves it to the stack '''
    def run(self, edit=None):
        ''' Runs the command '''
        window = self.view.window()
        bookmarker = VieUserStack(view=self.view)

        selection = list(self.view.sel())
        if len(selection) > 1:
            return

        # Save the current cursor for later comparison
        cursor = selection[0]

        # Save the current position
        bookmarker.push(
            view=self.view,
            regions=[cursor],
        )

        window.run_command('goto_definition')

        # Did we find a definition?
        new_cursor = list(self.view.sel())[0]
        if cursor.begin() == new_cursor.begin() and cursor.end() == new_cursor.end():
            # Nothing changed, cannot push a "new item"
            return

        # Push the new context on to the stack
        bookmarker.push(
            view=self.view,
            regions=[new_cursor],
        )

class ViePopBookmark(sublime_plugin.TextCommand):
    ''' Goes up one mark on the context stack '''
    def run(self, edit=None):
        ''' Runs the command '''
        bookmarker = VieUserStack(view=self.view)
        mark = bookmarker.pop()
        if mark is not None:
            bookmarker.go_to_mark(mark=mark, select=True)


class VieShowUserStack(sublime_plugin.TextCommand):
    ''' Shows a panel with the visual stack '''
    def run(self, edit=None):
        ''' Runs the command '''
        bookmarker = VieUserStackPanel(view=self.view)
        bookmarker.open_marks_panel(self.view)


# --------------------------------------------------------------------------------------------------


class VieUserStack(VieStack):
    ''' A Stack for user user '''
    ALLOWED_MARKS = list(itertools.chain(
        '!@#$%^&*()',
    ))

    def get_mark(self, character):
        mark = super().get_mark(character)
        if mark is None:
            return None

        index = self.ALLOWED_MARKS.index(mark.name)
        mark.pretty_name = 'S{}'.format(index + 1)

        return mark


class VieUserStackPanel(VieMarkPanel):
    ''' Panel showing the current visual stack '''

    def __init__(self):
        super().__init__()
        self.bookmarker = VieUserStack(view=self.view)

        # Visual mode is already quite visible, lets ensure you know the exact
        #  selection
        self.line_preview = True































# --------------------------------------------------------------------------------------------------
'''
Commands

vie_reuse_visual

"gv"  selects previous selection

⌘p VieMarks: Visual Stack
  * Shows the current stack
'''
class VieReuseVisualCommand(sublime_plugin.TextCommand):
    ''' Loads the last visual selection (or multiselect) '''
    def run(self, edit=None):
        ''' Runs the command '''
        visual_stack = VieVisualStack(view=self.view)
        cursor = visual_stack.peek()
        cursor.select()


class VieShowVisualStack(sublime_plugin.TextCommand):
    ''' Shows a panel with the visual stack '''
    def run(self, edit=None):
        ''' Runs the command '''
        bookmarker = VieVisualStackPanel(view=self.view)
        bookmarker.open_marks_panel(self.view)

# --------------------------------------------------------------------------------------------------


class VieVisualStack(VieStack):
    ''' A stack for previous visual selections '''
    ALLOWED_MARKS = list(itertools.chain(
        '1234567890',
    ))


class VieVisualStackPanel(VieMarkPanel):
    ''' Panel showing the current visual stack '''

    def __init__(self):
        super().__init__()
        self.bookmarker = VieVisualStack(view=self.view)

        # Visual mode is already quite visible, lets ensure you know the exact
        #  selection
        self.line_preview = False


class VisualModeListener(sublime_plugin.EventListener):
    ''' Stores the last used visual selection '''
    @classmethod
    def applies_to_primary_view_only(cls):
        ''' We want this to apply for just one view for the factory '''
        return True

    def on_selection_modified(self, view):
        ''' Updates the last visual selection made '''
        saveable = sublime_is_visual(view) or sublime_is_multiselect(view)
        updating = getattr(self, 'updating', False)

        if not saveable:
            # Nothing to do, but lets remember we're going to be pushing a new item now
            if updating:
                self.updating = False
            return

        window = view.window()
        if window is None:
            # This is a quickpanel... not an actual window
            return

        visual_stack = VieVisualStack(view=view)
        selection = [region for region in view.sel()]

        if updating:
            # Old visual, keep updating it
            visual_stack.update(view=view, regions=selection)
        else:
            # New visual, push
            visual_stack.push(view=view, regions=selection)
            self.updating = True















