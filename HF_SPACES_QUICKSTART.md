# Quick Start: Deploy to Hugging Face Spaces

## TL;DR

Your repository is now ready to deploy to Hugging Face Spaces. Here's what you need to do:

### 1. Get a Gemini API Key
- Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
- Create an API key (free tier available)
- Copy the key

### 2. Create a Hugging Face Space

```bash
# Install the CLI (if not already installed)
pip install huggingface_hub

# Login to HF
huggingface-cli login
# Paste your HF API token when prompted

# Create the Space
huggingface-cli repo create recovery-iq --type space --space_sdk docker

# Add HF as a git remote
git remote add hf https://huggingface.co/spaces/<your-username>/recovery-iq
```

### 3. Push Your Code

```bash
git add Dockerfile README.md HUGGINGFACE_DEPLOYMENT.md HF_SPACES_QUICKSTART.md prototype/requirements.txt
git commit -m "Add Hugging Face Spaces Docker configuration"
git push hf main
```

HF will automatically build and deploy (takes 5-10 minutes).

### 4. Add the API Key as a Secret

In the HF Space UI:
1. Go to **Settings** → **Repository secrets**
2. Add `GEMINI_API_KEY` = your Google Gemini API key

### 5. Verify It's Working

Wait for the Space to show **"Running"**, then:

```bash
SPACE_URL="https://<your-username>-recovery-iq.hf.space"

# Health check
curl $SPACE_URL/health

# Agent card
curl $SPACE_URL/.well-known/agent-card.json | jq '.name'

# Full test
cd prototype
python test_public_url.py $SPACE_URL --with-case
```

### 6. Share Your Agent Card URL

Use this URL with the Prompt Opinion Marketplace:
```
https://<your-username>-recovery-iq.hf.space/.well-known/agent-card.json
```

## What Was Added

✅ **Dockerfile** — Docker configuration for HF Spaces (runs on port 7860)
✅ **README.md** — Updated with HF Spaces frontmatter and A2A protocol info
✅ **requirements.txt** — Updated package versions for better compatibility
✅ **HUGGINGFACE_DEPLOYMENT.md** — Detailed deployment guide
✅ **HF_SPACES_QUICKSTART.md** — This file

## Troubleshooting

### Build is taking too long
- This is normal (5-10 min), especially if it's the first build
- Check the Logs tab in the Space for any errors

### Agent card not found (404)
- Space might still be building
- Refresh the page after a few minutes
- Check Logs for startup errors

### A2A requests timing out
- First request might be slow due to LLM processing
- Try increasing timeout: `python test_public_url.py <url> --timeout 120`
- Check if GEMINI_API_KEY is set in the Space secrets

### Space is "sleeping"
- Free tier HF Spaces sleep after inactivity
- First request wakes it up (~30s delay)
- For Always On, upgrade to Pro tier

## Next Steps

After deployment, you can:
1. Share your agent card URL with judges/reviewers
2. Monitor requests in the Space Logs
3. Iterate on the clinical summaries based on feedback
4. (Optional) Upgrade to HF Pro for Always On and custom domains

## Questions?

- **Deployment issues?** Check `HUGGINGFACE_DEPLOYMENT.md`
- **A2A protocol?** See `prototype/A2A_DEPLOYMENT.md`
- **How the agents work?** See `SYSTEM_ARCHITECTURE_CHART.md`

Good luck! 🚀
