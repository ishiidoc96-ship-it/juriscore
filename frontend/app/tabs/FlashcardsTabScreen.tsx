import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, FlatList, StyleSheet, ActivityIndicator, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../src/constants/colors';
import { useAuth } from '../../src/contexts/AuthContext';
import { getDecks, deleteDeck } from '../../src/services/api';

type Deck = { id: string; title: string; subject: string; created_at: string };

export default function FlashcardsScreen({ navigation }: any) {
  const { user } = useAuth();
  const [decks, setDecks] = useState<Deck[]>([]);
  const [loading, setLoading] = useState(true);

  const loadDecks = async () => {
    if (!user?.id) return;
    setLoading(true);
    try {
      const res: any = await getDecks(user.id);
      setDecks(Array.isArray(res) ? res : res?.decks || []);
    } catch { /* silent */ }
    setLoading(false);
  };

  useEffect(() => { loadDecks(); }, [user]);

  return (
    <View style={styles.container}>
      <View style={styles.topBar}>
        <Text style={styles.title}>Flashcards</Text>
      </View>
      {loading ? <ActivityIndicator style={{ marginTop: 40 }} color={Colors.primary} /> : decks.length === 0 ? (
        <View style={styles.empty}><Ionicons name="flash" size={48} color={Colors.textSecondary} /><Text style={styles.emptyText}>No decks yet</Text><Text style={styles.emptySub}>Create one to start studying</Text></View>
      ) : (
        <FlatList
          data={decks}
          keyExtractor={(i) => i.id}
          contentContainerStyle={{ padding: 16, gap: 10 }}
          renderItem={({ item }) => (
            <TouchableOpacity style={styles.deckCard} onPress={() => navigation.navigate('DeckDetail', { deckId: item.id, title: item.title })}>
              <View style={styles.deckIcon}>
                <Ionicons name="flash" size={24} color={Colors.accent} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.deckTitle}>{item.title}</Text>
                <Text style={styles.deckSub}>{item.subject || 'General'}</Text>
                <Text style={styles.deckDate}>Created {new Date(item.created_at).toLocaleDateString()}</Text>
              </View>
              <TouchableOpacity onPress={() => {
                Alert.alert('Delete Deck?', 'This cannot be undone.', [
                  { text: 'Cancel', style: 'cancel' },
                  { text: 'Delete', style: 'destructive', onPress: async () => { await deleteDeck(item.id); loadDecks(); } },
                ]);
              }}>
                <Ionicons name="trash-outline" size={20} color={Colors.error} />
              </TouchableOpacity>
            </TouchableOpacity>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, backgroundColor: Colors.surface, borderBottomWidth: 1, borderBottomColor: Colors.border },
  title: { fontSize: 20, fontWeight: '700', color: Colors.primary },
  empty: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 8 },
  emptyText: { fontSize: 16, color: Colors.textSecondary, fontWeight: '500' },
  emptySub: { fontSize: 13, color: Colors.textSecondary },
  deckCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.surface, borderRadius: 12, padding: 16, borderWidth: 1, borderColor: Colors.border, gap: 14, shadowColor: '#000', shadowOpacity: 0.04, shadowRadius: 2, elevation: 2 },
  deckIcon: { width: 44, height: 44, borderRadius: 12, backgroundColor: '#F0E6D3', justifyContent: 'center', alignItems: 'center' },
  deckTitle: { fontSize: 15, fontWeight: '600', color: Colors.textPrimary },
  deckSub: { fontSize: 12, color: Colors.textSecondary, marginTop: 2 },
  deckDate: { fontSize: 11, color: Colors.textSecondary, marginTop: 4 },
});
