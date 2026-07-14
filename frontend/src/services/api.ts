import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000/api';

export const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
});

api.interceptors.request.use(
  async (config: any) => {
    const token = await AsyncStorage.getItem('auth_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  },
  (error: any) => Promise.reject(error),
);

api.interceptors.response.use(
  (response: any) => response,
  async (error: any) => {
    if (error.response?.status === 401) {
      await AsyncStorage.removeItem('auth_token');
    }
    return Promise.reject(error);
  },
);

export const searchCases = async (params: any) =>
  api.get('/cases/search', { params }).then((r: any) => r.data);

export const getRecentCases = async (limit: number = 10) =>
  api.get('/cases/recent', { params: { limit } }).then((r: any) => r.data);

export const getCase = async (id: string) =>
  api.get(`/cases/${id}`).then((r: any) => r.data);

export const getCaseSummary = async (id: string) =>
  api.get(`/cases/${id}/summary`).then((r: any) => r.data);

export const saveCase = async (id: string, user_id: string, folder_id?: string) =>
  api.post(`/cases/${id}/save`, { user_id, folder_id }).then((r: any) => r.data);

export const compareCases = async (case_a_id: string, case_b_id: string) =>
  api.post('/cases/compare', { case_a_id, case_b_id }).then((r: any) => r.data);

export const getStatutes = async () =>
  api.get('/statutes').then((r: any) => r.data);

export const getStatute = async (id: string) =>
  api.get(`/statutes/${id}`).then((r: any) => r.data);

export const searchStatutes = async (params: any) =>
  api.get('/statutes/search', { params }).then((r: any) => r.data);

export const getConstitution = async () =>
  api.get('/constitution').then((r: any) => r.data);

export const getChapter = async (num: number) =>
  api.get(`/constitution/chapters/${num}`).then((r: any) => r.data);

export const getArticle = async (num: number) =>
  api.get(`/constitution/articles/${num}`).then((r: any) => r.data);

export const searchConstitution = async (q: string) =>
  api.get('/constitution/search', { params: { q } }).then((r: any) => r.data);

export const getFolders = async (user_id: string) =>
  api.get('/notebook/folders', { params: { user_id } }).then((r: any) => r.data);

export const createFolder = async (user_id: string, name: string) =>
  api.post('/notebook/folders', { name }, { params: { user_id } }).then((r: any) => r.data);

export const renameFolder = async (id: string, name: string) =>
  api.put(`/notebook/folders/${id}`, { name }).then((r: any) => r.data);

export const deleteFolder = async (id: string) =>
  api.delete(`/notebook/folders/${id}`).then((r: any) => r.data);

export const addEntryToFolder = async (folder_id: string, case_id?: string, statute_id?: string, note_text?: string) =>
  api.post(`/notebook/folders/${folder_id}/entries`, { case_id, statute_id, note_text }).then((r: any) => r.data);

export const deleteEntry = async (id: string) =>
  api.delete(`/notebook/entries/${id}`).then((r: any) => r.data);

export const getDecks = async (user_id: string) =>
  api.get('/flashcards/decks', { params: { user_id } }).then((r: any) => r.data);

export const createDeck = async (user_id: string, title: string, subject: string) =>
  api.post('/flashcards/decks', { title, subject }, { params: { user_id } }).then((r: any) => r.data);

export const getDeck = async (id: string) =>
  api.get(`/flashcards/decks/${id}`).then((r: any) => r.data);

export const addCard = async (deck_id: string, front: string, back: string) =>
  api.post(`/flashcards/decks/${deck_id}/cards`, { front, back }).then((r: any) => r.data);

export const updateCardReview = async (card_id: string, status: string, ease_factor?: number, next_review?: string) =>
  api.put(`/flashcards/cards/${card_id}`, {
    interval: status === 'good' ? 1 : 0.5,
    ease_factor: ease_factor || 2.5,
    next_review: next_review || new Date().toISOString(),
  }).then((r: any) => r.data);

export const getDueCards = async (deck_id: string) =>
  api.get(`/flashcards/decks/${deck_id}/due`).then((r: any) => r.data);

export const deleteDeck = async (id: string) =>
  api.delete(`/flashcards/decks/${id}`).then((r: any) => r.data);

export const getStudyNotes = async (user_id: string) =>
  api.get('/study/notes', { params: { user_id } }).then((r: any) => r.data);

export const createStudyNote = async (user_id: string, note: any) =>
  api.post('/study/notes', note, { params: { user_id } }).then((r: any) => r.data);

export const updateStudyNote = async (id: string, note_text: string) =>
  api.put(`/study/notes/${id}`, { note_text }).then((r: any) => r.data);

export const deleteStudyNote = async (id: string) =>
  api.delete(`/study/notes/${id}`).then((r: any) => r.data);

export const generateNotes = async (case_id: string, user_id: string) =>
  api.post('/study/notes/generate', { case_id }, { params: { user_id } }).then((r: any) => r.data);

export const exportCaseBrief = async (case_id: string, format: string = 'full') =>
  api.post('/export/case-brief', { case_id, format }, { responseType: 'blob' }).then((r: any) => r.data);

export const exportComparison = async (case_a_id: string, case_b_id: string) =>
  api.post('/export/comparison', { case_a_id, case_b_id }, { responseType: 'blob' }).then((r: any) => r.data);

export const exportStatute = async (statute_id: string) =>
  api.post('/export/statute', { statute_id }, { responseType: 'blob' }).then((r: any) => r.data);

export { api as default };
