import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, FlatList, RefreshControl } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../constants/colors';
import { useAuth } from '../../contexts/AuthContext';
import { supabase } from '../../services/supabase';

const SETTINGS_ITEMS = [
  { label: 'Edit Profile', icon: 'person-outline', route: null },
  { label: 'Notifications', icon: 'notifications-outline', route: null },
  { label: 'Offline Storage', icon: 'cloud-download-outline', route: null },
  { label: 'About Juriscore', icon: 'information-circle-outline', route: null },
  { label: 'Terms of Service', icon: 'document-text-outline', route: null },
  { label: 'Privacy Policy', icon: 'lock-closed-outline', route: null },
];

export default function ProfileScreen({ navigation }: any) {
  const { user, logout } = useAuth();
  const [stats, setStats] = useState({ saved: 0, decks: 0, notes: 0 });

  useEffect(() => { loadStats(); }, []);

  const loadStats = async () => {
    try {
      const [{ count: saved }, { count: decksCount }, { count: notesCount }] = await Promise.all([
        supabase.from('notebook_entries').select('*', { count: 'estimated', head: true }),
        supabase.from('flashcard_decks').select('*', { count: 'estimated', head: true }),
        supabase.from('study_notes').select('*', { count: 'estimated', head: true }),
      ]);
      setStats({ saved: saved || 0, decks: decksCount || 0, notes: notesCount || 0 });
    } catch { /* silent */ }
  };

  const fullName = user?.user_metadata?.full_name || 'Student';
  const university = user?.user_metadata?.university || 'Not set';
  const initials = fullName.split(' ').map((n: string) => n[0]).slice(0, 2).join('').toUpperCase();

  return (
    <View style={styles.container}>
      <View style={styles.profileHeader}>
        <View style={styles.avatar}><Text style={styles.avatarText}>{initials}</Text></View>
        <Text style={styles.name}>{fullName}</Text>
        <View style={styles.uniBadge}><Text style={styles.uniText}>{university}</Text></View>
      </View>
      <View style={styles.statsRow}>
        <View style={styles.stat}><Text style={styles.statNum}>{stats.saved}</Text><Text style={styles.statLabel}>Cases Saved</Text></View>
        <View style={[styles.stat, { borderLeftWidth: 1, borderRightWidth: 1, borderColor: Colors.border }]}>
          <Text style={styles.statNum}>{stats.decks}</Text><Text style={styles.statLabel}>Flashcards</Text>
        </View>
        <View style={styles.stat}><Text style={styles.statNum}>{stats.notes}</Text><Text style={styles.statLabel}>Notes</Text></View>
      </View>
      <FlatList
        data={SETTINGS_ITEMS}
        keyExtractor={(i) => i.label}
        ItemSeparatorComponent={() => <View style={{ height: 1, backgroundColor: Colors.border, marginLeft: 56 }} />}
        contentContainerStyle={{ marginTop: 16 }}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.settingRow} onPress={() => item.route && navigation.navigate(item.route)}>
            <Ionicons name={item.icon as any} size={22} color={Colors.textSecondary} />
            <Text style={styles.settingText}>{item.label}</Text>
            <Ionicons name="chevron-forward" size={18} color={Colors.textSecondary} style={{ marginLeft: 'auto' }} />
          </TouchableOpacity>
        )}
      />
      <TouchableOpacity style={styles.logoutBtn} onPress={logout}>
        <Text style={styles.logoutText}>Log Out</Text>
      </TouchableOpacity>
      <Text style={styles.version}>Juriscore v1.0.0</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  profileHeader: { alignItems: 'center', paddingVertical: 32, backgroundColor: Colors.surface, borderBottomWidth: 1, borderBottomColor: Colors.border },
  avatar: { width: 72, height: 72, borderRadius: 36, backgroundColor: Colors.primary, justifyContent: 'center', alignItems: 'center', marginBottom: 12 },
  avatarText: { fontSize: 24, fontWeight: '700', color: '#fff' },
  name: { fontSize: 20, fontWeight: '600', color: Colors.textPrimary },
  uniBadge: { backgroundColor: '#F0E6D3', borderRadius: 14, paddingHorizontal: 14, paddingVertical: 4, marginTop: 8 },
  uniText: { fontSize: 13, color: Colors.accent, fontWeight: '500' },
  statsRow: { flexDirection: 'row', backgroundColor: Colors.surface, borderBottomWidth: 1, borderBottomColor: Colors.border },
  stat: { flex: 1, alignItems: 'center', paddingVertical: 16 },
  statNum: { fontSize: 22, fontWeight: '700', color: Colors.primary },
  statLabel: { fontSize: 12, color: Colors.textSecondary, marginTop: 2 },
  settingRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.surface, paddingVertical: 16, paddingHorizontal: 20, gap: 14 },
  settingText: { fontSize: 15, color: Colors.textPrimary },
  logoutBtn: { margin: 24, backgroundColor: '#FEE2E2', borderRadius: 10, paddingVertical: 14, alignItems: 'center' },
  logoutText: { color: Colors.error, fontWeight: '600', fontSize: 15 },
  version: { textAlign: 'center', color: Colors.textSecondary, fontSize: 12, paddingBottom: 16 },
});
