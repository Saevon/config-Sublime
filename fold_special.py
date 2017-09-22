import sublime
import sublime_plugin
import re


def sublime_show_region(view, region):
    if not view.visible_region().intersects(region):
        view.show_at_center(region)


def isWhitespace(str):
    return len(str.lstrip()) == 0



class FoldSpecialCommand(sublime_plugin.TextCommand):
    FOLD_PATTERN = (
        r"(it|itErrors)"
        r"\( *"
        r"("
            r"([']([^']|\\['])*')"
            r"|([`]([^`]|\\[`])*`)"
            r'|(["]([^"]|\\["])*")'
        r")"

        # Optional Second Argument
        r"("
            r" *, *"
            r"[^,]+"
        r")?"

        r" *, *(function)? *\((done)?\) *(=>)? *{\n?"
    )

    def run(self, edit=None, **kwargs):
        selected = self.view.sel()
        selection_backup = []
        for region in selected:
            selection_backup.append(region)

        matched_regions = self.view.find_all(self.FOLD_PATTERN, re.DOTALL)

        # Grab the point right after the region to fold
        for region in matched_regions:
            point = region.end() + 1
            region.a = point
            region.b = point

            self.view.sel().clear()
            self.view.sel().add(region)

            # Inbuild Fold Command, needs a start + end to fold a region
            # self.view.fold(matched_regions)
            # Not as good, as it needs the selection to exist (thus we need to revert the selection + view)
            # self.view.run_command('fold')
            # Also not great as this changes selection
            self.view.run_command('expand_selection', args={'to': 'scope'})

            # Normalize the region: ensures reverse regions are flipped
            fold_region = self.view.sel()[0]
            fold_region = sublime.Region(
                fold_region.begin(),
                fold_region.end(),
            )

            # Strip starting spaces from a region
            while fold_region.b > fold_region.a and isWhitespace(self.view.substr(fold_region.a).lstrip()):
                fold_region.a += 1


            # Strip trailing spaces from a region
            while fold_region.b > fold_region.a and isWhitespace(self.view.substr(fold_region.b - 1)):
                fold_region.b -= 1


            self.view.fold(fold_region)


        # Reset the cursor
        self.view.sel().clear()
        for region in selection_backup:
            self.view.sel().add(region)

        if len(selection_backup):
            sublime_show_region(self.view, selection_backup[0])


class FoldSetupCommand(FoldSpecialCommand):
    FOLD_PATTERN = (
        r"(before|after)(Each)?"
        "\(.*{"
    )



