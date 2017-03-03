#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
# Shows all the vi marks that exist


import sublime
import sublime_plugin

import itertools
import string


class ViShowAllBookmarks(sublime_plugin.TextCommand):
    def run(self, edit=None):
        self.reset()
        self.save_view()

        marks = self.get_marks()

        # Format them for the panel
        items = []
        for mark in marks:
            items.append("'{mark}': #{line_num}: {full_text}".format(**mark))

        # Show all the bookmarks in a panel
        self.view.window().show_quick_panel(
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

    def on_done(self, selected_index):
        if selected_index == -1:
            # aborted
            self.load_view()
        else:
            # selected
            self.go_to_mark(selected_index, select=True)

        self.reset()

    def on_highlighted(self, selected_index):
        # Selected Item was Changed
        self.go_to_mark(selected_index)

    # --------------------------
    # Events: Non-Quickpanel code

    ALLOWED_CHARS = itertools.chain(
        # string.ascii_lowercase,
        # string.ascii_uppercase,
        # string.whitespace,
        # string.punctuation,
        # string.digits,
        string.printable
    )

    def get_marks(self):
        marks = []

        # FIXME: If you call this command twice in a row, the second time, no bookmarks are found

        for mark in self.ALLOWED_CHARS:
            # a group of regions at the current vim bookmark
            regions = self.view.get_regions("bookmark_" + mark)

            # There should only be one bookmark per region
            if len(regions) == 0:
                continue
            elif len(regions) != 1:
                print("WARNING: Got multiple regions under viMark: {mark}".format(mark=mark))

            region = regions[0]
            start = sublime.Region(region.begin(), region.begin())
            full_line = self.view.line(region)
            row, col = self.view.rowcol(region.begin())

            marks.append({
                "mark": mark,
                "row": row,
                "col": col,
                "line_num": row + 1,
                "full_line": full_line,
                "full_text": self.view.substr(full_line),
                "text": self.view.substr(region),
                "region": region,
                "start": start,
            })

        self.marks = marks

        return marks

    def go_to_mark(self, index, select=False):
        mark = self.marks[index]

        if select:
            selection = self.view.sel()

            selection.clear()
            selection.add(mark["start"])
        else:
            self.view.show_at_center(mark["start"])
            self.view.add_regions(
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

    def save_view(self):
        self.saved_viewport = self.view.viewport_position()

    def load_view(self):
        self.view.set_viewport_position(self.saved_viewport)

    def reset(self):
        self.view.erase_regions("vi_bookmarks_highlight")


