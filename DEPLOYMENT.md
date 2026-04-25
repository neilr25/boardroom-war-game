# Deployment Guide

## GitHub Repository Setup

The code is complete and committed locally. To push to GitHub, follow these steps when you return:

### 1. Authenticate GitHub CLI

```powershell
cd C:\Projects\crewai\boardroom
gh auth login
# Follow prompts: HTTPS, authenticate in browser
```

### 2. Create Repository (choose one)

**Option A: Private repo on your own account**
```powershell
gh repo create boardroom-war-game --private --source=. --push
```

**Option B: Public repo**
```powershell
gh repo create boardroom-war-game --public --source=. --push
```

**Option C: Org repo (if applicable)**
```powershell
gh repo create your-org/boardroom-war-game --private --source=. --push
```

### 3. Verify

```powershell
gh repo view boardroom-war-game --web
```

## What's Already Done

- All source code committed to local git
- .gitignore excludes artifacts
- README.md with usage instructions
- PLAN.md with decisions recorded

## Next Steps After Push

1. Copy `.env.example` to `.env` and add your `OLLAMA_CLOUD_API_KEY`
2. Run `python main.py --idea "Your idea" --dry-run` to verify
3. Run `python main.py --idea "Your idea" --mock` for a dry run with no API calls
4. Run `python main.py --idea "Your idea"` for live execution
