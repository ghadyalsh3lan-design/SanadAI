"""Smoke test 1: confirm we can talk to the LLM."""
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

llm = ChatGroq(model="llama-3.3-70b-versatile")
response = llm.invoke("Say hi in exactly one word.")
print(response.content)