"""Minimal live test — 1 agent, 1 task to verify Ollama Cloud works."""
import os
os.environ["OPENAI_API_KEY"] = "301524cdd35744f8b16eebe1d8d84863.H2ucMytOprRJAPRo5GwzJkPT"
os.environ["OPENAI_BASE_URL"] = "https://ollama.com/v1"

from crewai import Agent, Task, Crew, Process, LLM

agent = Agent(
    role="CEO",
    goal="Pitch a startup idea",
    backstory="You are a charismatic founder.",
    llm=LLM(model="openai/gemma4:31b:cloud", temperature=0.7, max_tokens=100),
    allow_delegation=False,
)

task = Task(
    description="Pitch the idea: a smart water bottle that tracks hydration.",
    expected_output="A 2-sentence pitch.",
    agent=agent,
)

crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
result = crew.kickoff()
print("RESULT:", result)

# Also test a simple calculator tool call
from tools import CalculatorTool
calc = CalculatorTool()
print("CALC:", calc._run("10 * 5"))
