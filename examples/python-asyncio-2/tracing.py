"""A selector that prints each select() call: one line per loop iteration."""

import selectors


class TracingSelector(selectors.DefaultSelector):
    printing = True  # switch off to hide iterations you are not studying

    def select(self, timeout=None):
        if self.printing:
            shown = "None, wait for I/O" if timeout is None else f"{timeout:.2f} s"
            print(f"  -- select(timeout={shown})")
        return super().select(timeout)
