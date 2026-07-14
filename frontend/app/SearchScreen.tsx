import React, { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, SafeAreaView,
  FlatList, ActivityIndicator, RefreshControl, Alert, ScrollView,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../src/constants/colors';
import { searchCases } from '../src/services/api';

type CaseItem = {
  id: string;
  title: string;
  citation: string;
  court: string;
  year: number;
  subject_tags: string[];
};

const FILTERS = ['All', 'Supreme Court', 'Court of Appeal', 'High Court', 'Statutes'];
const SORT_OPTS = ['Relevance', 'Newest First', 'Oldest First'];

export default function SearchScreen({ navigation }: any) {
  const [query, setQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('All');
  const [sort, setSort] = useState('Relevance');
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [showSort, setShowSort] = useState(false);

  useEffect(() => {
    loadInitial();
  }, []);

  const loadInitial = async () => {
    setLoading(true);
    try {
      const res: any = await searchCases({ q: '', limit: 20 });
      setCases(Array.isArray(res) ? res : res?.results || []);
    } catch (e) { /* silent */ }
    setLoading(false);
  };

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const res: any = await searchCases({ q: query, limit: 20 });
      setCases(Array.isArray(res) ? res : res?.results || []);
    } catch (e) { Alert.alert('Search failed', 'Please try again.'); }
    setLoading(false);
  };

  const courtMap: Record<string, string> = {
    'Supreme Court': 'supreme',
    'Court of Appeal': 'appeal',
    'High Court': 'high court',
  };
  const filtered = activeFilter === 'All' ? cases : cases.filter(c => c.court.toLowerCase().includes(courtMap[activeFilter]?.toLowerCase() || activeFilter.toLowerCase()));

  const renderCase = ({ item }: { item: CaseItem }) => (
    <TouchableOpacity style={styles.card} onPress={() => navigation.navigate('CaseDetail', { caseId: item.id })}>
      <View style={styles.cardHeader}>
        <Text style={styles.caseName} numberOfLines={2}>{item.title}</Text>
        <TouchableOpacity>
          <Ionicons name="bookmark-outline" size={22} color={Colors.textSecondary} />
        </TouchableOpacity>
      </View>
      <Text style={styles.citation}>{item.citation}</Text>
      <View style={styles.badges}>
        <View style={styles.badge}><Text style={styles.badgeText}>{item.court}</Text></View>
        <View style={[styles.badge, { backgroundColor: Colors.accentLight }]}><Text style={styles.badgeText}>{item.year}</Text></View>
        {(item.subject_tags || []).slice(0, 2).map(t => (
          <View key={t} style={[styles.badge, { backgroundColor: '#E8EEF5' }]}><Text style={[styles.badgeText, { color: Colors.primary }]}>{t}</Text></View>
        ))}
      </View>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.searchBar}>
        <View style={styles.searchInputWrap}>
          <Ionicons name="search" size={20} color={Colors.textSecondary} />
          <TextInput style={styles.searchInput} placeholder="Search cases, statutes, topics..." placeholderTextColor={Colors.textSecondary} value={query} onChangeText={setQuery} onSubmitEditing={handleSearch} returnKeyType="search" />
          {query.length > 0 && (
            <TouchableOpacity onPress={() => { setQuery(''); loadInitial(); }}>
              <Ionicons name="close-circle" size={20} color={Colors.textSecondary} />
            </TouchableOpacity>
          )}
        </View>
        <TouchableOpacity style={styles.sortBtn} onPress={() => setShowSort(!showSort)}>
          <Ionicons name="swap-vertical" size={20} color={Colors.primary} />
        </TouchableOpacity>
      </View>
      {showSort && (
        <View style={styles.sortPanel}>
          {SORT_OPTS.map(s => (
            <TouchableOpacity key={s} style={[styles.sortChip, sort === s && styles.sortChipActive]} onPress={() => { setSort(s); setShowSort(false); }}>
              <Text style={[styles.sortChipText, sort === s && styles.sortChipTextActive]}>{s}</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterRow}>
        {FILTERS.map(f => (
          <TouchableOpacity key={f} style={[styles.filterChip, activeFilter === f && styles.filterChipActive]} onPress={() => setActiveFilter(f)}>
            <Text style={[styles.filterText, activeFilter === f && styles.filterTextActive]}>{f}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
      {loading ? (
        <View style={styles.center}><ActivityIndicator size="large" color={Colors.primary} /></View>
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(i) => i.id}
          renderItem={renderCase}
          contentContainerStyle={{ padding: 16, gap: 12 }}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={loadInitial} colors={[Colors.primary]} />}
          ListEmptyComponent={<View style={styles.center}><Text style={{ color: Colors.textSecondary }}>No cases found. Try different keywords.</Text></View>}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  searchBar: { flexDirection: 'row', paddingHorizontal: 16, paddingVertical: 12, gap: 10, alignItems: 'center' },
  searchInputWrap: { flex: 1, flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border, borderRadius: 10, paddingHorizontal: 12, gap: 8 },
  searchInput: { flex: 1, paddingVertical: 10, fontSize: 15, color: Colors.textPrimary },
  sortBtn: { padding: 10 },
  sortPanel: { flexDirection: 'row', paddingHorizontal: 16, gap: 8, marginBottom: 8 },
  sortChip: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 16, backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border },
  sortChipActive: { backgroundColor: Colors.primaryLight, borderColor: Colors.primaryLight },
  sortChipText: { fontSize: 13, color: Colors.textSecondary },
  sortChipTextActive: { color: '#fff', fontWeight: '600' },
  filterRow: { paddingHorizontal: 16, marginBottom: 8 },
  filterChip: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 20, backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border, marginRight: 8 },
  filterChipActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  filterText: { fontSize: 13, color: Colors.textSecondary },
  filterTextActive: { color: '#fff', fontWeight: '600' },
  card: { backgroundColor: Colors.surface, borderRadius: 12, padding: 16, borderWidth: 1, borderColor: Colors.border, shadowColor: '#000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.05, shadowRadius: 2, elevation: 2 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 },
  caseName: { flex: 1, fontSize: 15, fontWeight: '600', color: Colors.textPrimary, lineHeight: 20 },
  citation: { fontSize: 12, color: Colors.primary, marginBottom: 10 },
  badges: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  badge: { backgroundColor: '#F0F2F5', borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  badgeText: { fontSize: 11, color: Colors.textSecondary, fontWeight: '500' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingTop: 60 },
});
