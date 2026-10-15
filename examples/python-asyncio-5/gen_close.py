"""close() raises GeneratorExit at the paused yield, so cleanup code runs."""


def turnstile():
    people = 0
    try:
        while True:
            yield
            people += 1
    except GeneratorExit:
        print("gate closing")
        return people
    finally:
        print("lights off")


gate = turnstile()
next(gate)  # run to the first yield
gate.send(None)
gate.send(None)
print("close() returned", gate.close())
print("closed again:", gate.close())
