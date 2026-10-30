# llm.py: LangChain
# - get_llm(model: str = "qwen3") -> BaseChatModel
# - get_llm_with_tools(tools: list, model: str = "qwen3") -> Runnable, which uses .bind_tools()
# - get_structured_llm(schema: type[BaseModel], model: str = "qwen3") -> Runnable, which uses .with_structured_output()
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_ollama import ChatOllama
from pydantic import BaseModel

DEFAULT_MODEL = "qwen3"

# Ollama's default context window can be as small as 4096 tokens, and the tool descriptions alone
# take several thousand. 16k leaves room for the conversation and still fits in 16 GB of RAM.
CONTEXT_WINDOW = 16384

def get_llm(model: str = DEFAULT_MODEL) -> BaseChatModel:
    """
    Initialize and return a local chat model through Ollama.

    Supported models (both support tool calling):
        - qwen3: general reasoning and planning (qwen3:8b)
        - qwen-coder: code-focused tasks (qwen2.5-coder:7b)
    """
    model = model.lower()

    if model == "qwen3":
        return ChatOllama(
            model='qwen3:8b',
            temperature=0.2,
            num_ctx=CONTEXT_WINDOW,
            reasoning=False,  # skip the <think> phase for faster, cleaner tool calls
        )
    if model == "qwen-coder":
        return ChatOllama(
            model='qwen2.5-coder:7b',
            temperature=0.2,
            num_ctx=CONTEXT_WINDOW,
        )

    raise ValueError(
        f"Unsupported model: {model}. "
        "Supported models: qwen3, qwen-coder."
    )


def get_llm_with_tools(tools: list[BaseTool], model: str = DEFAULT_MODEL) -> Runnable:
    """
    Return an LLM configured to call the supplied tools.
    """
    llm = get_llm(model)
    return llm.bind_tools(tools)


def get_structured_llm(schema: type[BaseModel], model: str = DEFAULT_MODEL) -> Runnable:
    """
    Return an LLM configured to produce output matching a Pydantic schema.
    """
    llm = get_llm(model)
    return llm.with_structured_output(schema)
