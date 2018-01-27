#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
# Shows all the vi marks that exist
#
# Part of the VIE packages: VintageExtended
#
# * Can load bookmarks (across views)
# * Can show all bookmarks (across views)
# * Can use Vintage Bookmarks
# * Works with Split Panes (but can't)
#
# TODO: This is broken for split screen
#   (You can't seem to preview across panes)
# TODO: This should work as a motion command, so you could do:
#       d`m to delete to a mark
#       v`m to delete to select to a mark


import itertools
import functools
import string

import sublime
import sublime_plugin



class MetaWindowFactory(type):
    '''
    Factory, returns an object per window
    '''

    def __init__(cls, name, bases, attrs, **kwargs):
        cls._instances = {}
        super().__init__(name, bases, attrs, **kwargs)

    def __call__(cls, *args, **kwargs):
        if len(args) >= 1:
            view = args[0]
            args = args[1:]
        else:
            view = kwargs.pop('view')

        window = view.window()
        kwargs['window'] = window

        factory_id = window.id()
        if not cls._instances.get(factory_id, False):
            cls._instances[factory_id] = type.__call__(cls, *args, **kwargs)

        return cls._instances[factory_id]
































class VieShowAllBookmarks(sublime_plugin.TextCommand):
    def run(self, edit=None):
        bookmarker = ViBookmarker(view=self.view)
        bookmarker.open_marks_panel(self.view)


class VieDeleteBookmark(sublime_plugin.TextCommand):
    def run(self, edit=None):
        bookmarker = ViBookmarker(view=self.view)
        bookmarker.delete_selected()


class VieCreateBookmark(sublime_plugin.TextCommand):
    def run(self, edit=None, character=None):
        selection_regions = [selection for selection in self.view.sel()]

        bookmarker = ViBookmarker(view=self.view)
        bookmarker.add_mark(
            character=character,
            view=self.view,
            regions=selection_regions,
        )


class VieSelectBookmark(sublime_plugin.TextCommand):
    def run(self, edit=None, character=None, select=True):
        bookmarker = ViBookmarker(view=self.view)

        bookmarker.go_to_mark(character=character, select=select, previewable=False)


class VieClearBookmarks(sublime_plugin.TextCommand):
    def run(self, edit=None):
        bookmarker = ViBookmarker(view=self.view)
        bookmarker.delete_all_marks()


#
# ---------------------------------------------------------
#
#


class ViBookmarker(object, metaclass=MetaWindowFactory):
    '''
    Bookmarks API:
    '''

    def __init__(self, window):
        self.window = window

        self.current_selection = None
        self.saved_view = None
        self.saved_viewport = None

    def mark_or_character(func):
        '''
        Allows a method to accept either a character, or an internal mark
        '''
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            previewable = kwargs.pop('previewable', True)

            mark = kwargs.get('mark', None)
            if not mark:
                try:
                    character = kwargs.pop('character')
                except KeyError:
                    raise ValueError("You need either a 'mark' or 'character' kwarg")
                kwargs['mark'] = self.get_mark(character, previewable=previewable)

            return func(self, *args, **kwargs)

        return wrapper


    #------------------------------------
    # Events: Quickpanel

    def on_done(self, selected_index):
        if selected_index == -1:
            # aborted
            self.load_view()
        else:
            # selected
            mark = self.choices[selected_index]
            self.go_to_mark(mark=mark, select=True)

        # Reset everything
        self.reset()

    def on_highlighted(self, selected_index):
        self.current_selection = selected_index

        # Selected Item was Changed
        mark = self.choices[selected_index]
        self.go_to_mark(mark=mark, select=False)



    # --------------------------

    ALLOWED_MARKS = list(itertools.chain(
        # string.ascii_lowercase,
        # string.ascii_uppercase,
        # string.whitespace,
        # string.punctuation,
        # string.digits,

        # We'll just use all the keyboard chars
        # Rather than explicitly listing them like above
        string.printable
    ))

    def _get_views(self, previewable=True):
        if previewable:
            # If theres a quick panel we can't jump between groups or else it breaks
            # (As the panel auto closes with "loss of focus")
            active_group = self.window.active_group()
            return self.window.views_in_group(active_group)
        else:
            # If we're doing this using keystrokes, just jump anywhere
            return self.window.views()

    def get_mark(self, character, previewable=True):
        '''
        Gets info about the mark under the character
        '''

        # Some views can be jumped to, others can be previewed

        # a group of regions at the current vim bookmark
        view = None
        for view in self._get_views(previewable):
            regions = view.get_regions("bookmark_" + character)
            if len(regions) >= 1:
                break

        # There should only be one bookmark per region
        if len(regions) == 0:
            return

        region = regions[0]
        start = sublime.Region(region.begin(), region.begin())
        full_line = view.line(region)
        row, col = view.rowcol(region.begin())

        return {
            "mark": character,
            "start": start,
            "row": row,
            "col": col,
            "line_num": row + 1,

            "full_line": full_line,
            "full_text": view.substr(full_line),
            "text": view.substr(region),

            "view": view,
            "region": region,
        }

    def get_marks(self, previewable=True):
        '''
        Returns all the marks
        '''
        marks = []

        for char in self.ALLOWED_MARKS:
            mark = self.get_mark(char, previewable)
            if mark is not None:
                marks.append(mark)

        return marks



    #------------------------
    # Public API

    def add_mark(self, character, view, regions):
        self.delete_mark(character=character, previewable=False)
        view.add_regions("bookmark_" + character, regions)


    def open_marks_panel(self, view):
        '''
        @public
        '''
        self.reset()
        self.save_position(view)

        marks = self.get_marks(previewable=True)
        self.choices = marks

        # Format them for the panel
        items = []
        for mark in marks:
            items.append("'{mark}': #{line_num}: {full_text}".format(**mark))

        # Show all the bookmarks in a panel
        self.current_selection = 0
        self.window.show_quick_panel(
            # items
            items,
            # on_done
            self.on_done,
            # flags
            sublime.MONOSPACE_FONT,
            # selected_index
            0,
            # on_highlighted
            self.on_highlighted,
        )

    @mark_or_character
    def go_to_mark(self, mark=None, select=False):
        '''
        Jumps to a mark. Pass in either a mark or a character

        mark (Mark): Internal mark type, to jump to
        character (str): Name of the mark t jump to
        select (bool): whether to also select the mark (or just show it)
        '''
        if mark is None:
            return

        view = mark["view"]

        self.window.focus_view(view)

        if select:
            view.show_at_center(mark["start"])
            selection = view.sel()

            selection.clear()
            selection.add(mark["start"])
        else:
            view.show_at_center(mark["start"])
            view.add_regions(
                # Region Name
                "vi_bookmarks_highlight",
                # Area to highlight
                [mark["full_line"]],
                # scope
                "wordhighlight",
                # icon
                "bookmark",
                # Flags
                sublime.DRAW_SOLID_UNDERLINE | sublime.DRAW_EMPTY | sublime.DRAW_NO_FILL,
            )

    def delete_selected(self):
        '''
        Deletes the selected region in the quickpanel
        Does nothing if the quickpanel isn't open
        '''
        if self.current_selection is None:
            return

        mark = self.choices[self.current_selection]

        self.delete_mark(mark=mark)

        self.load_view()
        self.close_panel()


    def save_position(self, view):
        '''
        Saves the viewport for the view (to restore after the quickpanel moves you around)
        '''
        self.saved_view = view
        self.saved_viewport = view.viewport_position()

    def load_view(self):
        '''
        Reloads the saved view (restoring to before the quickpanel was opened)
        '''
        self.window.focus_view(self.saved_view)
        self.saved_view.set_viewport_position(self.saved_viewport)


    def reset(self):
        '''
        Reset the entire bookmarks panel

        @public
        '''
        self.current_selection = None
        self.reset_highlights()
        self.saved_view = None
        self.saved_viewport = None


    def reset_highlights(self):
        '''
        Clears any changes the bookmarks could have made

        @public
        '''
        for view in self._get_views():
            view.erase_regions("vi_bookmarks_highlight")

    def close_panel(self):
        '''
        Closes the input panel if its not there

        @public
        '''
        self.window.run_command("hide_overlay", {"cancel": True})

    @mark_or_character
    def delete_mark(self, mark=None):
        '''
        Erases a VI bookmark

        @public
        '''
        if mark is None:
            return

        mark['view'].erase_regions("bookmark_" + mark['mark'])

    def delete_all_marks(self):
        '''
        Erases all Vi bookmarks

        @public
        '''
        for mark in self.get_marks(previewable=False):
            self.delete_mark(mark=mark)






