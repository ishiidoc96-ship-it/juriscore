# Juriscore

## Smarter legal research for Kenyan law students

**Juriscore** is a purpose-built legal research mobile application designed for Kenyan law students and early-career legal practitioners. It streamlines the process of finding, analyzing, and organizing case law, statutes, and constitutional provisions.

All case law and statutes are sourced from [kenyalaw.org](https://www.kenyalaw.org) with proper attribution.

---

## Features

- **Smart Case Search** - Search and filter cases by keyword, court level, year, judge, or legal subject area
- **Structured Case Briefs** - Automated summaries including facts, issues, holdings, ratio decidendi, and obiter dicta
- **Case Comparison** - Side-by-side comparison of two cases
- **Citation Generator** - Properly formatted eKLR citations
- **Constitution Hub** - Browse the Constitution of Kenya (2010) with chapter-level navigation
- **Flashcard System** - Study with spaced-repetition flashcards organized by legal subject
- **Research Notebook** - Save cases and take notes organized in folders
- **PDF Export** - Export case briefs, comparisons, and statutes as PDF files

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React Native (Expo) with Expo Router |
| Backend | FastAPI (Python 3.11+) |
| Database | Supabase (PostgreSQL 15) |
| Processing | Rule-based NLP |
| Auth | Supabase Auth (Email + Google OAuth) |
| Scraping | httpx + BeautifulSoup |

---

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.11+
- A [Supabase](https://supabase.com) account
- No external API keys required

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
cp .env .env.backup  # Edit .env with your credentials
uvicorn main:app --reload
```

API available at `http://localhost:8000/docs`

### 2. Frontend

```bash
cd frontend
npm install
cp .env .env.backup  # Edit .env with your Supabase credentials
npx expo start
```

### 3. Database

1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Run the SQL migration in Supabase SQL Editor:
   - Copy contents of `supabase/migrations/001_initial_schema.sql`
   - Execute in SQL Editor
3. Seed sample data:
   ```bash
   cd backend
   python -m database.seed_data
   ```

### 4. Docker (Optional)

```bash
docker-compose up
```

---

## Deployment

### Frontend (Vercel)

1. Push to GitHub
2. Connect repo to [Vercel](https://vercel.com)
3. Set root directory to `frontend`
4. Framework: Expo
5. Deploy

### Backend (Render / Railway)

1. Create a new Web Service on [Render](https://render.com) or [Railway](https://railway.app)
2. Connect your GitHub repo
3. Set root directory to `backend`
4. Build command: `pip install -r requirements.txt`
5. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Add environment variables from `.env`

---

## Environment Variables

### Backend (`backend/.env`)

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
PROCESSING_MODE=rule-based
DATABASE_URL=sqlite+aiosqlite:///./juriscore.db
KENYALAW_BASE=https://www.kenyalaw.org
CORS_ORIGINS=*
```

### Frontend (`frontend/.env`)

```env
EXPO_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
EXPO_PUBLIC_API_URL=http://localhost:8000/api
```

---

## Project Structure

```
juriscore/
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── routers/             # API route handlers
│   ├── services/            # Scraper, business logic
│   ├── models/              # Database models & schemas
│   ├── middleware/           # Auth middleware
│   ├── database/            # Seed data
│   └── requirements.txt
├── frontend/
│   ├── app/                 # Expo Router screens
│   ├── src/
│   │   ├── services/        # API client, Supabase
│   │   ├── contexts/        # Auth context
│   │   ├── constants/       # Colors, routes
│   │   └── types/           # TypeScript interfaces
│   ├── package.json
│   └── app.json
├── supabase/
│   └── migrations/          # SQL schema migrations
├── docker-compose.yml
└── vercel.json
```

---

## Legal Disclaimer

This app is a research aid, not a source of legal advice. Always verify information against official sources before citing in formal submissions.

---

## License

MIT
