"""Every socket is a file descriptor, and a process may only hold so many."""

import errno
import resource
import socket

soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
resource.setrlimit(resource.RLIMIT_NOFILE, (64, hard))  # lower our own soft limit to 64
socks = []
try:
    while True:
        socks.append(socket.socket())  # one new file descriptor each
except OSError as e:
    print(f"highest fd that worked: {socks[-1].fileno()}")
    print(f"next socket(): OSError {errno.errorcode[e.errno]} ({e.strerror})")
finally:
    for s in socks:
        s.close()
    resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))
