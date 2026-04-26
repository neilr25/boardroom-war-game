#!/usr/bin/env python3
"""
Minimal test script to verify CrewAI + Ollama Cloud integration.
Forces environment variables before any imports to ensure proper configuration.
"""
import os

# Force environment variables BEFORE any imports
os.environ["OPENAI_API_KEY"] = "301524cdd35744f8b16eebe1d8d84863.H2ucMytOprRJAPRo5GwzJkPT"
os.environ["OPENAI_BASE_URL"] = "https://ollama.com/v1"

# Now import CrewAI components
from crewai import Agent, Task, Crew, LLM

# Create CrewAI LLM instance with explicit Ollama Cloud configuration
llm = LLM(
    model="openai/gemma4:31b:cloud",
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["OPENAI_BASE_URL"],
    temperature=0.1,
    max_tokens=50
)

# Create agent with the configured LLM
agent = Agent(
    role="Test Agent",
    goal="Respond to the test task",
    backstory="You are a test agent configured to work with Ollama Cloud",
    llm=llm,
    verbose=True,
    allow_delegation=False
)

# Create a simple test task
task = Task(
    description="Say 'Hello from Ollama Cloud' and nothing else",
    agent=agent,
    expected_output="A greeting message from Ollama Cloud"
)

# Create crew with no planning
crew = Crew(
    agents=[agent],
    tasks=[task],
    verbose=True
)

# Execute and print results
print("Starting CrewAI test with Ollama Cloud...")
result = crew.kickoff()
print("\n=== Test Result ===")
print(result)