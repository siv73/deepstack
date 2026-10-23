"""select() cannot watch a file descriptor numbered 1024 or higher; epoll can."""

import selectors
import socket

socks = [socket.socket() for _ in range(1030)]  # push fd numbers past 1023
high = socks[-1]
print(f"highest fd number is over 1023: {high.fileno() > 1023}")
for cls in (selectors.SelectSelector, selectors.EpollSelector):
    with cls() as sel:
        sel.register(high, selectors.EVENT_READ)
        try:
            sel.select(timeout=0)
            print(f"{cls.__name__}: select() works")
        except ValueError as e:
            print(f"{cls.__name__}: ValueError: {e}")
for s in socks:
    s.close()
