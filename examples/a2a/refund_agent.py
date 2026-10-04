"""The agent's logic: a Task that may pause to ask for the order ID."""

import re

from a2a.helpers import new_data_artifact, new_task_from_user_message, new_text_status_update_event
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import TaskArtifactUpdateEvent, TaskState

REFUNDS = {"ORD-1234": "processed", "ORD-5678": "pending"}  # stand-in for the payments DB


class RefundAgent(AgentExecutor):
    async def execute(self, context: RequestContext, queue: EventQueue) -> None:
        task = context.current_task or new_task_from_user_message(context.message)
        if not context.current_task:
            await queue.enqueue_event(task)  # a Task must be the first event

        def say(state, text):
            return new_text_status_update_event(task.id, task.context_id, state, text)

        order = re.search(r"ORD-\d+", context.get_user_input())
        if not order:  # pause and ask: the client answers with the same taskId
            await queue.enqueue_event(say(TaskState.TASK_STATE_INPUT_REQUIRED, "Which order ID?"))
            return
        result = {"order": order.group(), "refund": REFUNDS.get(order.group(), "not_found")}
        artifact = new_data_artifact(name="refund-status", data=result)
        event = TaskArtifactUpdateEvent(task_id=task.id, context_id=task.context_id, artifact=artifact)
        await queue.enqueue_event(event)
        await queue.enqueue_event(say(TaskState.TASK_STATE_COMPLETED, "Done."))

    async def cancel(self, context: RequestContext, queue: EventQueue) -> None:
        task = context.current_task
        await queue.enqueue_event(
            new_text_status_update_event(task.id, task.context_id, TaskState.TASK_STATE_CANCELED, "Canceled.")
        )
