import sublime
import sublime_plugin
import re


def sublime_show_region(view, region):
    if not view.visible_region().intersects(region):
        view.show_at_center(region)


class FoldSpecialCommand(sublime_plugin.TextCommand):
    FOLD_PATTERN = r"it\('([^']|\\')*', *(function)? *\((done)?\) *(=>)? *{"

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
            self.view.run_command('fold')

        # Reset the cursor
        self.view.sel().clear()
        for region in selection_backup:
            self.view.sel().add(region)

        if len(selection_backup):
            sublime_show_region(self.view, selection_backup[0])


