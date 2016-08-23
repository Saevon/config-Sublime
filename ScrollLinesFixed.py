import sublime
import sublime_plugin


class ScrollLinesFixedCommand(sublime_plugin.TextCommand):
    """Must work exactly as builtin scroll_lines command, but without moving the cursor when it goes out of the visible area."""

    def run(self, edit, amount, by="lines"):
        if by == 'pages':
            maxy = self.view.layout_extent()[1] - self.view.line_height()
            curx, cury = self.view.viewport_position()
            if by == "pages":
                delta = self.view.viewport_extent()[1]
            else:
                delta = self.view.line_height()
            nexty = min(max(cury - delta * amount, 0), maxy)
            self.view.set_viewport_position((curx, nexty))
        else:
            self.view.run_command("scroll_lines", {"amount": amount})
