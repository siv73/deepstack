"""throw() raises an exception inside the generator, at the yield where it paused."""


class OutOfStock(Exception):
    pass


def packing_line():
    while True:
        try:
            item = yield
            print("packed", item)
        except OutOfStock as error:
            print("skipped", error)


line = packing_line()
next(line)  # run to the first yield
line.send("soap")
line.throw(OutOfStock("rice"))  # raised at the paused yield, caught inside
line.send("tea")  # the generator is still alive
