import sublime_plugin


class SurroundWith(sublime_plugin.TextCommand):
    '''
    Surrounds the selections with quotes or brackets (basesd on the character passed in)

    if expand==True then it also expands the selection to a word
    '''

    def run(self, edit, character, expand=False):
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
        elif character in "*-+_%$|/\\":
            # Also allow weird characters
            start = end = character
        else:
            print("Can't surround this character", character)

        if expand:
            self.view.run_command("enter_visual_mode")
            self.view.run_command("expand_selection", {"to": "word"})

        for sel in self.view.sel():
            self.view.insert(edit, sel.begin(), start)
            self.view.insert(edit, sel.end() + 1, end)

        # Save the transaction
        self.view.end_edit(edit)
