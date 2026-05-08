# Deploying RecoveryIQ to Hugging Face Spaces

This guide explains how to deploy the RecoveryIntelligenceSystem to a Hugging Face Docker Space for public access.

## Prerequisites

- Hugging Face account (free tier works)
- Git CLI installed
- `huggingface_hub` CLI (optional but recommended)

## Step 1: Create a Hugging Face Space

### Option A: Using the Web UI

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces)
2. Click **"Create new Space"**
3. Fill in:
   - **Space name**: `recovery-iq` (or similar)
   - **License**: MIT
   - **SDK**: Docker
4. Click **"Create space"**

### Option B: Using the CLI

```bash
pip install huggingface_hub

huggingface-cli login
# Follow prompts to paste your HF API token

huggingface-cli repo create recovery-iq --type space --space_sdk docker
```

## Step 2: Clone and Configure the Repository

```bash
# Get the Space git URL from HF (visible after creation)
# Format: https://huggingface.co/spaces/<your-username>/recovery-iq

# Clone this RecoveryIntelligenceSystem repo
git clone https://github.com/yourusername/RecoveryIntelligenceSystem.git
cd RecoveryIntelligenceSystem

# Add HF Space as a remote
git remote add hf https://huggingface.co/spaces/<your-username>/recovery-iq
```

## Step 3: Set Up Environment Variables

In the HF Space settings:

1. Go to your Space: `https://huggingface.co/spaces/<your-username>/recovery-iq`
2. Click **Settings** → **Repository secrets**
3. Add a new secret:
   - **Name**: `GEMINI_API_KEY`
   - **Value**: Your Google Gemini API key

The app will read this from `os.environ` automatically via `Orchestrator.from_env()`.

### Getting a Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click **"Create API Key"** → **"Create API key in new project"**
3. Copy the API key and paste it into the HF Space secret

## Step 4: Push to Hugging Face

```bash
# Ensure you have all changes committed
git add Dockerfile README.md prototype/requirements.txt .gitignore
git commit -m "Add HF Spaces Docker configuration"

# Push to the HF Space
git push hf main
```

The HF platform will automatically:
1. Detect the `Dockerfile` at the repo root
2. Build the Docker image (5-10 minutes)
3. Deploy the container on port 7860
4. Provide a public HTTPS URL: `https://<your-username>-recovery-iq.hf.space`

## Step 5: Verify Deployment

Once the Space shows **"Running"** status:

### Health Check
```bash
SPACE_URL="https://<your-username>-recovery-iq.hf.space"

curl $SPACE_URL/health
# Expected: {"status":"ok"}
```

### Agent Card Discovery
```bash
curl $SPACE_URL/.well-known/agent-card.json | jq '.name'
# Expected: "hackathon_recovery_intelligence_agent"
```

### Full A2A Test
```bash
cd prototype
python test_public_url.py $SPACE_URL --with-case
```

Expected output:
```
✓ Agent card fetched successfully
✓ A2A invocation successful (status: completed)
✓ Plain-language opinion generated
```

## Step 6: Register with Prompt Opinion Marketplace

Share this URL with the Prompt Opinion Marketplace:
```
https://<your-username>-recovery-iq.hf.space/.well-known/agent-card.json
```

The Prompt Opinion system will:
1. Fetch your agent card
2. Discover the "PT Eligibility Review" capability
3. Register your A2A endpoint: `https://<your-username>-recovery-iq.hf.space/a2a`
4. Route PT authorization queries to your agent

## Monitoring

### View Logs

HF Spaces provides a **Logs** tab in the Space UI:
- Go to your Space settings
- Look for the **Logs** section
- Filter for errors or track request volumes

### Check Space Status

- **Running**: Container is healthy and serving requests
- **Building**: Docker image is being built (5-10 min)
- **Error**: Check logs for issues
- **Sleeping** (free tier): Space auto-sleeps after inactivity; first request wakes it (~30s)

### Manual Health Check

```bash
curl -I https://<your-username>-recovery-iq.hf.space/health
# Expected: HTTP/1.1 200 OK
```

## Troubleshooting

### Build Failed

Check the **Logs** tab:
- **Missing base image**: Ensure `FROM python:3.11-slim` is valid
- **Package installation error**: Verify all packages in `requirements.txt` are compatible
- **Timeout**: Build may take >10 min if embedding model is large

**Solutions:**
1. Try rebuilding manually: Space → **Restart**
2. Check if GEMINI_API_KEY is set in secrets
3. Verify `requirements.txt` has no syntax errors

### Slow First Request

Expected behavior on free tier:
- **First request**: ~30-60 seconds (Space wakes up + LLM processing)
- **Subsequent requests**: ~30-60 seconds (LLM processing)

To improve, consider upgrading to a paid Space with **Always On** mode.

### Agent Card Not Found

```bash
curl https://<your-username>-recovery-iq.hf.space/.well-known/agent-card.json
# Should return valid JSON, not HTML error
```

If returns HTML error:
- Space may still be building
- Check the **Logs** tab for startup errors
- Verify the app is listening on port 7860

### A2A Requests Timing Out

The LLM (Gemini) API may be rate-limited or slow:

**Check:**
1. Is `GEMINI_API_KEY` set correctly?
2. Have you exceeded free tier quota? (429 errors)
3. Is the LLM responding slowly? (check logs)

**Solutions:**
- Use a non-free tier Gemini key (paid project)
- Increase timeout in test: `python test_public_url.py <url> --timeout 120`
- Check Space logs for LLM error messages

## Advanced: Custom Domain

If you want to use a custom domain instead of `hf.space`:

1. Contact HF support (requires Pro account)
2. Configure a DNS CNAME to the HF Space URL
3. HF will handle HTTPS certificate provisioning

See [HF Spaces docs](https://huggingface.co/docs/hub/spaces) for details.

## Advanced: Docker Image Size

If the build is slow or frequently times out, you can optimize:

```dockerfile
# Skip pre-caching embeddings if size is an issue
# RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Instead, embeddings will be cached on first request (~10-20s slower startup)
```

Trade-off: Faster builds vs. slower cold starts.

## Updating the Deployment

To push updates:

```bash
# Make changes locally
git add .
git commit -m "Update: describe changes"
git push hf main
```

HF will auto-rebuild on every push.

## Cleanup

To delete the Space:

1. Go to Space settings
2. Scroll to **Danger Zone**
3. Click **Delete this space**

This removes the Space and all its data.

## Next Steps

1. ✅ Deploy to HF Spaces
2. ✅ Verify the A2A endpoint works
3. ✅ Share agent card URL with Prompt Opinion Marketplace
4. Monitor logs and iterate on clinical summaries
5. (Optional) Upgrade to Pro for Always On and custom domains

## References

- [HF Spaces Documentation](https://huggingface.co/docs/hub/spaces)
- [Docker Hub Python Images](https://hub.docker.com/_/python)
- [A2A Protocol](prototype/A2A_DEPLOYMENT.md)
- [Integration Checklist](prototype/PROMPT_OPINION_CHECKLIST.md)
