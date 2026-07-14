import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../constants/colors';
import { getConstitution, getChapter, getArticle } from '../../services/api';

const CHAPTERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

export default function ConstitutionScreen({ navigation }: any) {
  const [chapters, setChapters] = useState<any[]>([]);
  const [articles, setArticles] = useState<any[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadConstitution();
  }, []);

  const loadConstitution = async () => {
    setLoading(true);
    try {
      const res: any = await getConstitution();
      setChapters(res.chapters || []);
      if (res.chapters?.length > 0) {
        loadChapter(res.chapters[0].chapter_num);
      }
    } catch { /* silent */ }
    setLoading(false);
  };

  const loadChapter = async (num: number) => {
    try {
      const res: any = await getChapter(num);
      setArticles(res.articles || []);
      setSelectedChapter(num);
    } catch { /* silent */ }
  };

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" color={Colors.primary} /></View>;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Constitution of Kenya, 2010</Text>
        <Text style={styles.subtitle}>The supreme law of the Republic</Text>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chapterScroll} contentContainerStyle={{ paddingHorizontal: 16, gap: 8 }}>
        {CHAPTERS.map((ch) => (
          <TouchableOpacity
            key={ch}
            style={[styles.chapterChip, selectedChapter === ch && styles.chapterChipActive]}
            onPress={() => loadChapter(ch)}
          >
            <Text style={[styles.chapterText, selectedChapter === ch && styles.chapterTextActive]}>Ch. {ch}</Text>
          </TouchableOpacity>
        ))}
        <TouchableOpacity
          style={[styles.chapterChip, selectedChapter === 99 && styles.chapterChipActive]}
          onPress={() => { setSelectedChapter(99); setArticles([]); }}
        >
          <Text style={[styles.chapterText, selectedChapter === 99 && styles.chapterTextActive]}>Schedules</Text>
        </TouchableOpacity>
      </ScrollView>
      <ScrollView style={styles.articleList} contentContainerStyle={{ padding: 16, gap: 10 }}>
        {(selectedChapter === 99 ? [
          { article_num: 1, article_title: 'First Schedule', full_text: 'Transitional and consequential provisions...', id: 's1' },
          { article_num: 2, article_title: 'Second Schedule', full_text: 'Amendments to the Constitution...', id: 's2' },
          { article_num: 3, article_title: 'Third Schedule', full_text: 'Coat of Arms, flag, etc.', id: 's3' },
          { article_num: 4, article_title: 'Fourth Schedule', full_text: 'Distribution of functions...', id: 's4' },
          { article_num: 6, article_title: 'Sixth Schedule', full_text: 'Amnesty provisions...', id: 's6' },
        ] : articles).map((article: any) => (
          <TouchableOpacity key={article.id || article.article_num} style={styles.articleCard}>
            <View style={styles.articleHeader}>
              <Text style={styles.articleNum}>Art. {article.article_num}</Text>
            </View>
            <Text style={styles.articleTitle}>{article.article_title}</Text>
            <Text style={styles.articleSnippet} numberOfLines={3}>{article.full_text}</Text>
            <View style={styles.articleActions}>
              <TouchableOpacity style={styles.actionBtn} onPress={() => navigation.navigate('CaseDetail', { caseId: article.id })}>
                <Ionicons name="bookmark-outline" size={16} color={Colors.primary} />
                <Text style={styles.actionText}>Save</Text>
              </TouchableOpacity>
            </View>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { padding: 16, backgroundColor: Colors.surface, borderBottomWidth: 1, borderBottomColor: Colors.border },
  title: { fontSize: 20, fontWeight: '700', color: Colors.primary },
  subtitle: { fontSize: 13, color: Colors.textSecondary, marginTop: 2 },
  chapterScroll: { maxHeight: 56, backgroundColor: '#F5F5F5' },
  chapterChip: {
    paddingHorizontal: 14, paddingVertical: 10, borderRadius: 18,
    backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border, marginVertical: 8,
  },
  chapterChipActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  chapterText: { fontSize: 13, fontWeight: '500', color: Colors.textSecondary },
  chapterTextActive: { color: '#fff', fontWeight: '600' },
  articleList: { flex: 1 },
  articleCard: { backgroundColor: Colors.surface, borderRadius: 10, padding: 14, borderWidth: 1, borderColor: Colors.border, marginBottom: 8 },
  articleHeader: { marginBottom: 4 },
  articleNum: { fontSize: 12, fontWeight: '600', color: Colors.accent },
  articleTitle: { fontSize: 15, fontWeight: '600', color: Colors.textPrimary, marginBottom: 6 },
  articleSnippet: { fontSize: 13, color: Colors.textSecondary, lineHeight: 20, marginBottom: 10 },
  articleActions: { flexDirection: 'row', gap: 16 },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  actionText: { fontSize: 12, color: Colors.primary, fontWeight: '500' },
});
