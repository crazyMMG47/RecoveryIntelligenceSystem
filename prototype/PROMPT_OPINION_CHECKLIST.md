# Prompt Opinion Integration Checklist

Before connecting to Prompt Opinion, ensure all dependencies are installed and the service is properly configured.

## Pre-Deployment Checklist

### 1. Install All Dependencies
```bash
cd prototype
pip install -r requirements.txt
```

**Verify installation:**
```bash
python -c "import sentence_transformers; print('✓ sentence-transformers installed')"
python -c "import google.genai; print('✓ google-genai installed')"
python -c "import fastapi; print('✓ fastapi installed')"
```

### 2. Environment Configuration
```bash
# Required
export GEMINI_API_KEY="your-gemini-api-key"

# Optional but recommended
export GEMINI_MODEL="gemini-2.5-flash-lite"
export EMBEDDINGS_CACHE_DIR="./cache"
```

### 3. Local Testing
```bash
# Test the service locally
python test_a2a_integration.py

# Expected output:
# ✓ Agent card structure is correct
# ✓ A2A response contains both structured and plain-language artifacts
# ✓ PromptOpinionAgent integration is working
```

### 4. Start the Service
```bash
# For public deployment, use your domain/public URL
# The base URL is auto-detected from incoming requests
uvicorn src.hackathon_agent.app:app --host 0.0.0.0 --port 8000
```

### 5. Verify Public Accessibility
```bash
# Test with public URL (adjust to your actual URL)
python test_public_url.py https://your-domain.com --with-case

# Expected output:
# ✓ Agent card fetched successfully
# ✓ A2A invocation successful
# ✓ Plain-language opinion generated
```

## Common Errors & Solutions

### Error: "sentence-transformers is required for embedding retrieval"

**Cause:** Dependencies not installed in Prompt Opinion's environment

**Solution:**
```bash
pip install -r requirements.txt
```

Or install sentence-transformers specifically:
```bash
pip install sentence-transformers
```

### Error: "Failed to load embedding model 'all-MiniLM-L6-v2'"

**Cause:** Model download failed (network, disk space, permissions)

**Solutions:**
```bash
# Check internet connectivity
ping huggingface.co

# Check available disk space
df -h /tmp

# Clear cache and retry
rm -rf ~/.cache/huggingface
pip install --upgrade sentence-transformers

# Set custom cache directory
export HF_HOME=/path/to/cache
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

### Error: "GEMINI_API_KEY is not set"

**Cause:** API key not in environment

**Solution:**
```bash
export GEMINI_API_KEY="your-api-key"
# Or create .env file
echo "GEMINI_API_KEY=your-api-key" > .env
```

### Error: "An error occurred while trying to communicate with the external agent"

**Cause:** Service is down or unreachable

**Solutions:**
1. Verify service is running: `curl https://your-domain.com/health`
2. Check logs for errors
3. Verify network connectivity from Prompt Opinion to your service
4. Check HTTPS certificate (if using domain)
5. Verify all dependencies are installed (see above)

## Deployment Checklist for Prompt Opinion

- [ ] All dependencies installed: `pip install -r requirements.txt`
- [ ] GEMINI_API_KEY environment variable set
- [ ] Service running on public URL with HTTPS
- [ ] Agent card accessible: `curl https://your-domain.com/.well-known/agent-card.json`
- [ ] A2A endpoint working: Health check passing
- [ ] Local tests passing: `python test_a2a_integration.py`
- [ ] Public URL test passing: `python test_public_url.py https://your-domain.com --with-case`
- [ ] Domain is public and Prompt Opinion can reach it
- [ ] HTTPS is properly configured (if required by Prompt Opinion)
- [ ] Logs are monitored for errors
- [ ] Backup/failover plan documented

## Integration Steps

1. **Prepare service**
   - Deploy to public URL with HTTPS
   - Ensure all dependencies installed
   - Run checklist above

2. **Register with Prompt Opinion**
   - Provide agent card URL: `https://your-domain.com/.well-known/agent-card.json`
   - Confirm their environment can reach your service
   - Provide your team's contact info for support

3. **Prompt Opinion discovers agent**
   - Prompt Opinion fetches `.well-known/agent-card.json`
   - Registers "PT Eligibility Review" skill
   - Configures A2A endpoint

4. **Test end-to-end**
   - User requests PT eligibility analysis in Prompt Opinion
   - Prompt Opinion sends JSON-RPC to `/a2a`
   - Your service returns structured + markdown response
   - Prompt Opinion displays summary to care coordinator

5. **Monitor and refine**
   - Watch logs for A2A requests
   - Collect feedback on clinical summaries
   - Iterate on plain-language generation

## Monitoring

### Check service health
```bash
curl https://your-domain.com/health
# Expected: {"status":"ok"}
```

### Check agent card
```bash
curl https://your-domain.com/.well-known/agent-card.json | jq '.name'
# Expected: "hackathon_recovery_intelligence_agent"
```

### View logs
```bash
# If running in foreground
tail -f output.log

# If running with systemd
sudo journalctl -u recovery-iq -f

# Filter A2A requests only
grep "A2A" output.log
```

### Test manually
```bash
curl -X POST https://your-domain.com/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-1",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "Is Daniel eligible for 2x/week PT?"}]
      }
    }
  }' | jq '.result.status.state'
# Expected: "completed"
```

## Support

If you encounter issues:
1. Run the checklist above
2. Check logs for specific error messages
3. Verify each component works locally
4. Contact Prompt Opinion support with:
   - Your agent card URL
   - Error messages from logs
   - Steps to reproduce

## Reference

- **Requirements**: `requirements.txt`
- **API Endpoints**: `A2A_DEPLOYMENT.md`
- **Deployment Guide**: `START_SERVICE.md`
- **Implementation Details**: `IMPLEMENTATION_SUMMARY.md`
