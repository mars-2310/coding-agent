import os
import requests
import random
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage
from langchain_core.tools import Tool
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import add_messages
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI()

query = input("Enter your prompt: ")

# response = llm.invoke(query)
# print(f"User query: {query}")
# print(response)

class PlannerState(TypedDict):

    query: Annotated["str", "User's query"]
    environment: Annotated["dict", "Representation of current environment"]
    goals: Annotated["list", "List of agent goals"]
    actions: Annotated["list", "List of currently available actions"]
    metadata: Annotated["dict", "Metadata information"]
    response: Annotated["dict", { "steps": [], "explanations": [], "data": {}}]


planner = StateGraph(PlannerState)
planner.add_node()