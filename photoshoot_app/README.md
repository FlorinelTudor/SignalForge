# Photoshoot Sub-App

Generate professional-looking portraits from a selfie using xAI's Image API.

## Setup

1. Copy `.env.example` to `.env` and set `XAI_API_KEY`.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

```bash
uvicorn photoshoot_app.main:app --host 127.0.0.1 --port 8001 --reload
```

Open `http://127.0.0.1:8001`.
