export interface Case {
  id: string;
  title: string;
  citation: string;
  court: string;
  year: number;
  subject_tags: string[];
  full_text: string;
  summary: {
    facts: string[];
    issues: string[];
    holdings: string[];
    ratio: string;
    obiter: string;
    cases_cited: string[];
  };
  judges: string[];
  cases_cited: string[];
  created_at: string;
}

export interface Statute {
  id: string;
  title: string;
  citation: string;
  cap_number: string;
  full_text: string;
  amendments: any[];
  created_at: string;
}

export interface ConstitutionArticle {
  id: string;
  chapter_num: number;
  chapter_title: string;
  article_num: number;
  article_title: string;
  full_text: string;
  plain_summary: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  university: string;
}

export interface NotebookFolder {
  id: string;
  user_id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface FlashcardDeck {
  id: string;
  user_id: string;
  title: string;
  subject: string;
  mastered_count: number;
  total_count: number;
  created_at: string;
}

export interface Flashcard {
  id: string;
  deck_id: string;
  front: string;
  back: string;
  status: string;
  interval: number;
  ease_factor: number;
  next_review: string;
  review_count: number;
}

export interface StudyNote {
  id: string;
  user_id: string;
  case_id: string;
  note_text: string;
  subject: string;
  created_at: string;
  updated_at: string;
}

export interface SearchFilters {
  court: string[];
  yearFrom: number;
  yearTo: number;
  subject: string[];
  sort: string;
}
