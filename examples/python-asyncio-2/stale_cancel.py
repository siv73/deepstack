"""Refusing a cancel without uncancel() leaves the task marked as 'being cancelled'."""

import asyncio


async def _fails() -> None:
    raise ValueError("bad row")


async def refuse_then_use_taskgroup(call_uncancel: bool) -> str:
    me = asyncio.current_task()
    asyncio.get_running_loop().call_later(0.01, me.cancel)
    try:
        await asyncio.sleep(1)
    except asyncio.CancelledError:
        if call_uncancel:
            me.uncancel()  # we refused the cancel, so remove its record too
    try:
        async with asyncio.TaskGroup() as tg:  # later, unrelated work fails
            tg.create_task(_fails())
            await asyncio.sleep(1)
    except* ValueError:
        pass  # handled
    return "done"
