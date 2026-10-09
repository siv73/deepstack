"""Simplified table lock queue. A request waits if it conflicts with a holder (hard block)
or with a request queued ahead of it (soft block), as pg_blocking_pids defines blocking."""

from lock_modes import COMMAND_LOCK, conflicts


class TableLocks:
    def __init__(self):
        self.held, self.queue = [], []  # lists of (session, mode), queue in arrival order

    def blockers(self, session, mode, ahead):
        return [s for s, m in self.held + ahead if s != session and conflicts(mode, m)]

    def request(self, session, command) -> str:
        mode = COMMAND_LOCK[command]
        if self.blockers(session, mode, self.queue):
            self.queue.append((session, mode))
            return "waiting"
        self.held.append((session, mode))
        return "granted"

    def finish(self, session):
        """Commit, rollback, or lock_timeout: the session leaves holders and queue."""
        self.held = [h for h in self.held if h[0] != session]
        waiting, self.queue = [w for w in self.queue if w[0] != session], []
        for s, m in waiting:  # wake waiters in order; each still respects those ahead of it
            (self.queue if self.blockers(s, m, self.queue) else self.held).append((s, m))

    def blocking_pids(self, session):
        i = next(i for i, (s, _) in enumerate(self.queue) if s == session)
        return self.blockers(session, self.queue[i][1], self.queue[:i])
