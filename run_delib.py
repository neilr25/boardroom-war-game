import os, subprocess, sys

os.environ['OLLAMA_CLOUD_API_KEY'] = '301524cdd35744f8b16eebe1d8d84863.H2ucMytOprRJAPRo5GwzJkPT'
os.environ['OPENAI_API_KEY'] = '301524cdd35744f8b16eebe1d8d84863.H2ucMytOprRJAPRo5GwzJkPT'
os.environ['OPENAI_BASE_URL'] = 'https://ollama.com/v1'

with open('delib_log.txt', 'w') as log:
    proc = subprocess.Popen(
        [
            sys.executable, 'main.py',
            '--idea', 'AI restaurant concierge booking tables by voice calls',
            '--session-id', 'live-deliberation-running',
            '--rounds', '1'
        ],
        stdout=log,
        stderr=subprocess.STDOUT,
        cwd='C:/Projects/crewai/boardroom'
    )
    print(f"Started deliberation PID={proc.pid}")
    
    # Wait up to 1 hour for completion
    try:
        proc.wait(timeout=3600)
    except subprocess.TimeoutExpired:
        print("Timed out after 1 hour")
        proc.kill()
        proc.wait()
    print(f"Exit code: {proc.returncode}")
