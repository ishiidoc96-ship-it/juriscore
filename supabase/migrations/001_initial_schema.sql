-- Juriscore Database Schema
-- Run this in Supabase SQL Editor or any PostgreSQL database

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Cases table
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    title TEXT NOT NULL,
    citation TEXT NOT NULL,
    court TEXT NOT NULL,
    year INTEGER NOT NULL,
    subject_tags JSONB,
    full_text TEXT NOT NULL,
    summary JSONB,
    ratio TEXT,
    judges JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Statutes table
CREATE TABLE IF NOT EXISTS statutes (
    id TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    title TEXT NOT NULL,
    citation TEXT NOT NULL,
    cap_number TEXT,
    full_text TEXT NOT NULL,
    amendments JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    university TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Notebooks table
CREATE TABLE IF NOT EXISTS notebooks (
    id TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Notebook entries table
CREATE TABLE IF NOT EXISTS notebook_entries (
    id TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    notebook_id TEXT NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
    case_id TEXT REFERENCES cases(id) ON DELETE SET NULL,
    statute_id TEXT REFERENCES statutes(id) ON DELETE SET NULL,
    note_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Flashcard decks table
CREATE TABLE IF NOT EXISTS flashcard_decks (
    id TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    subject TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Flashcards table
CREATE TABLE IF NOT EXISTS flashcards (
    id TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    deck_id TEXT NOT NULL REFERENCES flashcard_decks(id) ON DELETE CASCADE,
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    interval FLOAT DEFAULT 1.0,
    ease_factor FLOAT DEFAULT 2.5,
    next_review TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Study notes table
CREATE TABLE IF NOT EXISTS study_notes (
    id TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    case_id TEXT REFERENCES cases(id) ON DELETE SET NULL,
    statute_id TEXT REFERENCES statutes(id) ON DELETE SET NULL,
    note_text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_cases_court ON cases(court);
CREATE INDEX IF NOT EXISTS idx_cases_year ON cases(year);
CREATE INDEX IF NOT EXISTS idx_cases_title ON cases USING gin(to_tsvector('english', title));
CREATE INDEX IF NOT EXISTS idx_notebooks_user ON notebooks(user_id);
CREATE INDEX IF NOT EXISTS idx_notebook_entries_notebook ON notebook_entries(notebook_id);
CREATE INDEX IF NOT EXISTS idx_flashcard_decks_user ON flashcard_decks(user_id);
CREATE INDEX IF NOT EXISTS idx_flashcards_deck ON flashcards(deck_id);
CREATE INDEX IF NOT EXISTS idx_flashcards_next_review ON flashcards(next_review);
CREATE INDEX IF NOT EXISTS idx_study_notes_user ON study_notes(user_id);

-- Row Level Security (RLS) policies
ALTER TABLE notebooks ENABLE ROW LEVEL SECURITY;
ALTER TABLE notebook_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE flashcard_decks ENABLE ROW LEVEL SECURITY;
ALTER TABLE flashcards ENABLE ROW LEVEL SECURITY;
ALTER TABLE study_notes ENABLE ROW LEVEL SECURITY;

-- Policies: users can only access their own data
CREATE POLICY "Users can view own notebooks" ON notebooks FOR SELECT USING (auth.uid()::text = user_id);
CREATE POLICY "Users can create own notebooks" ON notebooks FOR INSERT WITH CHECK (auth.uid()::text = user_id);
CREATE POLICY "Users can update own notebooks" ON notebooks FOR UPDATE USING (auth.uid()::text = user_id);
CREATE POLICY "Users can delete own notebooks" ON notebooks FOR DELETE USING (auth.uid()::text = user_id);

CREATE POLICY "Users can view own entries" ON notebook_entries FOR SELECT USING (
    notebook_id IN (SELECT id FROM notebooks WHERE user_id = auth.uid()::text)
);
CREATE POLICY "Users can create entries" ON notebook_entries FOR INSERT WITH CHECK (
    notebook_id IN (SELECT id FROM notebooks WHERE user_id = auth.uid()::text)
);
CREATE POLICY "Users can delete own entries" ON notebook_entries FOR DELETE USING (
    notebook_id IN (SELECT id FROM notebooks WHERE user_id = auth.uid()::text)
);

CREATE POLICY "Users can view own decks" ON flashcard_decks FOR SELECT USING (auth.uid()::text = user_id);
CREATE POLICY "Users can create own decks" ON flashcard_decks FOR INSERT WITH CHECK (auth.uid()::text = user_id);
CREATE POLICY "Users can delete own decks" ON flashcard_decks FOR DELETE USING (auth.uid()::text = user_id);

CREATE POLICY "Users can view own cards" ON flashcards FOR SELECT USING (
    deck_id IN (SELECT id FROM flashcard_decks WHERE user_id = auth.uid()::text)
);
CREATE POLICY "Users can create cards" ON flashcards FOR INSERT WITH CHECK (
    deck_id IN (SELECT id FROM flashcard_decks WHERE user_id = auth.uid()::text)
);
CREATE POLICY "Users can update cards" ON flashcards FOR UPDATE USING (
    deck_id IN (SELECT id FROM flashcard_decks WHERE user_id = auth.uid()::text)
);

CREATE POLICY "Users can view own notes" ON study_notes FOR SELECT USING (auth.uid()::text = user_id);
CREATE POLICY "Users can create own notes" ON study_notes FOR INSERT WITH CHECK (auth.uid()::text = user_id);
CREATE POLICY "Users can update own notes" ON study_notes FOR UPDATE USING (auth.uid()::text = user_id);
CREATE POLICY "Users can delete own notes" ON study_notes FOR DELETE USING (auth.uid()::text = user_id);
