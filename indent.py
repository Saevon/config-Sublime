import re
import sublime
import sublime_plugin


class ConvertIndentationCommand(sublime_plugin.TextCommand):
    TAB_KEY = 'tab'

    def run(self, edit=None, **kwargs):
        from_size = kwargs.get("from_size")
        to_size = kwargs.get("to_size")

        # Shortcircuit
        if from_size == to_size:
            return

        # We don't need to convert it to tabs if its already there
        if from_size != self.TAB_KEY:
            self.view.run_command(
                'set_setting',
                args={
                    "setting": "tab_size",
                    "value": from_size,
                }
            )
            self.view.run_command(
                'unexpand_tabs',
                args={
                    "set_translate_tabs": True,
                }
            )

        # We don't need to convert to spaces if we want tabs
        if to_size != self.TAB_KEY:
            self.view.run_command(
                'set_setting',
                args={
                    "setting": "tab_size",
                    "value": to_size,
                }
            )
            self.view.run_command(
                'expand_tabs',
                args={
                    "set_translate_tabs": True,
                }
            )

