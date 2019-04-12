'''
Helper functions for working with sublime
'''
import sublime
import sublime_plugin


def sublime_show_region(view, region):
    ''' Shows the region in the view (not moving if its already visible) '''
    if not view.visible_region().intersects(region):
        view.show_at_center(region)


def sublime_is_multiselect(view):
    ''' Figures out if we're in multiselect mode '''
    selections = view.sel()

    return len(selections) > 1


def sublime_is_visual(view):
    ''' Figures out if we're in visual mode '''
    selections = view.sel()

    # Is anything selecting at least one char? aka are we in block mode
    # Note:  Command Mode is identical to Insert mode (selection of no chars)
    #    except its displayed as a block cursor
    # ONLY visual mode selects a char
    return any(
        (not sel.empty()) for sel in selections
    )


class MetaWindowFactory(type):
    '''
    Factory: Singleton per window

    Meta-Using classes:
        view MUST be passed into __init__
        self.window is always assigned
    '''

    def __init__(cls, name, bases, attrs, **kwargs):
        cls._instances = {}
        super().__init__(name, bases, attrs, **kwargs)

    def __call__(cls, *args, **kwargs):
        view = kwargs.pop('view', None)
        window = kwargs.pop('window', None)

        if window is None and view is not None:
            window = view.window()

        factory_id = window.id()
        self = cls._instances.get(factory_id, None)
        if self is None:
            self = cls.__new__(cls, *args, **kwargs)
            self.window = window
            self.__init__(*args, **kwargs)

            cls._instances[factory_id] = self

        return self


class MetaViewFactory(type):
    '''
    Factory: Singleton per view

    Meta-Using classes:
        view MUST be passed into __init__
        self.view is always assigned
    '''

    def __init__(cls, name, bases, attrs, **kwargs):
        cls._instances = {}

        super().__init__(name, bases, attrs, **kwargs)

    def __call__(cls, *args, **kwargs):
        view = kwargs.pop('view', None)

        factory_id = view.id()
        self = cls._instances.get(factory_id, None)
        if self is None:
            self = cls.__new__(cls, *args, **kwargs)
            self.view = view
            self.__init__(*args, **kwargs)

            cls._instances[factory_id] = self

            self.view = view

        return self


class Viewport():
    ''' Saved viewport in a specific view '''
    def __init__(self, view):
        self.view = view
        self.__viewport = view.viewport_position()

    def load(self):
        ''' Reloads this viewport '''
        self.view.window().focus_view(self.view)
        self.view.set_viewport_position(self.__viewport)


class QuickPanelFinder(metaclass=MetaWindowFactory):
    ''' One-Use listener that gives you back the view of the quickpanel '''

    def __init__(self):
        ''' Creates a listener '''
        self.listener = None

    def listen(self, callback):
        ''' Callback that returns the view when the quickpanel opens '''
        if self.listener is not None:
            raise RuntimeError("Existing Listener: Another quickpanel is also opening?")

        self.listener = callback

    def on_open(self, view):
        ''' Event: called when a quickpanel opens '''
        if not self.listener:
            return

        try:
            self.listener(view)
        finally:
            self.listener = None


class QuickPanelListener(sublime_plugin.EventListener):
    ''' Listener for a quickpanel '''
    def on_activated(self, view):
        ''' This method is called whenever a view (tab, quick panel, etc.) gains focus '''
        QuickPanelFinder(view=view).on_open(view)


# --------------------------------------------------------------------------------------------------
def closest_visible(selection, visible_region=None, inverted=False):
    ''' Returns the first region which is fully visible.
    If nothing is visible, a random selection is returned

    visible_region = view.visible_region()
    '''
    if len(selection) == 0:
        # Nothing to choose from...
        return None

    if visible_region is None or len(selection) == 1:
        # Since nothing seems visible, then the very first selection
        # is our default 'closest'
        return selection[0]

    # Find the first region which is withing our viewport
    for region in selection:
        if visible_region.contains(region):
            # We found one inside the viewport!
            return region
        elif not inverted and visible_region.begin() <= region.begin():
            # We've Gone past the viewport, just take the next one
            return region
        elif inverted and visible_region.end() <= region.end():
            # We've gone past the viewport, just take the next one
            return region

    # We've hit the end... loop back to the first one
    return selection[0]


class CursorMatch(object):
    ''' Show that this region is special (is the one the viewport should jump to '''
    # pylint: disable=too-few-public-methods

    def __init__(self, cursor, region, is_visible=False):
        ''' Stores a region '''
        self.region = region
        self.orig = cursor
        self.is_visible = is_visible


def cursor_to_matches(*, cursors, matches, viewport, inverted=False, find_visible_only=False):
    ''' Loops through and generates a new set of cursors to jump to
    a VisibleMatch() is yielded if that is the best region to show the user
    '''
    matches = list(matches)
    if len(matches) == 0:
        # There is no such thing as 'next'
        return

    # We'll be messing with the list, duplicate it
    cursors = list(cursors)

    # Invert our jump
    if inverted:
        # Sublime merges adjacent regions, so they cannot overlap
        # THUS inverting it results in a sorted (backwards) list
        cursors = [cursor for cursor in cursors[::-1]]
        matches = matches[::-1]

    # Find the closest cursor to the visible regions
    if len(cursors) == 0:
        # There is no cursor to jump from?
        # Just go to a visible match
        new_visible = closest_visible(matches, viewport, inverted=inverted)

        # And theres no cursors to 'jump'... finish off
        yield CursorMatch(None, new_visible, is_visible=True)
        return

    # Find the first cursor that is visible
    visible_cursor = closest_visible(cursors, viewport, inverted=inverted)

    # If we just want the visible cursor only (aka only the new viewport focus)
    # Then pretend we only have one cursor... the closest visible one
    if find_visible_only:
        cursors = [visible_cursor]

    # Used when cursors no longer see a match after them
    # They all loop around to the first one
    loop_match = matches[0]

    # The search has Multiple Stages, this ensures we keep circling through them
    # until we're done

    limit = LoopLimit(
        'Overflowed the search, either there were too many items (over 10000), '
        'or there is an infinite loop bug'
    )
    while len(matches) and len(cursors):
        limit.count()

        # Stage 1: Drop matches that are before ANY Cursors
        while len(matches) and (
                # Normal means we're going forwards (compare the starts)
                (not inverted and cursors[0].begin() >= matches[0].begin())
                # Inverted means we're going backwards (compare the ends)
                or (inverted and cursors[0].end() <= matches[0].end())
        ):
            limit.count()

            # Drop elements before the cursor
            matches.pop(0)

        # Stage 2: Early Abort (no Matches left!)
        if len(matches) == 0:
            # We've exhausted the search
            # Replace all remaining cursors with the looped match

            yield CursorMatch(None, loop_match, is_visible=(visible_cursor in cursors))
            return

        # Stage 3: Jump cursors that are before the next match (with that match)
        was_visible = False
        replaced_cursors = []
        while len(cursors) and (
                (not inverted and cursors[0].begin() <= matches[0].begin())
                or (inverted and cursors[0].end() >= matches[0].end())
        ):
            limit.count()

            # We found the 'visible cursor' note that down
            if cursors[0] == visible_cursor:
                was_visible = True

            # Replace cursors before the match
            replaced_cursors.append(cursors.pop(0))

        # All the cursors we just dropped go to this match
        yield CursorMatch(
            (replaced_cursors[0] if replaced_cursors else None),
            matches[0],
            is_visible=was_visible,
        )


































# -------------------------------------------------------------------------------------------------
# Misc helpers
# NON SUBLIME
import itertools


class Sentinel:
    ''' Sentinel Value '''
    def __repr__(self):
        return self.__class__.__name__


class PairwiseTailSentinel(Sentinel):
    ''' Means you don't want a tail '''


def pairwise(iterable, tail=PairwiseTailSentinel):
    """
    s -> (s0,s1), (s1,s2), (s2, s3), ...
    s, None -> (s0, s1) ... (sn-1, sn), (sn, None)

    """
    left, right = itertools.tee(iterable)
    next(right, None)
    if tail is not PairwiseTailSentinel:
        right = itertools.chain(right, [tail])

    return zip(left, right)


class LoopLimit(Exception):
    ''' Counts loop counters until yourun out, then raises itself as an error '''

    def __init__(self, message=None, limit=1000):
        self.counter = limit

        super().__init__(message)

    def count(self):
        ''' Counts down to the limit, crashes if its reached '''
        self.counter -= 1
        if self.counter <= 0:
            raise self











