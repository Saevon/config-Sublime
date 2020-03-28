'''
1. Use \$ to escape $ in the snippet
2. Use \t to indicate indentation (sublime auto-converts)
'''
from collections import defaultdict
import itertools
import textwrap
import os
import re
from collections import abc

import yaml
try:
    from jinja2 import Template
except ImportError:
    pass


SNIPPET_RAW = None


def init_jinja():
    '''

    Allows initializing jinja during runtime

    Warning! files in the sublime folders get auto-run as plugins
    ... but this is not a plugin?
    '''

    # Init Jinja2
    #   (with autoescape)
    global SNIPPET_RAW
    SNIPPET_RAW = Template(
        textwrap.dedent("""
            <!-- Auto Generated, See the related .yaml file -->
            <snippet>
                <content><![CDATA[{{ snippet|safe }}]]></content>
                <tabTrigger>{{ trigger }}</tabTrigger>

                <scope>{{ scope }}</scope>
                <description>{{ desc }}</description>
            </snippet>
        """),
        autoescape=True,
    )


def generate_snippets(in_file, out_path):
    with open(in_file) as in_fd:
        raw_data = yaml.safe_load(in_fd.read())

    snippet_groups = raw_data['snippets']
    scope = raw_data['scope']

    # Normalize the input data
    snippets = []
    for group, raw_snippets in snippet_groups.items():
        for entry in raw_snippets:
            if isinstance(entry, str):
                entry = {
                    'trigger': entry,
                    'snippet': entry,
                }

            assert isinstance(entry, dict), "Sanity Check for input"

            # Use the groupname as the default description
            if group is not None:
                if 'desc' not in entry:
                    entry['desc'] = []
                elif isinstance(entry['desc'], str):
                    entry['desc'] = [entry['desc']]

                if group not in entry['desc']:
                    entry['desc'].append(group)

            entry['scope'] = scope

            if ']]>' in entry['snippet']:
                raise Exception("Illegal Chars for CDATA Section ']]>'")

            if isinstance(entry.get('trigger', None), str):
                entry['triggers'] = [entry['trigger']]
            elif isinstance(entry.get('trigger', None), abc.Sequence):
                entry['triggers'] = entry['trigger']

            for trigger in entry['triggers']:
                tags = [
                    tag for tag in entry.get('tags', [])
                    if (tag not in entry['desc']) and (tag not in trigger)
                ]

                snippets.append({
                    **entry,
                    'trigger': trigger,
                    # Warning! this purposely doesn't include the "trigger"
                    #    since it clutters the dropdown
                    #  However, this means the Command-Palette isn't searchable...
                    'desc': ':'.join(itertools.chain(tags, entry['desc'])),
                })

    dups = defaultdict(int)

    for snippet in snippets:
        assert snippet["trigger"], "Need a trigger: {}".format(snippet)

        key = snippet['trigger'].lower()

        dups[key] += 1
        idx = dups[key]

        snippet_file = os.path.join(
            out_path,
            "{}__{}.sublime-snippet".format(
                slugify(snippet['trigger']),
                idx,
            ),
        )

        with open(snippet_file, 'w') as out_fd:
            out_fd.write(SNIPPET_RAW.render(snippet))


def slugify(filename):
    return re.sub(r'[^\w\-. ]+', r'_', filename)


def walk_files(path):
    ''' Returns only the files in the given tree '''
    files = []
    for root, dirs, files in os.walk(path, topdown=False):
        yield from (
            os.path.join(root, file)
            for file in files
        )


def main(path):
    # Find all the ".snippet_gen.yaml" files
    walk_files(path)

    gen_files = [
        file
        for file in walk_files(path)
        if re.match(r".*\.snippet_gen.yaml", file)
    ]

    for file in gen_files:

        out_path = os.path.join(
            os.path.dirname(file),
            "snippet_gen",
        )

        # Ensure the folder exists
        if not os.path.exists(out_path):
            os.mkdir(out_path)
        else:
            # Clear the old snippets
            for old_snippet_file in os.listdir(out_path):
                if old_snippet_file.endswith(".sublime-snippet"):
                    os.remove(os.path.join(
                        out_path,
                        old_snippet_file,
                    ))

        generate_snippets(
            in_file=file,
            out_path=out_path,
        )


if __name__ == '__main__':
    init_jinja()
    main(".")




