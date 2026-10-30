# state.py: TypedDict and LangGraph types
# - AgentState: fields messages (using add_messages), plan, current_step, todos, iterations, done

from typing import TypedDict, Annotated, Any
from langgraph.graph import add_messages
from langchain_core.messages import AnyMessage
from Core.schemas import PlanStep, TodoItem

class PlannerState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    query: str
    environment: dict[str, Any]
    goals: list[str]
    actions: list[dict[str, Any]]
    metadata: dict[str, Any]
    response: list[PlanStep]


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    plan: list[PlanStep]
    current_step: int
    todos: list[TodoItem]
    iterations: int
    done: bool
