import React, { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView, StyleSheet,
  FlatList, ActivityIndicator, RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../src/constants/colors';
import { useAuth } from '../../src/contexts/AuthContext';
import { searchCases, getRecentCases } from '../../src/services/api';

type CaseItem = { id: string; title: string; citation: string; court: string; year: number };

export default function HomeScreen({ navigation }: any) {
  const { user } = useAuth();
  const [recent, setRecent] = useState<CaseItem[]>([]);
  const [recs, setRecs] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [recRes, allRes]: [any, any] = await Promise.all([
        getRecentCases(5).catch(() => []),
        searchCases({ q: 'kenya law', limit: 8 }).catch(() => []),
      ]);
      setRecent(Array.isArray(recRes) ? recRes.slice(0, 5) : []);
      setRecs(Array.isArray(allRes) ? allRes.slice(0, 5) : []);
    } catch { /* silent */ }
    setLoading(false);
  };

  const firstName = user?.user_metadata?.full_name?.split(' ')[0] || user?.email?.split('@')[0] || 'Student';
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  const navigateTo = (route: string) => navigation.navigate(route);

  const CaseLink = ({ item }: { item: CaseItem }) => (
    <TouchableOpacity style={styles.recentCard} onPress={() => navigation.navigate('CaseDetail', { caseId: item.id })}>
      <Text style={styles.recentTitle} numberOfLines={1}>{item.title}</Text>
      <Text style={styles.recentCitation}>{item.citation}</Text>
      <View style={styles.progressBar}><View style={styles.progressFill} /></View>
    </TouchableOpacity>
  );

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={{ padding: 16, gap: 20 }} refreshControl={<RefreshControl refreshing={loading} onRefresh={loadData} colors={[Colors.primary]} />}>
        <View>
          <Text style={styles.greeting}>{greeting}, {firstName}</Text>
          <TextInput
            style={styles.searchBar}
            placeholder="Search cases, statutes, topics..."
            placeholderTextColor={Colors.textSecondary}
            onFocus={() => navigateTo('search')}
          />
        </View>

        <View>
          <Text style={styles.sectionLabel}>Quick Actions</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ gap: 12 }}>
            {[
              { label: 'Recent Cases', icon: 'time', route: 'search' },
              { label: 'My Notebook', icon: 'folder', route: 'notebook' },
              { label: 'Flashcards', icon: 'flash', route: 'flashcards' },
              { label: 'Constitution', icon: 'document', route: 'constitution-hub' },
            ].map((action) => (
              <TouchableOpacity key={action.label} style={styles.actionBtn} onPress={() => navigateTo(action.route)}>
                <Ionicons name={action.icon as any} size={24} color={Colors.accent} />
                <Text style={styles.actionLabel}>{action.label}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>

        <View>
          <Text style={styles.sectionLabel}>Continue Studying</Text>
          {loading ? <ActivityIndicator color={Colors.primary} /> : (
            <FlatList
              data={recent}
              horizontal
              keyExtractor={(i) => i.id}
              renderItem={({ item }: { item: CaseItem }) => <CaseLink item={item} />}
              showsHorizontalScrollIndicator={false}
              ItemSeparatorComponent={() => <View style={{ width: 10 }} />}
              ListEmptyComponent={<Text style={{ color: Colors.textSecondary }}>Start exploring to see your history</Text>}
            />
          )}
        </View>

        <View>
          <Text style={styles.sectionLabel}>Recommended for You</Text>
          {loading ? <ActivityIndicator color={Colors.primary} /> : (
            <View style={{ gap: 10 }}>
              {recs.map((item: CaseItem) => (
                <TouchableOpacity key={item.id} style={styles.recCard} onPress={() => navigation.navigate('CaseDetail', { caseId: item.id })}>
                  <Text style={styles.recTitle} numberOfLines={1}>{item.title}</Text>
                  <Text style={styles.recSub}>{item.citation}</Text>
                  <View style={styles.badgeRow}>
                    <View style={[styles.badge, { backgroundColor: '#E8EEF5' }]}>
                      <Text style={[styles.badgeText, { color: Colors.primary }]}>{item.court}</Text>
                    </View>
                    <View style={[styles.badge, { backgroundColor: '#F0E6D3' }]}>
                      <Text style={[styles.badgeText, { color: Colors.accent }]}>{item.year}</Text>
                    </View>
                  </View>
                </TouchableOpacity>
              ))}
            </View>
          )}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  greeting: { fontSize: 22, fontWeight: '700', color: Colors.textPrimary, marginBottom: 12 },
  searchBar: {
    backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border,
    borderRadius: 12, paddingHorizontal: 16, paddingVertical: 12, fontSize: 15, color: Colors.textPrimary,
  },
  sectionLabel: { fontSize: 16, fontWeight: '600', color: Colors.textPrimary, marginBottom: 10 },
  actionBtn: { alignItems: 'center', backgroundColor: Colors.surface, borderRadius: 12, padding: 16, borderWidth: 1, borderColor: Colors.border, minWidth: 90 },
  actionLabel: { fontSize: 12, color: Colors.textSecondary, marginTop: 8, fontWeight: '500' },
  recentCard: { backgroundColor: Colors.surface, borderRadius: 10, padding: 14, borderWidth: 1, borderColor: Colors.border, minWidth: 200, maxWidth: 260 },
  recentTitle: { fontSize: 14, fontWeight: '600', color: Colors.textPrimary, marginBottom: 4 },
  recentCitation: { fontSize: 11, color: Colors.primary, marginBottom: 8 },
  progressBar: { height: 4, backgroundColor: Colors.border, borderRadius: 2 },
  progressFill: { width: '60%', height: 4, backgroundColor: Colors.primary, borderRadius: 2 },
  recCard: { backgroundColor: Colors.surface, borderRadius: 10, padding: 14, borderWidth: 1, borderColor: Colors.border },
  recTitle: { fontSize: 14, fontWeight: '600', color: Colors.textPrimary, marginBottom: 4 },
  recSub: { fontSize: 12, color: Colors.primary, marginBottom: 8 },
  badgeRow: { flexDirection: 'row', gap: 6 },
  badge: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  badgeText: { fontSize: 11, fontWeight: '500' },
});
