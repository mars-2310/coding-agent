# llm.py: LangChain
# - get_llm(provider: str = "ollama") -> BaseChatModel
# - get_llm_with_tools(tools: list) -> Runnable, which uses .bind_tools()
# - get_structured_llm(schema: type[BaseModel]) -> Runnable, which uses .with_structured_output()