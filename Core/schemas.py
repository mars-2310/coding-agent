# schemas.py: Pydantic models
# - Tool inputs (args_schema): ReadFileInput, EditFileInput, WriteFileInput, SearchInput, RunCommandInput
# - Structured LLM output: PlanStep, Plan, TodoItem, ToolResult

from pydantic import BaseModel, Field
from typing import Literal, Any

class ReadFileInput(BaseModel):
    path: str = Field(description="Path of the file to read, relative to the agent's current directory.")
    start_line: int | None = Field(default=None, ge=1, description="First line to return, counting from 1. Defaults to the start of the file.")
    end_line: int | None = Field(default=None, ge=1, description="Last line to return, inclusive. Defaults to the end of the file.")


class EditFileInput(BaseModel):
    path: str = Field(description="Path of an existing file, relative to the agent's current directory.")
    old_text: str = Field(description="Exact text to replace, copied from the file character for character, including indentation and line breaks. Read the file first to get it right.")
    new_text: str = Field(description="Text to put in place of old_text, with the indentation it should have in the file. An empty string deletes old_text.")


class WriteFileInput(BaseModel):
    path: str = Field(description="Path of the file to write, relative to the agent's current directory.")
    content: str = Field(description="Complete content of the file. It replaces everything in the file, so include every line, not just the changed part.")
    overwrite: bool = Field(default=False, description="Must be true to replace a file that already exists. Leave false when creating a new file, so an existing file is never lost by accident.")


class SearchInput(BaseModel):
    query: str = Field(min_length=1, description="Python regular expression to search for, e.g. 'def load_config' or 'import (os|sys)'. Put a backslash before special characters such as ( . * to match them literally.")
    path: str = Field(default=".", description="Directory or file to search, relative to the agent's current directory.")
    file_pattern: str = Field(default="*", description="Only search files whose name matches this glob, e.g. '*.py' or 'test_*'. Defaults to all files.")
    case_sensitive: bool = Field(default=False, description="Match letter case exactly. By default 'todo' also finds 'TODO'.")


class RunCommandInput(BaseModel):
    command: str = Field(min_length=1, description="Command to execute.")
    cwd: str = Field(default=".", description="Working directory, relative to the agent's current directory.")
    timeout: int = Field(default=30, ge=1, le=600, description="Maximum run time in seconds before the command is stopped.")


##LLM Outputs

class PlanStep(BaseModel):
    step_id: int = Field(ge=1, description="Position of this step in the plan, starting at 1.")
    description: str = Field(description="One sentence saying what this step does and why.")
    action: str = Field(description="Tool name or operation needed for this step.")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments for the tool named in `action`, using that tool's parameter names.",
    )
    status: Literal["pending", "in_progress", "completed", "failed"] = Field(
        default="pending",
        description="Execution progress. Set by the agent while running; the planner leaves it as 'pending'.",
    )


class Plan(BaseModel):
    goal: str = Field(description="The user's request restated as one concrete goal.")
    steps: list[PlanStep] = Field(min_length=1, description="Ordered steps that together achieve the goal.")
    reasoning_summary: str = Field(default="", description="Brief explanation of why the plan is ordered this way.")


class TodoItem(BaseModel):
    task_id: str = Field(description="Short unique identifier for this task.")
    description: str = Field(description="What needs to be done, in one sentence.")
    status: Literal["pending", "in_progress", "completed", "failed"] = Field(
        default="pending", description="Current progress of the task."
    )
    step_id: int | None = Field(default=None, ge=1, description="The plan step this task belongs to, if any.")


class ToolResult(BaseModel):
    tool_name: str
    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
