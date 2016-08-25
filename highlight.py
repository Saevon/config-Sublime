import sublime
import sublime_plugin


# HIGHLIGHT_GROUP = 'Saevon-HighlightAllPlugin'


class HighlightAllCommand(sublime_plugin.TextCommand):

    def on_change(self, data):
        pass

    def on_done(self, data):
        selection = self.view.sel()

        regions = self.view.find_all(data, sublime.IGNORECASE)

        # Filter out things that haven't been selected
        if len(selection) >= 2 or selection[0].size() >= 1:
            regions = list(filter(lambda region: selection.contains(region), regions))

        # Keep any old highlights
        regions += self.view.get_regions('highlightALL')
        self.view.add_regions('highlightALL', regions, 'variable.function')

    def on_cancel(self):
        pass

    def on_action(self, data=None):
        print(data)

    def run(self, edit=None):
        self.view.window().show_input_panel('  ? ', '', on_done=self.on_done, on_change=self.on_change, on_cancel=self.on_cancel)


class ClearAllHighlightsCommand(sublime_plugin.TextCommand):
    def run(self, edit=None):
        self.view.erase_regions('highlightALL')
