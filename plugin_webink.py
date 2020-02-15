import re
import webbrowser

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
    ''' Opens the Link under the cursor/cursors '''

    def run(self, edit):
        is_visual = sublime_is_visual(self.view)

        selection = self.view.sel()

        for cursor in selection:
            if is_visual:
                word = self.view.substr(cursor)
            else:
                word_region = self.view.word(cursor)
                row, col = self.view.rowcol(word_region.begin())
                line = self.view.substr(self.view.full_line(word_region))

                left = re.search(r'((\[[^\]]+\]\())?\S*$', line[:col]).group()
                right = re.search(r'^\S*', line[col+1:]).group()

                word = left + line[col] + right

            match = re.match(MD_HYPERLINK_RE, word)
            if not match:
                match = re.match(HYPERLINK_RE, word)

            if match:
                url = match.group(1)
                webbrowser.open_new_tab(url)


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
            sublime.DRAW_NO_FILL |
            sublime.DRAW_NO_OUTLINE
            # sublime.DRAW_SQUIGGLY_UNDERLINE
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
            link=url,
            content='↪',
        )
        view.add_phantom(
            'saevon-weblink-icon',
            sublime.Region(region.end(), region.end()),
            content,
            sublime.LAYOUT_INLINE,
            self.on_navigate
        )

    def on_load_async(self):
        self.render(self.view)

    def on_modified_async(self):
        ''' Adds all links '''
        self.view.erase_phantoms('saevon-weblink-icon')
        self.view.erase_regions('saevon-weblink')

        self.render(self.view)
