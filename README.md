# Credit API

FastAPI adapter for the Intelligent Credit Scoring System.

## Endpoints

- `GET /health`
- `GET /meta`
- `POST /score`

## Local run

```bash
pip install -r requirements.txt
python -m uvicorn app:app --reload --host 127.0.0.1 --port 8001
```

## Vercel deployment

- Set the Vercel project Root Directory to `final_individual_project/services/credit_api`
- `app.py` is the Vercel entrypoint
- `vercel.json` contains the function configuration

## Environment

- `ALLOW_ORIGINS`: comma-separated site origins allowed by CORS, or `*`
