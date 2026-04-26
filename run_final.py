import os, subprocess, sys, time

os.environ['OLLAMA_CLOUD_API_KEY'] = '301524cdd35744f8b16eebe1d8d84863.H2ucMytOprRJAPRo5GwzJkPT'
os.environ['OPENAI_API_KEY'] = '301524cdd35744f8b16eebe1d8d84863.H2ucMytOprRJAPRo5GwzJkPT'
os.environ['OPENAI_BASE_URL'] = 'https://ollama.com/v1'

log = open('delib_final.txt', 'w', buffering=1)
proc = subprocess.Popen(
    [sys.executable, 'main.py',
     '--idea', 'AI restaurant voice concierge',
     '--session-id', 'live-delib-final',
     '--rounds', '1'],
    stdout=log,
    stderr=subprocess.STDOUT,
    cwd='C:/Projects/crewai/boardroom'
)

print(f'PID={proc.pid}', file=log)
print(f'Started at {time.strftime(\"%H:%M:%S\")}', file=log)
log.flush()

# Main wait loop - print status every 30s
try:
    for i in range(180):  # 90 minutes max
        time.sleep(30)
        if proc.poll() is not None:
            print(f'Finished at {time.strftime(\"%H:%M:%S\")} with exit code {proc.returncode}', file=log)
            break
        print(f'Still running... {time.strftime(\"%H:%M:%S\")}', file=log)
        log.flush()
except KeyboardInterrupt:
    print('Interrupted', file=log)
    proc.kill()

log.close()
