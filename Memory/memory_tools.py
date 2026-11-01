# - todo_write(items: list[TodoItem]) -> str
# - todo_read() -> list[TodoItem]
# - remember(fact: str) -> str
# - recall(query: str) -> list[str]
# - ask_user(question: str) -> str
# - finish(summary: str) -> str
# - tools = [...]

import json
import re
from datetime import date
from langchain_core.tools import tool
from Core.workspace import get_workspace
from Core.schemas import TodoItem
from pydantic import ValidationError

# Facts survive between runs in a JSON file inside the workspace.
MEMORY_FILE = get_workspace() / ".agent" / "memory.json"
TODO_FILE = get_workspace() / ".agent" / "todo.json"

def _load_facts() -> list[dict]:
    try:
        return json.loads(MEMORY_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []


# Common words that would make almost every fact look like a match.
STOPWORDS = {"a", "an", "the", "is", "are", "to", "of", "in", "on", "for", "and", "or", "with", "how",
             "do", "does", "i", "we", "it", "what", "where", "when", "which", "from", "by", "be"}

def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower())) - STOPWORDS


@tool(parse_docstring=True)
def remember(fact: str) -> str:
    """Save a fact so it can be recalled in later runs. Facts are kept in .agent/memory.json in the workspace and persist between runs.

    Save things that will still be useful later and aren't obvious from the code, e.g. how to run the project's tests, a user preference, or the fix for a recurring problem. Don't save temporary details of the current task. Exact duplicates are ignored.

    Args:
        fact: One self-contained fact, written so it makes sense without the current conversation, e.g. 'Tests are run with pytest from the repo root'.
    """
    fact = fact.strip()
    if not fact:
        return "Error: fact is empty"

    facts = _load_facts()
    if any(f["fact"].lower() == fact.lower() for f in facts):
        return "Already remembered"

    facts.append({"fact": fact, "saved": date.today().isoformat()})
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE.write_text(json.dumps(facts, indent=2))
    return f"Remembered ({len(facts)} facts saved)"


@tool(parse_docstring=True)
def recall(query: str, max_results: int = 5) -> str:
    """Look up remembered facts that share words with the query, best matches first, each with the date it was saved.

    Use this at the start of a task to check for relevant notes from earlier runs, e.g. recall('run tests') before running tests. Matching is by shared words, not by meaning, so try a few different keywords if nothing comes back.

    Args:
        query: Keywords to look for, e.g. 'run tests' or 'database setup'.
        max_results: Maximum number of facts to return. Defaults to 5.
    """
    facts = _load_facts()
    if not facts:
        return "Nothing has been remembered yet"

    query_words = _words(query)
    scored = [(len(query_words & _words(f["fact"])), f) for f in facts]
    matches = [f for score, f in sorted(scored, key=lambda s: s[0], reverse=True) if score > 0]
    if not matches:
        return f"No remembered facts match {query!r}"

    return "\n".join(f"- {f['fact']} (saved {f['saved']})" for f in matches[:max(max_results, 1)])


@tool(parse_docstring=True)
def ask_user(question: str) -> str:
    """Ask the user a question and wait for their typed answer, which is returned as text.

    Use this only when you cannot continue without the user: the request is ambiguous, a choice is theirs to make, or an action is risky, such as deleting files, installing packages or committing. Don't ask for things you can find out with other tools. Ask one clear, specific question, and offer options when you can.

    Args:
        question: The question to ask, e.g. 'Should the new function go in utils.py or in a new file?'
    """
    # Simple terminal version. Once the graph has a checkpointer, LangGraph's interrupt() can replace this.
    try:
        answer = input(f"\n[agent asks] {question}\n> ").strip()
    except EOFError:
        return "Error: no user is available to answer"

    return answer or "The user gave no answer"


@tool(parse_docstring=True)
def todo_write(items: list[TodoItem]) -> str:
    """Replace the entire working checklist with the supplied tasks.

    Use this for tasks with three or more steps. Update task statuses as work
    progresses and provide the complete checklist on every call.

    Args:
        items: The complete list of tasks, including IDs, descriptions,
            statuses, and optional plan step IDs.
    """
    TODO_FILE.parent.mkdir(parents=True, exist_ok=True)
    TODO_FILE.write_text(
        json.dumps(
            [item.model_dump(mode="json") for item in items],
            indent=2,
        )
    )
    return f"Saved {len(items)} todo items."


@tool(parse_docstring=True)
def todo_read() -> str:
    """Read the saved checklist as formatted text.

    Use this to review task statuses and identify unfinished work.
    Returns 'No todos yet.' if the checklist is missing, empty, or invalid.
    """
    try:
        data = json.loads(TODO_FILE.read_text())
        items = [TodoItem.model_validate(item) for item in data]
    except (FileNotFoundError, json.JSONDecodeError, ValidationError, TypeError):
        return "No todos yet."

    if not items:
        return "No todos yet."

    return "\n".join(
        f"[{item.status}] {item.task_id}. {item.description}"
        + (f" (step {item.step_id})" if item.step_id is not None else "")
        for item in items
    )


@tool(parse_docstring=True)
def finish(summary: str) -> str:
    """Signal that the agent has finished its task.

    Call this only as the final step, once the work is complete and verified.
    Do not call it while required tasks remain unfinished.

    Args:
        summary: A concise summary of completed work and any remaining issues.
    """
    return f"Task finished: {summary}"


tools = [remember, recall, ask_user, todo_read, todo_write, finish]
