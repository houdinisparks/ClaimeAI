# Deploying ClaimeAI API to Fly.io

This guide explains how to deploy the FastAPI server to Fly.io with API key authentication in the London region.

## Prerequisites

1. Install the Fly CLI:
```bash
curl -L https://fly.io/install.sh | sh
```

2. Login to Fly:
```bash
fly auth login
```

## Configuration

The API is configured with:
- **Region**: London (lhr)
- **Resources**: 2 CPUs, 2GB RAM (suitable for LLM workflows)
- **Authentication**: API key via `X-API-Key` header
- **Auto-scaling**: Machines start/stop automatically

## Deployment Steps

### 1. Set Secrets

Set your API keys as Fly secrets (these won't be logged or visible):

```bash
cd apps/agent

# Set your API key for authentication
fly secrets set API_KEY=your-secure-api-key-here

# Required: LLM provider keys
fly secrets set OPENAI_API_KEY=your-openai-key
fly secrets set GEMINI_API_KEY=your-gemini-key
fly secrets set TAVILY_API_KEY=your-tavily-key

# Optional: Additional search provider
fly secrets set EXA_API_KEY=your-exa-key

# Optional: LangSmith tracing for debugging
fly secrets set LANGSMITH_API_KEY=your-langsmith-key
fly secrets set LANGSMITH_TRACING=true

# Optional: Database (if using persistence)
fly secrets set DATABASE_URI=your-database-uri
fly secrets set REDIS_URI=your-redis-uri
```

### 2. Create or Update the App

First deployment:
```bash
fly launch --config fly.toml --name claime-agent-api --region lhr
```

Or if the app already exists:
```bash
fly deploy
```

### 3. Verify Deployment

Check the app status:
```bash
fly status
```

View logs:
```bash
fly logs
```

Open the app:
```bash
fly open
```

## Using the API

Once deployed, your API will be available at: `https://claime-agent-api.fly.dev`

### Example Requests

All protected endpoints require the `X-API-Key` header:

```bash
# Health check (no auth required)
curl https://claime-agent-api.fly.dev/health

# Extract claims (requires API key)
curl -X POST https://claime-agent-api.fly.dev/extract-claims \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secure-api-key-here" \
  -d '{
    "text": "The Earth revolves around the Sun."
  }'

# Fact check (requires API key)
curl -X POST https://claime-agent-api.fly.dev/fact-check \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-secure-api-key-here" \
  -d '{
    "answer": "Climate change is causing global temperatures to rise."
  }'
```

### Python Client Example

```python
import requests

API_URL = "https://claime-agent-api.fly.dev"
API_KEY = "your-secure-api-key-here"

headers = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY
}

# Fact check
response = requests.post(
    f"{API_URL}/fact-check",
    headers=headers,
    json={"answer": "The Eiffel Tower was completed in 1889."}
)

print(response.json())
```

## Scaling

### Vertical Scaling (More Resources)

Increase CPU/memory for better performance:

```bash
# Scale to 4 CPUs and 4GB RAM
fly scale vm shared-cpu-4x --memory 4096
```

### Horizontal Scaling (More Machines)

Run multiple instances:

```bash
# Scale to 2 machines
fly scale count 2

# Scale by region
fly scale count 2 --region lhr
```

## Monitoring

### View Logs
```bash
fly logs
```

### Check Metrics
```bash
fly dashboard
```

### SSH into Machine
```bash
fly ssh console
```

## Configuration Options

### fly.toml Settings

The current configuration in `fly.toml`:

- **Region**: `lhr` (London)
- **CPUs**: 2 shared
- **Memory**: 2GB
- **Auto-stop/start**: Enabled (saves costs)
- **Min machines**: 1

### Adjust Resources

Edit `fly.toml` to change:

```toml
[[vm]]
cpu_kind = 'shared'  # or 'performance' for dedicated CPUs
cpus = 2             # Number of CPUs
memory = '2gb'       # RAM allocation
```

Then redeploy:
```bash
fly deploy
```

## Cost Optimization

1. **Auto-stop machines**: Already enabled - machines stop when idle
2. **Reduce min_machines**: Set to 0 if you can tolerate cold starts
3. **Use shared CPUs**: Current configuration uses cost-effective shared CPUs

## Troubleshooting

### Check if secrets are set
```bash
fly secrets list
```

### View current configuration
```bash
fly config show
```

### Restart the app
```bash
fly apps restart claime-agent-api
```

### Redeploy after changes
```bash
fly deploy --config fly.toml
```

## Security Notes

1. **API Key**: Keep your `API_KEY` secret and rotate it regularly
2. **HTTPS**: Always enforced by Fly.io
3. **Secrets**: Never commit secrets to git - use `fly secrets set`
4. **CORS**: Update CORS settings in `api/main.py` for production origins

## API Documentation

Once deployed, interactive docs are available at:
- **Swagger UI**: https://claime-agent-api.fly.dev/docs
- **ReDoc**: https://claime-agent-api.fly.dev/redoc

## Updating the App

To deploy changes:

```bash
cd apps/agent
fly deploy
```

The deployment will:
1. Build the Docker image using `Dockerfile.fastapi`
2. Deploy to the London region
3. Use the secrets you've set
4. Auto-restart the application
