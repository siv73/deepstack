"""contextvars: a value that belongs to the current context, not to the module."""

import contextvars

request_id = contextvars.ContextVar("request_id", default="-")  # at module level, never in a closure
shopper_tier = contextvars.ContextVar("shopper_tier")  # no default


def show(where):
    print(f"{where:40} request_id = {request_id.get()}")


show("nothing set yet")
token = request_id.set("shopper-1")
show("after set('shopper-1')")
request_id.reset(token)
show("after reset(token)")

try:
    shopper_tier.get()
except LookupError:
    print(f"{'a variable with no value and no default':40} get() raises LookupError")

ctx = contextvars.copy_context()  # a snapshot of the current context


def inside():
    request_id.set("shopper-2")  # recorded in ctx, the context being run
    show("inside ctx.run(), after set")


ctx.run(inside)
show("outside, after ctx.run() returned")
print(f"{'the snapshot itself':40} ctx[request_id] = {ctx[request_id]}")

with request_id.set("shopper-3"):  # 3.14: the Token is a context manager
    show("inside with request_id.set('shopper-3')")
show("after the with block")
