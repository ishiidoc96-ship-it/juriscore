import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, ScrollView, StyleSheet, TouchableOpacity, ActivityIndicator, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../src/constants/colors';
import { getCase, getCaseSummary, saveCase, addCard, exportCaseBrief } from '../../src/services/api';
import { useAuth } from '../../src/contexts/AuthContext';
import Markdown from 'react-native-markdown-display';

const TABS = ['Summary', 'Full Judgment', 'Notes', 'Related'] as const;

export default function CaseDetailScreen({ navigation, route }: any) {
  const { caseId } = route.params || {};
  const { user } = useAuth();
  const [tab, setTab] = useState(0);
  const [caseData, setCaseData] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [noteText, setNoteText] = useState('');

  useEffect(() => {
    if (caseId) loadCase();
  }, [caseId]);

  const loadCase = async () => {
    setLoading(true);
    try {
      const [c, s]: [any, any] = await Promise.all([
        getCase(caseId).catch(() => null),
        getCaseSummary(caseId).catch(() => null),
      ]);
      setCaseData(c);
      setSummary(s);
    } catch { /* silent */ }
    setLoading(false);
  };

  const handleSave = async () => {
    try {
      await saveCase(caseId, user?.id || '');
      Alert.alert('Saved', 'Case saved to your collection.');
    } catch { Alert.alert('Error', 'Could not save case.'); }
  };

  const handleCreateCard = async () => {
    try {
      await addCard(caseId, caseData?.title || 'Case', summary?.ratio || 'No summary');
      Alert.alert('Card Created', 'Flashcard added to your deck.');
    } catch { Alert.alert('Error', 'Could not create flashcard.'); }
  };

  const handleExport = async () => {
    try {
      await exportCaseBrief(caseId, 'full');
      Alert.alert('Exported', 'PDF exported successfully.');
    } catch { Alert.alert('Error', 'Could not export PDF.'); }
  };

  if (loading) return <View style={styles.center}><ActivityIndicator size="large" color={Colors.primary} /></View>;
  if (!caseData) return <View style={styles.center}><Text>Case not found.</Text></View>;

  const s = summary || caseData.summary || {};

  return (
    <View style={styles.container}>
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={24} color={Colors.primary} />
        </TouchableOpacity>
        <Text style={styles.topTitle} numberOfLines={1}>Case Detail</Text>
        <View style={{ width: 40 }} />
      </View>
      <ScrollView style={styles.scrollView}>
        <View style={styles.header}>
          <Text style={styles.caseName}>{caseData.title}</Text>
          <Text style={styles.citation}>{caseData.citation}</Text>
          <View style={styles.badges}>
            <View style={styles.badge}><Text style={styles.badgeText}>{caseData.court}</Text></View>
            <View style={[styles.badge, { backgroundColor: Colors.accentLight }]}><Text style={styles.badgeText}>{caseData.year}</Text></View>
            {(caseData.subject_tags || []).map((t: string) => (
              <View key={t} style={[styles.badge, { backgroundColor: '#E8EEF5' }]}><Text style={[styles.badgeText, { color: Colors.primary }]}>{t}</Text></View>
            ))}
          </View>
        </View>
        <View style={styles.tabBar}>
          {TABS.map((t, i) => (
            <TouchableOpacity key={t} style={[styles.tab, tab === i && styles.tabActive]} onPress={() => setTab(i)}>
              <Text style={[styles.tabText, tab === i && styles.tabTextActive]}>{t}</Text>
            </TouchableOpacity>
          ))}
        </View>
        <View style={styles.content}>
          {tab === 0 && (
            <View>
              {s.facts?.length > 0 && <View style={styles.section}><Text style={styles.sectionTitle}>Facts</Text>{(Array.isArray(s.facts) ? s.facts : [s.facts]).map((f: string, i: number) => <Text key={i} style={styles.bullet}>{typeof f === 'string' ? f : JSON.stringify(f)}</Text>)}</View>}
              {s.issues?.length > 0 && <View style={styles.section}><Text style={styles.sectionTitle}>Issues</Text>{(Array.isArray(s.issues) ? s.issues : [s.issues]).map((iss: string, i: number) => <Text key={i} style={styles.numbered}>{i + 1}. {typeof iss === 'string' ? iss : JSON.stringify(iss)}</Text>)}</View>}
              {s.holdings?.length > 0 && <View style={styles.section}><Text style={styles.sectionTitle}>Holdings</Text>{(Array.isArray(s.holdings) ? s.holdings : [s.holdings]).map((h: string, i: number) => <Text key={i} style={styles.numbered}>{i + 1}. {typeof h === 'string' ? h : JSON.stringify(h)}</Text>)}</View>}
              {s.ratio && <View style={styles.highlight}><Text style={styles.highlightLabel}>Ratio Decidendi</Text><Text style={styles.highlightText}>{s.ratio}</Text></View>}
              {s.obiter && <View style={styles.section}><Text style={styles.sectionTitle}>Obiter Dictum</Text><Text style={styles.body}>{s.obiter}</Text></View>}
              {s.cases_cited?.length > 0 && <View style={styles.section}><Text style={styles.sectionTitle}>Cases Cited</Text>{(Array.isArray(s.cases_cited) ? s.cases_cited : [s.cases_cited]).map((c: string, i: number) => <Text key={i} style={styles.body}>{typeof c === 'string' ? c : JSON.stringify(c)}</Text>)}</View>}
              {!s.facts && !s.issues && <Text style={styles.body}>No summary available yet.</Text>}
            </View>
          )}
          {tab === 1 && (
            <View>
              <Text style={styles.sectionTitle}>Full Judgment</Text>
              <Markdown style={{ body: { color: Colors.textPrimary, fontSize: 14, lineHeight: 22 } }}>{caseData.full_text || 'Full text not available.'}</Markdown>
            </View>
          )}
          {tab === 2 && (
            <View>
              <Text style={styles.sectionTitle}>My Notes</Text>
              <TextInput
                style={styles.notesInput}
                placeholder="Add your personal notes here..."
                placeholderTextColor={Colors.textSecondary}
                multiline
                numberOfLines={6}
                textAlignVertical="top"
                value={noteText}
                onChangeText={setNoteText}
              />
              <TouchableOpacity style={styles.saveBtn}><Text style={styles.saveBtnText}>Save Note</Text></TouchableOpacity>
            </View>
          )}
          {tab === 3 && (
            <View>
              {caseData.cases_cited?.length > 0 ? (
                caseData.cases_cited.map((c: string, i: number) => (
                  <View key={i} style={styles.relatedCard}><Text style={styles.relatedTitle}>{typeof c === 'string' ? c : JSON.stringify(c)}</Text><Text style={styles.relatedSub}>Cited in this case</Text></View>
                ))
              ) : <Text style={{ color: Colors.textSecondary }}>No related cases available.</Text>}
            </View>
          )}
        </View>
      </ScrollView>
      <View style={styles.bottomBar}>
        <TouchableOpacity style={styles.bottomBtn} onPress={handleSave}><Ionicons name="bookmark-outline" size={20} color={Colors.primary} /><Text style={styles.bottomLabel}>Save</Text></TouchableOpacity>
        <TouchableOpacity style={styles.bottomBtn} onPress={handleCreateCard}><Ionicons name="flash" size={20} color={Colors.accent} /><Text style={styles.bottomLabel}>Cards</Text></TouchableOpacity>
        <TouchableOpacity style={styles.bottomBtn} onPress={handleExport}><Ionicons name="download" size={20} color={Colors.primary} /><Text style={styles.bottomLabel}>Export</Text></TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  topBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16, backgroundColor: Colors.surface, borderBottomWidth: 1, borderBottomColor: Colors.border },
  backBtn: { width: 40 },
  topTitle: { fontSize: 16, fontWeight: '600', color: Colors.textPrimary },
  scrollView: { flex: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { padding: 16, backgroundColor: Colors.surface, borderBottomWidth: 1, borderBottomColor: Colors.border },
  caseName: { fontSize: 18, fontWeight: '700', color: Colors.textPrimary, marginBottom: 6 },
  citation: { fontSize: 13, color: Colors.primary, marginBottom: 10 },
  badges: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  badge: { backgroundColor: '#F0F2F5', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  badgeText: { fontSize: 11, color: Colors.textSecondary, fontWeight: '500' },
  tabBar: { flexDirection: 'row', backgroundColor: Colors.surface, borderBottomWidth: 1, borderBottomColor: Colors.border },
  tab: { flex: 1, paddingVertical: 12, alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderBottomColor: Colors.primary },
  tabText: { fontSize: 13, color: Colors.textSecondary },
  tabTextActive: { color: Colors.primary, fontWeight: '600' },
  content: { padding: 16 },
  section: { marginBottom: 18 },
  sectionTitle: { fontSize: 15, fontWeight: '600', color: Colors.textPrimary, marginBottom: 8 },
  bullet: { fontSize: 14, color: Colors.textPrimary, lineHeight: 22, marginBottom: 4 },
  numbered: { fontSize: 14, color: Colors.textPrimary, lineHeight: 22, marginBottom: 4 },
  body: { fontSize: 14, color: Colors.textPrimary, lineHeight: 22, marginBottom: 4 },
  highlight: { backgroundColor: '#FFF8E1', borderWidth: 1, borderColor: Colors.accent, borderRadius: 10, padding: 14, marginBottom: 14 },
  highlightLabel: { fontSize: 12, fontWeight: '600', color: Colors.accent, textTransform: 'uppercase', marginBottom: 4 },
  highlightText: { fontSize: 14, color: Colors.textPrimary, lineHeight: 21 },
  notesInput: {
    backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border,
    borderRadius: 10, padding: 14, fontSize: 14, color: Colors.textPrimary, minHeight: 120, marginBottom: 12,
  },
  saveBtn: { backgroundColor: Colors.primary, borderRadius: 10, paddingVertical: 12, alignItems: 'center' },
  saveBtnText: { color: '#fff', fontWeight: '600', fontSize: 15 },
  relatedCard: { backgroundColor: Colors.surface, borderRadius: 10, padding: 14, borderWidth: 1, borderColor: Colors.border, marginBottom: 8 },
  relatedTitle: { fontSize: 14, fontWeight: '600', color: Colors.textPrimary },
  relatedSub: { fontSize: 12, color: Colors.textSecondary, marginTop: 2 },
  bottomBar: { flexDirection: 'row', backgroundColor: Colors.surface, borderTopWidth: 1, borderTopColor: Colors.border, paddingVertical: 10, paddingHorizontal: 16, justifyContent: 'space-around' },
  bottomBtn: { alignItems: 'center', gap: 4 },
  bottomLabel: { fontSize: 11, color: Colors.textSecondary, fontWeight: '500' },
});
