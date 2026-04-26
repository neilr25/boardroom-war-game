"""Quick model test. Only test the models we need to replace."""
import os
os.environ["OPENAI_API_KEY"] = "301524cdd35744f8b16eebe1d8d84863.H2ucMytOprRJAPRo5GwzJkPT"

from crewai import LLM

# Test only relevant replacements for deepseek-v4-pro
models = [
    "openai/deepseek-v4:cloud",
    "openai/qwen2.5:72b:cloud", 
    "openai/gemma4:31b:cloud",
    "openai/kimi-k2.5:cloud",
]

for model in models:
    llm = LLM(model=model, base_url="https://ollama.com/v1", temperature=0.1, max_tokens=10)
    try:
        result = llm.call("Say hello")
        print(f"OK:  {model:45} -> {str(result)[:40]}")
    except Exception as e:
        print(f"FAIL: {model:45} -> {type(e).__name__}: {getattr(e, 'status_code', '')}")
