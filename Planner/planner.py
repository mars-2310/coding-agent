# - plan_node(state) -> dict: the LLM returns a Plan as structured output
# - replan_node(state) -> dict: updates the plan after a step fails
# - build_planner_graph() -> CompiledGraph


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
from Core.state import PlannerState

load_dotenv()

llm = ChatOpenAI()

query = input("Enter your prompt: ")

# response = llm.invoke(query)
# print(f"User query: {query}")
# print(response)

planner = StateGraph(PlannerState)
planner.add_node()