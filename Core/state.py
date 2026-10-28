# state.py: TypedDict and LangGraph types
# - AgentState: fields messages (using add_messages), plan, current_step, todos, iterations, done
# - Move your PlannerState here from planner.py

from typing import TypedDict, Annotated, Any
from langgraph.graph import add_messages
from langchain_core.messages import AnyMessage

class PlannerState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    query: str
    environment: dict[str, Any]
    goals: list[str]
    actions: list[dict[str, Any]]
    metadata: dict[str, Any]
    response: list[dict[str, Any]]


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    plan: list[dict[str, Any]]
    current_step: int
    todos: list[dict[str, Any]]
    iterations: int
    done: bool