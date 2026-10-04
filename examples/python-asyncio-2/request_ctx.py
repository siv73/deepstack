"""A request id that follows the request through tasks and threads."""

import asyncio
import contextvars

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def log_line(msg: str) -> str:
    return f"[{request_id.get()}] {msg}"


async def child(out: list[str]) -> None:
    out.append(log_line("child"))
    request_id.set("changed-by-child")  # only changes the child's copy


async def handle(rid: str, out: list[str]) -> None:
    request_id.set(rid)
    async with asyncio.TaskGroup() as tg:
        tg.create_task(child(out))  # the task gets a copy of the current context
    await asyncio.sleep(0.01)  # let other requests run in between
    out.append(log_line("parent"))
    out.append(await asyncio.to_thread(log_line, "thread"))
