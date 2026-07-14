import React, { useState, useEffect } from 'react';
import { View, Text, FlatList, TouchableOpacity, StyleSheet, Alert, ActivityIndicator } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../src/constants/colors';
import { useAuth } from '../../src/contexts/AuthContext';
import { getFolders, createFolder, deleteFolder } from '../../src/services/api';

type Folder = { id: string; name: string; created_at: string };

export default function NotebookScreen({ navigation }: any) {
  const { user } = useAuth();
  const [folders, setFolders] = useState<Folder[]>([]);
  const [loading, setLoading] = useState(true);

  const loadFolders = async () => {
    if (!user?.id) return;
    setLoading(true);
    try {
      const res: any = await getFolders(user.id);
      setFolders(Array.isArray(res) ? res : res?.folders || []);
    } catch { /* silent */ }
    setLoading(false);
  };

  useEffect(() => { loadFolders(); }, [user]);

  const handleCreate = async () => {
    const name = 'New Folder';
    try {
      await createFolder(user.id, name);
      loadFolders();
    } catch { Alert.alert('Error', 'Could not create folder.'); }
  };

  const handleDelete = (id: string) => {
    Alert.alert('Delete Folder?', 'This will also remove all entries.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => { await deleteFolder(id); loadFolders(); } },
    ]);
  };

  return (
    <View style={styles.container}>
      <View style={styles.topBar}>
        <Text style={styles.title}>My Notebook</Text>
        <TouchableOpacity style={styles.addBtn} onPress={handleCreate}>
          <Ionicons name="add" size={24} color="#fff" />
        </TouchableOpacity>
      </View>
      {loading ? <ActivityIndicator style={{ marginTop: 40 }} color={Colors.primary} /> : folders.length === 0 ? (
        <View style={styles.empty}><Ionicons name="folder-open" size={48} color={Colors.textSecondary} /><Text style={styles.emptyText}>No folders yet</Text><Text style={styles.emptySub}>Tap + to create your first study folder</Text></View>
      ) : (
        <FlatList
          data={folders}
          keyExtractor={(i) => i.id}
          contentContainerStyle={{ padding: 16, gap: 10 }}
          renderItem={({ item }) => (
            <TouchableOpacity style={styles.folderCard} onPress={() => navigation.navigate('FolderDetail', { folderId: item.id, folderName: item.name })}>
              <Ionicons name="folder" size={32} color={Colors.accent} />
              <View style={{ flex: 1, marginLeft: 12 }}>
                <Text style={styles.folderName}>{item.name}</Text>
                <Text style={styles.folderDate}>{new Date(item.created_at).toLocaleDateString()}</Text>
              </View>
              <TouchableOpacity onPress={() => handleDelete(item.id)}>
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
  addBtn: { backgroundColor: Colors.primary, borderRadius: 10, padding: 8 },
  empty: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 8 },
  emptyText: { fontSize: 16, color: Colors.textSecondary, fontWeight: '500' },
  emptySub: { fontSize: 13, color: Colors.textSecondary },
  folderCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: Colors.surface, borderRadius: 12, padding: 16, borderWidth: 1, borderColor: Colors.border, shadowColor: '#000', shadowOpacity: 0.04, shadowRadius: 2, elevation: 2 },
  folderName: { fontSize: 15, fontWeight: '600', color: Colors.textPrimary },
  folderDate: { fontSize: 12, color: Colors.textSecondary, marginTop: 2 },
});
