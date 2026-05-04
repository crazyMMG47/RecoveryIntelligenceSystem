# QuickStart: Running RecoveryIQ A2A Service

## Prerequisites

```bash
cd prototype
export GEMINI_API_KEY="your-api-key"
```

## Option 1: Local Development

### Run the service
```bash
uvicorn src.hackathon_agent.app:app --reload --host 0.0.0.0 --port 8000
```

**Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Test locally
```bash
# In another terminal
python test_public_url.py http://localhost:8000 --with-case
```

### Available endpoints
- Agent card: `http://localhost:8000/.well-known/agent-card.json`
- A2A RPC: `http://localhost:8000/a2a`
- Health: `http://localhost:8000/health`

---

## Option 2: Public Testing with ngrok

### 1. Start the service
```bash
uvicorn src.hackathon_agent.app:app --host 0.0.0.0 --port 8000
```

### 2. In another terminal, create public tunnel
```bash
ngrok http 8000
```

**Output:**
```
Session Status                online                                   
Account                       user@example.com
Version                        3.x.x
Region                         us-central (...)
Forwarding                     https://1234-56-789-012.ngrok.io -> http://localhost:8000
...
```

### 3. Test with public URL
```bash
python test_public_url.py https://1234-56-789-012.ngrok.io --with-case
```

### 4. Agent card with public URL
```bash
curl https://1234-56-789-012.ngrok.io/.well-known/agent-card.json | jq '.url'
# Output: "https://1234-56-789-012.ngrok.io/a2a"
```

---

## Option 3: Production Deployment

### Example: AWS EC2 + nginx

#### 1. Install and start service on EC2
```bash
ssh ubuntu@your-instance.ec2.amazonaws.com

# Install Python and dependencies
sudo apt-get update
sudo apt-get install python3.11 python3-pip python3-venv
python3 -m venv /opt/recovery-iq/venv
source /opt/recovery-iq/venv/bin/activate

# Clone repo and install
git clone <your-repo>
cd RecoveryIntelligenceSystem/prototype
pip install -r requirements.txt

# Start service
export GEMINI_API_KEY="your-api-key"
uvicorn src.hackathon_agent.app:app --host 127.0.0.1 --port 8000
```

#### 2. Configure nginx reverse proxy
```bash
sudo tee /etc/nginx/sites-available/recovery-iq << 'EOF'
upstream recovery_iq {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name recovery-iq.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name recovery-iq.example.com;
    
    ssl_certificate /etc/letsencrypt/live/recovery-iq.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/recovery-iq.example.com/privkey.pem;
    
    location / {
        proxy_pass http://recovery_iq;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/recovery-iq /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

#### 3. Setup SSL with Let's Encrypt
```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot certonly --nginx -d recovery-iq.example.com
```

#### 4. Test production endpoint
```bash
python test_public_url.py https://recovery-iq.example.com --with-case
```

---

## Option 4: Docker Deployment

### Create Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY prototype/ .

ENV GEMINI_API_KEY=${GEMINI_API_KEY}
CMD ["uvicorn", "src.hackathon_agent.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build and run
```bash
docker build -t recovery-iq .
docker run -e GEMINI_API_KEY=$GEMINI_API_KEY -p 8000:8000 recovery-iq
```

---

## Integration with Prompt Opinion

Once your service is public and running:

### 1. Register agent URL
Provide Prompt Opinion with your agent card URL:
```
https://recovery-iq.example.com/.well-known/agent-card.json
```

### 2. Prompt Opinion discovers agent
Prompt Opinion fetches agent card and learns:
- Agent capabilities (PT eligibility review)
- A2A endpoint URL
- Supported input/output modes

### 3. User requests analysis in Prompt Opinion
Prompt Opinion sends JSON-RPC to `/a2a`:
```json
{
  "jsonrpc": "2.0",
  "id": "request-id",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"kind": "text", "text": "Is Daniel eligible for PT?"}]
    },
    "metadata": {"case": {...}}
  }
}
```

### 4. RecoveryIQ processes and responds
- Runs Clinical → Insurance → Orchestrator → PromptOpinionAgent
- Returns structured + plain-language artifacts
- Prompt Opinion presents to care coordinator

---

## Monitoring & Logs

### View service logs
```bash
# If running in foreground
tail -f output.log

# If running with systemd
sudo journalctl -u recovery-iq -f
```

### Monitor A2A requests
```bash
# Look for A2A log entries
grep "A2A request" output.log
grep "A2A response" output.log
```

### Check service health
```bash
curl https://recovery-iq.example.com/health
# Output: {"status":"ok"}
```

---

## Troubleshooting

### Port already in use
```bash
# Find what's using port 8000
lsof -i :8000
# Kill the process
kill -9 <PID>
```

### GEMINI_API_KEY not set
```bash
# Check if set
echo $GEMINI_API_KEY
# Set it
export GEMINI_API_KEY="your-key"
```

### SSL certificate issues (nginx)
```bash
# Test nginx config
sudo nginx -t
# View certificate details
sudo certbot certificates
```

### A2A invocations timing out
- Increase FastAPI timeout
- Check if LLM (Gemini/Ollama) is responsive
- Verify network connectivity to LLM API

---

## Environment Variables

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `GEMINI_API_KEY` | Yes | - | Google Gemini API key |
| `GEMINI_MODEL` | No | `gemini-2.5-flash-lite` | Model to use |
| `EMBEDDINGS_CACHE_DIR` | No | `./cache` | Where to cache embeddings |

---

## Performance Notes

- **First request**: ~30-60 seconds (LLM processing)
- **Subsequent requests**: ~30-60 seconds (each request is independent)
- **Embedding loading**: ~5-10 seconds (first load, then cached)
- **Concurrent requests**: Limited by LLM API rate limits

---

## Next Steps

1. Start the service locally or publicly
2. Test with `test_public_url.py`
3. Register with Prompt Opinion platform
4. Monitor logs and collect feedback
5. Iterate on clinical summary generation
