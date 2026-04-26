"""Test which models are available on Ollama Cloud."""
from crewai import LLM

api_key = "301524cdd35744f8b16eebe1d8d84863.H2ucMytOprRJAPRo5GwzJkPT"
base_url = "https://ollama.com/v1"

models_to_test = [
    "openai/kimi-k2.6:cloud",
    "openai/kimi-k2.5:cloud",
    "openai/gemma4:31b:cloud",
    "openai/gemma4:27b:cloud",
    "openai/gemma4:9b:cloud",
    "openai/deepseek-v4-pro:cloud",
    "openai/deepseek-v4:cloud", 
    "openai/deepseek-v4-flash:cloud",
    "openai/glm-5.1:cloud",
    "openai/glm-5:cloud",
    "openai/qwen2.5:72b:cloud",
    "openai/mistral-large:cloud",
    "openai/mistral-nemo:cloud",
]

results = {}
for model in models_to_test:
    llm = LLM(model=model, base_url=base_url, api_key=api_key, temperature=0.1, max_tokens=20)
    try:
        result = llm.call("Reply with only the word HELLO")
        status = "OK"
    except Exception as e:
        status = f"FAIL: {type(e).__name__}"
    results[model] = status
    print(f"{model:45} -> {status}")

print("\n" + "="*60)
print("AVAILABLE MODELS:")
available = [m for m, s in results.items() if s == "OK"]
for m in available:
    print(f"  - {m}")

print(f"\nTotal: {len(available)}/{len(models_to_test)} available")
