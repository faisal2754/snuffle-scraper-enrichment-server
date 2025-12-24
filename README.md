# Scraper Server

FastAPI server that manages scraper jobs, queues companies for processing, and aggregates results.

## Structure

```
scraper-server/
├── api.py              # FastAPI app (models, endpoints, logic)
├── Dockerfile
├── env.example
├── pyproject.toml
├── README.md
└── requirements.txt
```

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/enqueue_scraper` | Start a scraper job |
| `GET` | `/task/{task_id}` | Get task status |
| `GET` | `/task/{task_id}/results` | Get task results |
| `POST` | `/scraper_aggregator` | Receive worker results |

## Input/Output

### POST /enqueue_scraper

```json
{
  "formData": [
    {"companyName": "Acme Corp", "companyId": 123},
    {"companyName": "Widget Inc", "companyId": 456}
  ],
  "webhookUrl": "https://your-server.com/webhook"
}
```

### Webhook Payload

```json
{
  "taskId": "uuid-string",
  "results": [
    {
      "companyId": 123,
      "companyName": "Acme Corp",
      "contacts": [
        {
          "firstName": "John",
          "lastName": "Doe",
          "email": "john.doe@acme.com",
          "phone": "+1-555-1234",
          "linkedinUrl": "https://linkedin.com/in/johndoe",
          "role": "HR Director",
          "confidenceScore": 85
        }
      ]
    }
  ]
}
```

Contacts with `confidenceScore < 50` are filtered out.

## Setup

```bash
cp env.example .env
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

## Docker

```bash
docker build -t scraper-server .
docker run -p 8000:8000 --env-file .env scraper-server
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `REDIS_URL` | Redis connection URL |
| `SERVICEBUS_CONNECTION_STRING` | Azure Service Bus connection |
| `QUEUE_SCRAPER_RESEARCH` | Queue name for scraper jobs |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | (Optional) Azure App Insights |
