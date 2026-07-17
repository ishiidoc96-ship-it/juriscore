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
  citation: string;
  court: string;
  year: number;
  doc_type: string;
  excerpt: string;
  url: string;
  search_url?: string;
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
    // Return a fallback ChatResponse structure for when chat endpoint is not available
    throw error;
  }
}

export async function getChatHistory(sessionId: string) {
  const response = await api.get(`/chat/history/${sessionId}`);
  return response.data;
}

export async function searchCases(query: string, limit: number = 20) {
  const response = await api.get('/search/', {
    params: { q: query, limit },
  });
  return response.data;
}

export async function getAcademicWorkspace() {
  const response = await api.get('/workspaces/academic');
  return response.data;
}
