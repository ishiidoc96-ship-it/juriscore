import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Animated, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../src/constants/colors';
import { getDueCards, updateCardReview } from '../../src/services/api';

type Card = {
  id: string;
  front: string;
  back: string;
  interval: number;
  ease_factor: number;
  next_review: string;
};

export default function StudySessionScreen({ navigation, route }: any) {
  const { deckId, title } = route.params || {};
  const [cards, setCards] = useState<Card[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showBack, setShowBack] = useState(false);
  const [loading, setLoading] = useState(true);
  const flipAnim = new Animated.Value(0);

  useEffect(() => {
    loadCards();
  }, [deckId]);

  const loadCards = async () => {
    setLoading(true);
    try {
      const res: any = await getDueCards(deckId);
      setCards(Array.isArray(res) ? res : []);
    } catch { /* silent */ }
    setLoading(false);
  };

  const currentCard = cards[currentIndex];

  const handleFlip = () => {
    Animated.spring(flipAnim, {
      toValue: showBack ? 0 : 1,
      useNativeDriver: true,
    }).start();
    setShowBack(!showBack);
  };

  const handleReview = async (quality: number) => {
    if (!currentCard) return;
    const newEase = Math.max(1.3, currentCard.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)));
    const newInterval = quality >= 3 ? currentCard.interval * newEase : 1;
    const nextReview = new Date();
    nextReview.setDate(nextReview.getDate() + Math.ceil(newInterval));

    try {
      await updateCardReview(currentCard.id, quality >= 3 ? 'good' : 'hard', newEase, nextReview.toISOString());
    } catch { /* silent */ }

    if (currentIndex < cards.length - 1) {
      setCurrentIndex(currentIndex + 1);
      setShowBack(false);
      flipAnim.setValue(0);
    } else {
      Alert.alert('Session Complete!', `You reviewed ${cards.length} cards.`, [
        { text: 'Done', onPress: () => navigation.goBack() },
      ]);
    }
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <Ionicons name="flash" size={48} color={Colors.accent} />
        <Text style={styles.loadingText}>Loading cards...</Text>
      </View>
    );
  }

  if (cards.length === 0) {
    return (
      <View style={styles.center}>
        <Ionicons name="checkmark-circle" size={64} color={Colors.success} />
        <Text style={styles.doneTitle}>All caught up!</Text>
        <Text style={styles.doneSub}>No cards due for review right now.</Text>
        <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
          <Text style={styles.backBtnText}>Go Back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const progress = ((currentIndex + 1) / cards.length) * 100;

  return (
    <View style={styles.container}>
      <View style={styles.topBar}>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Ionicons name="close" size={28} color={Colors.textPrimary} />
        </TouchableOpacity>
        <Text style={styles.topTitle}>{title || 'Study Session'}</Text>
        <Text style={styles.counter}>{currentIndex + 1}/{cards.length}</Text>
      </View>

      <View style={styles.progressBar}>
        <View style={[styles.progressFill, { width: `${progress}%` }]} />
      </View>

      <TouchableOpacity style={styles.cardContainer} onPress={handleFlip} activeOpacity={0.9}>
        <View style={styles.card}>
          <Text style={styles.cardLabel}>{showBack ? 'Answer' : 'Question'}</Text>
          <Text style={styles.cardText}>
            {showBack ? currentCard.back : currentCard.front}
          </Text>
          <Text style={styles.tapHint}>Tap to {showBack ? 'see question' : 'reveal answer'}</Text>
        </View>
      </TouchableOpacity>

      {showBack && (
        <View style={styles.actions}>
          <TouchableOpacity style={[styles.actionBtn, styles.hardBtn]} onPress={() => handleReview(1)}>
            <Ionicons name="close-circle" size={24} color="#fff" />
            <Text style={styles.actionText}>Hard</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.actionBtn, styles.goodBtn]} onPress={() => handleReview(3)}>
            <Ionicons name="checkmark-circle" size={24} color="#fff" />
            <Text style={styles.actionText}>Good</Text>
          </TouchableOpacity>
          <TouchableOpacity style={[styles.actionBtn, styles.easyBtn]} onPress={() => handleReview(5)}>
            <Ionicons name="rocket" size={24} color="#fff" />
            <Text style={styles.actionText}>Easy</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 16, padding: 32 },
  topBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 16 },
  topTitle: { fontSize: 16, fontWeight: '600', color: Colors.textPrimary },
  counter: { fontSize: 14, color: Colors.textSecondary, fontWeight: '500' },
  progressBar: { height: 4, backgroundColor: Colors.border, marginHorizontal: 16, borderRadius: 2 },
  progressFill: { height: 4, backgroundColor: Colors.primary, borderRadius: 2 },
  cardContainer: { flex: 1, justifyContent: 'center', padding: 24 },
  card: {
    backgroundColor: Colors.surface, borderRadius: 20, padding: 32,
    borderWidth: 1, borderColor: Colors.border, minHeight: 280,
    shadowColor: '#000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.08, shadowRadius: 8, elevation: 4,
  },
  cardLabel: { fontSize: 12, fontWeight: '600', color: Colors.accent, textTransform: 'uppercase', marginBottom: 16 },
  cardText: { fontSize: 20, fontWeight: '500', color: Colors.textPrimary, lineHeight: 30, textAlign: 'center' },
  tapHint: { fontSize: 12, color: Colors.textSecondary, textAlign: 'center', marginTop: 24 },
  actions: { flexDirection: 'row', justifyContent: 'center', gap: 16, padding: 24, paddingBottom: 40 },
  actionBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 24, paddingVertical: 14, borderRadius: 12 },
  hardBtn: { backgroundColor: Colors.error },
  goodBtn: { backgroundColor: Colors.success },
  easyBtn: { backgroundColor: Colors.accent },
  actionText: { color: '#fff', fontWeight: '600', fontSize: 15 },
  loadingText: { fontSize: 16, color: Colors.textSecondary },
  doneTitle: { fontSize: 22, fontWeight: '700', color: Colors.textPrimary },
  doneSub: { fontSize: 14, color: Colors.textSecondary, textAlign: 'center' },
  backBtn: { backgroundColor: Colors.primary, paddingHorizontal: 32, paddingVertical: 14, borderRadius: 12, marginTop: 8 },
  backBtnText: { color: '#fff', fontWeight: '600', fontSize: 15 },
});
