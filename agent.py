from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

load_dotenv()


class State(TypedDict):
    pass

# graph = StateGraph(State)
# graph.add_node("")

model = ChatOllama(
    model='gemma:latest',
    temperature=0.2,
    num_ctx=4096
)

messages = [
    SystemMessage(content="You are an expert developer instructor."),
    HumanMessage(content='Write a python function for Fibonacci series in a structured JSON format')
]

response = model.invoke(messages)
print(response.content)