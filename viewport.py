#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
# Manipulate your viewport


import sublime
import sublime_plugin


class CenterOnVisibleCommand(sublime_plugin.TextCommand):
    '''
    Moves the cursor to the center of the current viewport
    (on the first non-blank char)
    '''
    def run(self, edit=None):
        view = self.view

        visible_region = view.visible_region()
        lines = view.lines(visible_region)
        selection = view.sel()

        # Assumes at least one line always
        # Moves to the center of the visible region
        selection_region = lines[int(len(lines) / 2)]

        # Now selects the start of the line
        selection_region.b = selection_region.a
        selection.clear()
        selection.add(selection_region)

        # Now go to the first real char on the line
        self.view.run_command(
            'set_motion',
            args={
                "motion": "vi_move_to_first_non_white_space_character",
                "motion_args": {"extend": True},
                "clip_to_line": True,
            },
        )


