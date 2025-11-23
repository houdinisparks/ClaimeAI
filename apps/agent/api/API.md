# ClaimeAI FastAPI Server

This FastAPI server wraps the LangGraph fact-checking workflows, providing REST API endpoints to trigger the various agents.

## 🚀 Quick Start

```bash
# Install dependencies (if not already installed)
cd apps/agent
poetry install

# Run the server
poetry run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000` and interactive docs at `http://localhost:8000/docs`.

## Available Workflows

1. **Claim Extractor** - Extracts verifiable claims from text
2. **Claim Verifier** - Verifies a single claim using iterative evidence gathering
3. **Fact Checker** - Complete fact-checking pipeline (extraction + verification + report)

## Installation

The FastAPI dependency should already be installed with Poetry:

```bash
cd apps/agent
poetry install
```

If FastAPI isn't installed, add it:

```bash
poetry add fastapi
```

## Running the Server

### Development Mode

```bash
poetry run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
poetry run uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Authentication

All endpoints (except `/` and `/health`) require API key authentication via the `X-API-Key` header.

Set the `API_KEY` environment variable:

```bash
export API_KEY=your-secure-api-key-here
```

Or in your `.env` file:
```env
API_KEY=your-secure-api-key-here
```

**Note**: If `API_KEY` is not set, the API will run without authentication (for development only).

## API Endpoints

### Health Check

```bash
GET /
GET /health
```

### Extract Claims

Extract verifiable claims from text:

```bash
POST /extract-claims
Content-Type: application/json

{
  "text": "The Earth revolves around the Sun. Water boils at 100 degrees Celsius."
}
```

### Verify Claim

Verify a single claim:

```bash
POST /verify-claim
Content-Type: application/json

{
  "claim": "The Earth revolves around the Sun",
  "disambiguated_sentence": "The Earth revolves around the Sun",
  "original_sentence": "The Earth revolves around the Sun",
  "original_index": 0
}
```

### Fact Check (Complete Pipeline)

Run the full fact-checking workflow:

```bash
POST /fact-check
Content-Type: application/json

{
  "answer": "The Earth revolves around the Sun. Water boils at 100 degrees Celsius at sea level."
}
```

## API Documentation

Once the server is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Example Usage with curl

### Extract Claims

```bash
curl -X POST "http://localhost:8000/extract-claims" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "text": "Climate change is causing sea levels to rise. The temperature has increased by 1.5 degrees Celsius since pre-industrial times."
  }'
```

### Fact Check

Runs the complete fact-checking workflow as a background job. Results are sent to the callback URL when processing completes.

```bash
curl -X POST "http://localhost:8000/fact-check" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "answer": "The Eiffel Tower is 330 meters tall and was completed in 1889.",
    "callback_url": "https://your-app.com/api/fact-check-callback"
  }'
```

## Example Usage with Python

```python
import requests

API_KEY = "your-api-key-here"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY
}

# Extract claims
response = requests.post(
    "http://localhost:8000/extract-claims",
    headers=headers,
    json={"text": "Your text here..."}
)
result = response.json()
print(result)

# Fact check
response = requests.post(
    "http://localhost:8000/fact-check",
    headers=headers,
    json={"answer": "Your text to fact-check..."}
)
result = response.json()
print(result)
```

## Environment Variables

Make sure you have the required environment variables set in your `.env` file:

```env
# API Authentication
API_KEY=your-secure-api-key-here

# Required: LLM Provider Keys
OPENAI_API_KEY=sk-proj-your-key-here
GEMINI_API_KEY=AIzaSy-your-key-here
TAVILY_API_KEY=tvly-dev-your-key-here

# Optional: Additional search provider
EXA_API_KEY=your-exa-key

# Optional: LangSmith tracing for debugging
LANGSMITH_API_KEY=lsv2_pt_your-key-here
LANGSMITH_TRACING=true

# Optional: Database for persistence
DATABASE_URI=your-database-uri
REDIS_URI=redis://localhost:6379
```

## CORS Configuration

The server allows all origins by default for development. For production, update the CORS settings in `api/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Error Handling

All endpoints return proper HTTP status codes:

- `200` - Success
- `403` - Invalid or missing API key
- `404` - Workflow not found
- `500` - Internal server error
- `503` - Service unavailable (graph not initialized)

Error responses include a `detail` field with the error message:

```json
{
  "detail": "Error message here"
}
```

## Logging

The server logs all requests and errors. Check the console output for debugging information.

## Deployment

For deploying to Fly.io with API key authentication in the London region, see [DEPLOYMENT.md](./DEPLOYMENT.md).

The deployment includes:
- API key authentication via `X-API-Key` header
- London region (lhr) hosting
- 2 CPUs and 2GB RAM for LLM workflows
- Auto-scaling capabilities
- HTTPS enforcement
