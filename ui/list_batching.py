"""
Shared batching rule for the collection list panels.

Each list panel builds one button per row, a few at a time (BATCH_SIZE every
BATCH_DELAY_MS). That is fine for the list you are looking at, but the startup
preload builds every collection's list while nothing is on screen, and the
back-to-back batches leave the window unresponsive for seconds. A list that is
not currently shown therefore trickles in a few rows per tick instead, and
switches to the fast batches by itself the moment its view is opened.
"""


class BatchedListMixin:
    """Mix into a list panel that defines BATCH_SIZE and BATCH_DELAY_MS."""

    HIDDEN_BATCH_SIZE = 3
    HIDDEN_BATCH_DELAY_MS = 120

    def _batch_size(self) -> int:
        return self.BATCH_SIZE if self.winfo_ismapped() else self.HIDDEN_BATCH_SIZE

    def _batch_delay(self) -> int:
        return self.BATCH_DELAY_MS if self.winfo_ismapped() else self.HIDDEN_BATCH_DELAY_MS
