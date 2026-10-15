"""Close a socket without unregistering it, and the selector remembers a dead socket."""

import selectors
import socket

sel = selectors.DefaultSelector()
old = socket.socket()
old_fd = old.fileno()
sel.register(old, selectors.EVENT_READ, data="seller-a")
old.close()  # bug: closed while still registered
print(f"after close: the selector still holds {len(sel.get_map())} entry (for the dead socket)")

new = socket.socket()  # the OS hands out the lowest free number again
print(f"new socket reuses the same fd number: {new.fileno() == old_fd}")
try:
    sel.register(new, selectors.EVENT_READ, data="seller-b")
except KeyError as e:
    print(f"register(new socket) -> KeyError: ... {e.args[0].rsplit(') ', 1)[-1]}")

sel.unregister(old)  # the fix: unregister first, then close
sel.register(new, selectors.EVENT_READ, data="seller-b")
print(f"after unregistering the old one: new socket registered as {sel.get_key(new).data}")
new.close()
sel.close()
