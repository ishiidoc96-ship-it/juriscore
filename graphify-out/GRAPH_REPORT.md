# Graph Report - C:\Users\pixel\AppData\Local\Temp\opencode\juriscore  (2026-07-14)

## Corpus Check
- Corpus is ~25,556 words - fits in a single context window. You may not need a graph.

## Summary
- 493 nodes · 835 edges · 33 communities (31 shown, 2 thin omitted)
- Extraction: 81% EXTRACTED · 19% INFERRED · 0% AMBIGUOUS · INFERRED: 160 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Frontend Dependencies
- API Data Models
- Database Models
- Constitution Router
- API Constitution Routes
- App Configuration
- AI & Search Services
- Cases API
- Cases Router
- Backend Schemas
- AI Service Functions
- API Database Layer
- Build Dependencies
- TypeScript Config
- Flashcard Models
- Seed Data (API)
- Seed Data (Backend)
- Notebook Models
- API Entry Point
- API Auth Middleware
- Backend Entry Point
- Backend Auth Middleware
- Frontend Vercel Config
- Root Vercel Config

## God Nodes (most connected - your core abstractions)
1. `search_kenyalaw()` - 14 edges
2. `search_kenyalaw()` - 14 edges
3. `Case` - 13 edges
4. `Case` - 13 edges
5. `expo` - 13 edges
6. `compilerOptions` - 12 edges
7. `Base` - 11 edges
8. `_call_model()` - 11 edges
9. `_parse_json()` - 11 edges
10. `Base` - 11 edges

## Surprising Connections (you probably didn't know these)
- `seed_constitution()` --calls--> `scrape_constitution()`  [INFERRED]
  api/backend/database/seed_data.py → api/backend/services/scraper.py
- `seed_cases()` --calls--> `Case`  [INFERRED]
  api/backend/database/seed_data.py → api/backend/models/database.py
- `seed_demo_user()` --calls--> `User`  [INFERRED]
  api/backend/database/seed_data.py → api/backend/models/database.py
- `seed_decks()` --calls--> `FlashcardDeck`  [INFERRED]
  api/backend/database/seed_data.py → api/backend/models/database.py
- `generate_notes()` --indirect_call--> `Case`  [INFERRED]
  api/backend/routers/study.py → api/backend/models/database.py

## Import Cycles
- None detected.

## Communities (33 total, 2 thin omitted)

### Community 0 - "Frontend Dependencies"
Cohesion: 0.05
Nodes (39): axios, expo, expo-constants, expo-linking, expo-router, expo-secure-store, expo-status-bar, @expo/vector-icons (+31 more)

### Community 1 - "API Data Models"
Cohesion: 0.10
Nodes (33): StudyNote, CaseComparisonRequest, CaseComparisonResponse, CaseSaveRequest, CaseSearchFilters, ConstitutionArticle, ConstitutionChapter, ExportCaseRequest (+25 more)

### Community 2 - "Database Models"
Cohesion: 0.11
Nodes (29): Base, Flashcard, FlashcardDeck, DeclarativeBase, StudyNote, User, FlashcardDeckResponse, FlashcardResponse (+21 more)

### Community 3 - "Constitution Router"
Cohesion: 0.09
Nodes (32): get_article(), get_chapter(), get_chapters(), get_constitution(), get_session(), AsyncSession, search_constitution(), list_courts() (+24 more)

### Community 4 - "API Constitution Routes"
Cohesion: 0.10
Nodes (30): get_article(), get_chapter(), get_chapters(), get_constitution(), get_session(), AsyncSession, search_constitution(), list_courts() (+22 more)

### Community 5 - "App Configuration"
Cohesion: 0.07
Nodes (28): backgroundColor, foregroundImage, adaptiveIcon, package, expo, android, assetBundlePatterns, extra (+20 more)

### Community 6 - "AI & Search Services"
Cohesion: 0.15
Nodes (23): AI-powered query rewriting: fix misspellings, expand terms., rewrite_query(), _call_model(), compare_cases(), extract_key_quotes(), fuzzy_match_court(), fuzzy_match_doc_type(), fuzzy_match_term() (+15 more)

### Community 7 - "Cases API"
Cohesion: 0.16
Nodes (21): Case, CaseResponse, compare_cases(), get_case(), get_case_summary(), get_citation(), get_recent_cases(), list_cases_by_court() (+13 more)

### Community 8 - "Cases Router"
Cohesion: 0.16
Nodes (21): Case, CaseResponse, compare_cases(), get_case(), get_case_summary(), get_citation(), get_recent_cases(), list_cases_by_court() (+13 more)

### Community 9 - "Backend Schemas"
Cohesion: 0.16
Nodes (23): CaseComparisonRequest, CaseComparisonResponse, CaseSaveRequest, CaseSearchFilters, ConstitutionArticle, ConstitutionChapter, ExportCaseRequest, ExportComparisonRequest (+15 more)

### Community 10 - "AI Service Functions"
Cohesion: 0.17
Nodes (21): _call_model(), compare_cases(), extract_key_quotes(), fuzzy_match_court(), fuzzy_match_doc_type(), fuzzy_match_term(), generate_case_summary(), generate_citation() (+13 more)

### Community 11 - "API Database Layer"
Cohesion: 0.18
Nodes (18): Base, Notebook, NotebookEntry, DeclarativeBase, User, NotebookFolderResponse, add_entry(), create_folder() (+10 more)

### Community 12 - "Build Dependencies"
Cohesion: 0.11
Nodes (17): @babel/core, devDependencies, @babel/core, @types/react, typescript, main, name, private (+9 more)

### Community 13 - "TypeScript Config"
Cohesion: 0.11
Nodes (17): compilerOptions, allowSyntheticDefaultImports, baseUrl, esModuleInterop, jsx, module, moduleResolution, paths (+9 more)

### Community 14 - "Flashcard Models"
Cohesion: 0.24
Nodes (16): Flashcard, FlashcardDeck, FlashcardDeckResponse, FlashcardResponse, add_card(), create_deck(), delete_deck(), due_cards() (+8 more)

### Community 15 - "Seed Data (API)"
Cohesion: 0.24
Nodes (14): main(), seed_cases(), seed_constitution(), seed_decks(), seed_demo_user(), seed_statutes(), Statute, StatuteResponse (+6 more)

### Community 16 - "Seed Data (Backend)"
Cohesion: 0.24
Nodes (14): main(), seed_cases(), seed_constitution(), seed_decks(), seed_demo_user(), seed_statutes(), Statute, StatuteResponse (+6 more)

### Community 17 - "Notebook Models"
Cohesion: 0.25
Nodes (15): Notebook, NotebookEntry, NotebookFolderResponse, add_entry(), create_folder(), delete_entry(), delete_folder(), get_recent() (+7 more)

### Community 19 - "API Auth Middleware"
Cohesion: 0.40
Nodes (3): BaseHTTPMiddleware, Request, SupabaseAuthMiddleware

### Community 21 - "Backend Auth Middleware"
Cohesion: 0.40
Nodes (3): BaseHTTPMiddleware, Request, SupabaseAuthMiddleware

### Community 22 - "Frontend Vercel Config"
Cohesion: 0.40
Nodes (4): buildCommand, framework, installCommand, outputDirectory

### Community 24 - "Root Vercel Config"
Cohesion: 0.50
Nodes (3): builds, routes, version

## Knowledge Gaps
- **72 isolated node(s):** `name`, `slug`, `version`, `orientation`, `icon` (+67 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Statute` connect `Seed Data (API)` to `API Database Layer`, `API Constitution Routes`, `Cases API`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Why does `Statute` connect `Seed Data (Backend)` to `Cases Router`, `Database Models`, `Constitution Router`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Why does `Case` connect `Cases API` to `API Data Models`, `API Database Layer`, `Seed Data (API)`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `search_kenyalaw()` (e.g. with `list_courts()` and `list_doc_types()`) actually correct?**
  _`search_kenyalaw()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `search_kenyalaw()` (e.g. with `list_courts()` and `list_doc_types()`) actually correct?**
  _`search_kenyalaw()` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `name`, `slug`, `version` to the rest of the system?**
  _72 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Frontend Dependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.05128205128205128 - nodes in this community are weakly interconnected._