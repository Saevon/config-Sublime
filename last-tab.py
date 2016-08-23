import sublime, sublime_plugin

class LastViewCommand(sublime_plugin.WindowCommand):
    def run(self):
        self.window.focus_view(self.window.views()[-1])
