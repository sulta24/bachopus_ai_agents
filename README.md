# AI Orchestrator

Multi-agent AI system for intelligent data analysis and external API orchestration with three-phase reasoning (Planning → Execution → Feedback).

## Quick Start

```bash
# Install
git clone <repository-url>
cd AI_Orchestrator
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env: OPENAI_API_KEY=your-key

# Run
uvicorn main:app --reload --port 8000
```

## API

**POST /orchestrate**
```bash
curl -X POST "http://localhost:8000/orchestrate" \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "service_id": "test-service",
    "session_id": "test-session",
    "user_message": "Analyze system performance"
  }'
```

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `DATADOG_API_KEY` | No | Datadog API key |
| `DATADOG_APP_KEY` | No | Datadog app key |

## Structure

```
├── agents/          # Specialized agents
├── core/           # Core system logic
├── main.py         # FastAPI application
└── requirements.txt # Dependencies
```

## Documentation

Interactive API docs: `http://localhost:8000/docs`