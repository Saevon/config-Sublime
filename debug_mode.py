import re
import sublime
import sublime_plugin


SUBLIME_DEBUG_STATUS = {}


class DebugSublimeToggleCommandsCommand(sublime_plugin.ApplicationCommand):

    def run(self):
        status = not SUBLIME_DEBUG_STATUS.get('commands', False)
        SUBLIME_DEBUG_STATUS['commands'] = status

        sublime.log_commands(status)
        sublime.log_input(status)

