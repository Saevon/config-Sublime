import sublime
import sublime_plugin


class SurroundWith(sublime_plugin.TextCommand):
    '''
    Surrounds the selections with quotes or brackets (basesd on the character passed in)

    if expand==True then it also expands the selection to a word
    '''

    def run(self, edit, character, expand=False):
        # This should already be sorted
        orig_selection = [region for region in self.view.sel()]

        if character in "{}":
            start = "{"
            end = "}"
        elif character in "[]":
            start = "["
            end = "]"
        elif character in "()":
            start = "("
            end = ")"
        elif character in "<>":
            start = ">"
            end = ">"
        elif character in "'\"`":
            start = end = character
        elif character in "*-+_%$|/\\ ":
            # Also allow weird characters
            start = end = character
        else:
            # TODO: status bar message?
            print("Can't surround with character: '{}'".format(character))
            return;

        if expand:
            self.view.run_command("enter_visual_mode")
            self.view.run_command("expand_selection", {"to": "word"})

        for sel in self.view.sel():
            self.view.insert(edit, sel.begin(), start)
            self.view.insert(edit, sel.end() + 1, end)

        # Reset each selection in order, adding the resulting offset for each change
        offset = 0
        self.view.sel().clear()
        for selection in orig_selection:
            offset += len(start)

            self.view.sel().add(sublime.Region(
                selection.begin() + offset,
                selection.end() + offset,
            ))

            # Now add the "end" offset for the next selection
            offset += len(end)

        # Save the transaction
        self.view.end_edit(edit)
