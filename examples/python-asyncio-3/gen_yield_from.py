"""yield from hands control to another generator and gets its return value."""


def weigh(label):
    weight = yield f"weigh {label}"  # this request goes all the way out to the caller
    return weight


def parcel_desk():
    total = 0
    for label in ("box-1", "box-2"):
        total += yield from weigh(label)  # the value sent in reaches weigh() directly
    return total


desk = parcel_desk()
print(desk.send(None))
print(desk.send(3))
try:
    desk.send(5)
except StopIteration as stop:
    print("total weight:", stop.value)
