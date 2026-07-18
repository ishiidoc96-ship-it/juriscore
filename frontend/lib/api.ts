import axios from 'axios';

const API_BASE = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface ChatMessage {
  message: string;
  session_id?: string;
}

export interface ChatResponse {
  response: string;
  session_id: string;
  results?: any[];
  sources?: string[];
}

export interface SearchResult {
  id: string;
  title: string;
  citation?: string;
  court?: string;
  year?: number;
  doc_type?: string;
  excerpt: string;
  url?: string;
  search_url?: string;
  score?: number;
  source?: string;
}

export interface SearchResponse {
  count: number;
  results: SearchResult[];
  jurisdiction?: string;
  source?: string;
  sources_used?: string[];
  facets?: Record<string, any>;
}

export interface SearchFilters {
  doc_type?: string;
  court?: string;
  jurisdiction?: string;
  source?: string;
  limit?: number;
}

export async function sendChatMessage(message: string, sessionId?: string): Promise<ChatResponse> {
  try {
    const response = await api.post<ChatResponse>('/chat/send', {
      message,
      session_id: sessionId,
    });
    return response.data;
  } catch (error) {
    console.warn('Chat endpoint failed, falling back to search:', error);
    throw error;
  }
}

export async function getChatHistory(sessionId: string) {
  const response = await api.get(`/chat/history/${sessionId}`);
  return response.data;
}

export async function searchCases(
  query: string,
  filters: SearchFilters = {},
): Promise<SearchResponse> {
  const params: Record<string, any> = { q: query };
  if (filters.doc_type) params.doc_type = filters.doc_type;
  if (filters.court) params.court = filters.court;
  if (filters.jurisdiction) params.jurisdiction = filters.jurisdiction;
  if (filters.source) params.source = filters.source;
  if (filters.limit) params.limit = filters.limit;

  const response = await api.get<SearchResponse>('/search', { params });
  return response.data;
}

export async function getAcademicWorkspace() {
  const response = await api.get('/workspaces/academic');
  return response.data;
}
