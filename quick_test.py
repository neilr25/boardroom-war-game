"""Run a single agent quick test to see if deliberation works at all."""
import os
os.environ["OPENAI_API_KEY"] = "301524cdd35744f8b16eebe1d8d84863.H2ucMytOprRJAPRo5GwzJkPT"
os.environ["OPENAI_BASE_URL"] = "https://ollama.com/v1"

from crewai import Agent, Task, Crew, LLM

agent = Agent(
    role="CEO",
    goal="Test",
    backstory="Test",
    llm=LLM(model="openai/gemma4:31b:cloud", api_key=os.environ["OPENAI_API_KEY"], base_url="https://ollama.com/v1", temperature=0.1, max_tokens=20),
    allow_delegation=False,
)

task = Task(description="Say hello in 5 words.", expected_output="Hello", agent=agent)

crew = Crew(agents=[agent], tasks=[task], verbose=False)
print("Starting...")
try:
    result = crew.kickoff()
    print("Done:", result)
except Exception as e:
    print("Error:", type(e).__name__, e)
