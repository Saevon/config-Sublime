import re
from importlib import import_module
import inspect

import sublime_plugin
import sublime


SCOPE_RE = re.compile(r'\bsource\.python\b')
LIB_MODULE_RE = re.compile(r'\bsupport\.module\.python\b')

# Modules we will autocomplete on
MODULE_WHITELIST = {
    # Misc
    'builtins',
    'math',
    'operator',
    'random',
    're',
    'shlex',
    'subprocess',
    'unittest',

    # Debug
    'sys',
    'os',
    'os.path',
    'path',
    'shutil',
    'inspect',
    'logging',
    'resource',
    'struct',
    'tempfile',
    'traceback',

    # Common
    'datetime',
    'time',
    'codecs',
    'string',
    'getpass',
    'decimal',

    # Tools
    'functools',
    'itertools',
    'collections',
    'contextlib',

    'json',

    # External
    #   Need to import somehow...
    # 'requests',
    # 'flask',
}


def format_attr(attr, module):
    module_name = module.__name__
    pretty_attr = attr
    snippet_attr = attr

    obj = getattr(module, attr)

    # if inspect.isclass(attr):
    if isinstance(attr, type):
        pretty_attr = 'class {}()'.format(attr)
    elif callable(obj):
        pretty_attr = '{}()'.format(attr)
        snippet_attr = '{}($1)'.format(attr)

    return (
        pretty_attr + '\t' + module_name,
        snippet_attr,
    )


def grab_module(view, cursor):
    ''' Grabs the entire module path under the cursor '''
    word_sel = view.word(cursor)

    pos = None

    # Are we on a dot right now?
    if view.substr(cursor.begin() - 1) == '.':
        pos = cursor.begin() - 1

    # Are we on a word?
    elif view.substr(word_sel.begin() - 1) == '.':
        pos = word_sel.begin() - 1

    # Not a module
    else:
        return False

    path_parts = []
    while view.substr(pos) == '.':
        # Expand prefix to a word
        word_sel = view.word(pos - 1)
        word = view.substr(word_sel)

        path_parts.append(word)
        pos = word_sel.begin() - 1

    # Format the module path
    path = '.'.join(reversed(path_parts))

    return path


class PythonAutoCompletion(sublime_plugin.EventListener):

    def on_query_completions(self, view, prefix, locations):
        cursor = view.sel()[-1]
        scopes = view.scope_name(cursor.begin())

        # sys.

        # Skip unknown languages
        if not SCOPE_RE.match(scopes):
            return

        # Grab the current path
        module_name = grab_module(view, cursor)
        if module_name not in MODULE_WHITELIST:
            return

        module = import_module(module_name)
        properties = dir(module)

        completions = [
            # Convert to completions format
            format_attr(prop, module)

            for prop in properties

            # Filter out private properties
            if not prop.startswith('_')
        ]

        return (
            # Completions
            completions,

            # Flags:
            (
                # Disable document-word completions
                sublime.INHIBIT_WORD_COMPLETIONS
                # Disable .sublime-completions
                | sublime.INHIBIT_EXPLICIT_COMPLETIONS
            ),
        )

