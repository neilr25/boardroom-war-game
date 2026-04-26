"""Minimal crew test with larger token budgets to avoid empty responses."""
import os
os.environ["OPENAI_API_KEY"] = "301524cdd35744f8b16eebe1d8d84863.H2ucMytOprRJAPRo5GwzJkPT"
os.environ["OPENAI_BASE_URL"] = "https://ollama.com/v1"

from crewai import Agent, Task, Crew, Process, LLM

manager = Agent(
    role="Board Chair",
    goal="Oversee the evaluation",
    backstory="Ex-McKinsey partner.",
    llm=LLM(model="openai/gemma4:31b:cloud", temperature=0.3, max_tokens=500),
    allow_delegation=True,
)

agent = Agent(
    role="CEO",
    goal="Pitch an idea",
    backstory="Charismatic founder.",
    llm=LLM(model="openai/gemma4:31b:cloud", temperature=0.7, max_tokens=500),
    allow_delegation=False,
)

task = Task(
    description="Pitch the idea: a smart water bottle that tracks hydration. Keep it to 2 sentences.",
    expected_output="A 2-sentence pitch.",
    agent=agent,
)

crew = Crew(
    agents=[agent],
    tasks=[task],
    process=Process.hierarchical,
    manager_agent=manager,
    manager_llm=LLM(model="openai/gemma4:31b:cloud", temperature=0.3, max_tokens=500),
    verbose=False,
    planning=False,
)

result = crew.kickoff()
print("RESULT:", result)
