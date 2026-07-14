import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../src/constants/colors';
import { getChapter } from '../../src/services/api';

const CHAPTERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

export default function ConstitutionHubScreen({ navigation }: any) {
  const [content, setContent] = useState('');
  const [selectedChapter, setSelectedChapter] = useState<number>(1);
  const [loading, setLoading] = useState(true);

  const loadChapter = async (num: number) => {
    setLoading(true);
    try {
      const res: any = await getChapter(num);
      setContent(res.content || '');
      setSelectedChapter(num);
    } catch { /* silent */ }
    setLoading(false);
  };

  useEffect(() => { loadChapter(1); }, []);

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
      </ScrollView>
      {loading ? <ActivityIndicator style={{ marginTop: 40 }} color={Colors.primary} /> : (
        <ScrollView style={styles.articleList} contentContainerStyle={{ padding: 16, gap: 10 }}>
          <View style={styles.articleCard}>
            <Text style={styles.articleTitle}>Chapter {selectedChapter}</Text>
            <Text style={styles.articleText}>{content || 'No content available for this chapter.'}</Text>
          </View>
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
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
  articleTitle: { fontSize: 15, fontWeight: '600', color: Colors.textPrimary, marginBottom: 6 },
  articleText: { fontSize: 13, color: Colors.textSecondary, lineHeight: 20 },
});
