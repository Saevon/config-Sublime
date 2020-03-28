'''
Allows you to treat links in text as hyperlinks


# TODO

 * Find In files makes the Link-Icons flicker
   (Since the page keeps being "modified")


'''
import re
import itertools
import webbrowser
import html

import sublime
import sublime_plugin


from User.sublime_helpers import sublime_is_visual

# Warning! `sublime.find_all` doesn't like named groups...
HYPERLINK_RE = (
    r'(' + (
        # Valid schemas
        r'(?:https?)'
        r'://'
        # The entire URL ending
        r'\S*'
    ) + r')'
)
MD_HYPERLINK_RE = (
    r'(?:' + (
        r'(?:\[[^\]]*\]\()'
        + HYPERLINK_RE +
        r'\)'
    ) + r')'
)


class OpenHyperLinkCommand(sublime_plugin.TextCommand):
    '''
    Opens the Link under the cursor/cursors

    If you're in visual mode (Have something selected) then it tried to go to that exact address
    (Unless you've selected an invalid link) Ignoring any prefix/suffix characters
    '''

    def run(self, edit):
        ''' Opens any links '''
        is_visual = sublime_is_visual(self.view)

        selection = self.view.sel()

        for cursor in selection:
            if is_visual:
                url = self.exact_link(cursor)
            else:
                url = next(self.selected_links(cursor), None)

            if url:
                webbrowser.open_new_tab(url)

    def exact_link(self, cursor):
        ''' Finds the link exactly selected by the cursor '''
        word = self.view.substr(cursor)

        match = re.match(MD_HYPERLINK_RE, word)
        if not match:
            match = re.match(HYPERLINK_RE, word)

        if match:
            return match.group(1)

        return None

    def selected_links(self, cursor):
        ''' Finds all links the cursor is on '''
        lines = self.view.full_line(cursor)
        line = self.view.substr(lines)

        # Find all links in the selection
        links = itertools.chain(
            re.finditer(MD_HYPERLINK_RE, line),
            re.finditer(HYPERLINK_RE, line),
        )

        for link in links:
            # Offset the link by the document position
            start = link.start() + lines.begin()
            end = link.end() + lines.begin()

            if start <= cursor.begin() and cursor.end() <= end:
                yield link.group(1)


class HyperLinkAnnotator(sublime_plugin.ViewEventListener):
    ''' Adds clickable hyperlinks '''

    def render(self, view):
        ''' Adds all links '''
        links = view.find_all(MD_HYPERLINK_RE + r"|" + HYPERLINK_RE)
        for link in links:
            self.render_link(view, link)

        # Also add the underline
        # current = view.get_regions('saevon-weblink')
        view.add_regions('saevon-weblink', links, 'markup.underline.link', flags=(
            sublime.DRAW_NO_FILL
            | sublime.DRAW_NO_OUTLINE
            # | sublime.DRAW_SQUIGGLY_UNDERLINE
        ))

    def on_navigate(self, url):
        ''' Adds all links '''
        webbrowser.open_new_tab(url)

    def render_link(self, view, region):
        ''' Adds all links '''
        text = view.substr(region)
        match = re.match(MD_HYPERLINK_RE, text)
        if not match:
            match = re.match(HYPERLINK_RE, text)

        url = match.group(1)

        content = """
            <span class="label label-success"><a href="{link}">{content}</a></span>
        """.format(
            link=html.escape(url),
            content=html.escape('↪'),
        )
        view.add_phantom(
            'saevon-weblink-icon',
            sublime.Region(region.end(), region.end()),
            content,
            sublime.LAYOUT_INLINE,
            self.on_navigate
        )

    def on_load_async(self):
        ''' On page loaded '''
        self.render(self.view)

    def on_modified_async(self):
        ''' On page edit '''
        self.view.erase_phantoms('saevon-weblink-icon')
        self.view.erase_regions('saevon-weblink')

        self.render(self.view)
