# !/usr/bin/env python3
# -*- coding: UTF-8 -*-
#
# Shows all the vi marks that exist
#
import os
import re

import sublime
import sublime_plugin


class ShebangSyntaxListener(sublime_plugin.EventListener):

    def on_load(self, view):
        view.run_command('shebang_syntax')

    def on_post_save(self, view):
        view.run_command('shebang_syntax')


SYNTAX_FILE_EXTENSIONS = [
    '.tmLanguage',
    '.sublime-syntax',
]


def all_syntax_files(package, syntax):
    for extension in SYNTAX_FILE_EXTENSIONS:
        yield os.path.join(
            package,
            syntax + extension,
        )


class ShebangSyntaxCommand(sublime_plugin.TextCommand):
    MAPPING = {
        re.compile(r'python([23]\.[0-9]+)?'): 'Python',
        re.compile(r'perl'): 'ModernPerl',
        re.compile(r'(bash|sh)'): ('ShellScript', "Shell-Unix-Generic"),
        re.compile(r'(ghc|haskell)'): 'Haskell',
    }


    def run(self, edit):
        # Only operate on files with no file extension (i.e. no dots)
        # if not os.path.basename(self.view.file_name()).find('.'):
        #     return

        # Grab the first line's contents
        first_line = self.view.substr(self.view.full_line(1))

        # Get the shebang components
        match = re.match(r"#\s*!\s*(?P<path>[^\s]+(\\|/))?(?P<cmd>[^\s/\\]+)\s*(?P<arg>[^\s]+)?", first_line)
        if not match:
            # We only run on things which have a shebang
            return

        command = match.group('cmd')
        if command == 'env':
            # If its the env command, use the first argument instead
            command = match.group('arg')

        # TODO: make this a proper plugin
        # Grab the user customizationgs
        # settings = sublime.load_settings('Shebang.sublime-settings')
        # mapping = settings.get('language_mapping')
        # mapping.get(' ')
        for regex, syntax in self.MAPPING.items():
            match = regex.match(command)
            if match:
                break
        else:
            # If its not special, try to find it as is
            syntax = command

        # Get the current syntax type
        # current_syntax = self.view.settings().get('syntax')

        # Check the syntax type
        if isinstance(syntax, tuple):
            # If its a tuple, the package and the syntax might differ
            print(syntax)
            package, syntax = syntax
        else:
            # If its a single value, its assumed the package is the same as the syntax
            package = syntax

        for syntax_file in all_syntax_files(package, syntax):
            if os.path.exists(os.path.join(sublime.packages_path(), syntax_file)):
                break
        else:
            # Syntax doesn't exist...
            return


        # Set the syntax
        print("Setting Syntax (from shebang): " + syntax_file)
        self.view.set_syntax_file(os.path.join('Packages', syntax_file))
