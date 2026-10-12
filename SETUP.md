# Setup Guide

Step-by-step instructions to get FARE running on a new machine.

## Prerequisites

- Python 3.10+ ([download](https://www.python.org/downloads/))
- Node.js 18+ ([download](https://nodejs.org/))
- Git

## 1. Clone the repository

```bash
git clone https://github.com/<your-username>/fare-rag.git
cd fare-rag
```

## 2. Backend setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate it
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in:
- `ANTHROPIC_API_KEY` — get one from https://console.anthropic.com/
- Other values have sensible defaults; change if needed

### Start the server

```bash
python app.py
```

Verify: open http://localhost:8000/health — you should see `{"status": "ok"}`.

## 3. Frontend setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Verify: open http://localhost:5173 — the FARE UI should load.

## 4. Add sample PDFs

Place 3–5 PDF files in the `data/` folder. These are not committed to git.

## Troubleshooting

| Problem | Fix |
|---|---|
| `pip install` fails on `sentence-transformers` | Make sure you have Python 3.10+. On Windows, install Visual C++ Build Tools. |
| Frontend can't reach backend | Check that backend is running on port 8000 and CORS is configured. |
| `ANTHROPIC_API_KEY` error | Make sure `.env` exists in `backend/` and has your key. |
