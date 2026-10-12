"""send() resumes a generator and gives the paused yield a value."""


def bill():
    total = 0
    while True:
        price = yield total  # hand out the total, then wait for the next price
        total += price


counter = bill()
print(counter.send(None))  # starts it: runs to the first yield
print(counter.send(120))
print(counter.send(45))

try:
    bill().send(5)  # a brand-new generator has no paused yield to receive 5
except TypeError as error:
    print("TypeError:", error)
