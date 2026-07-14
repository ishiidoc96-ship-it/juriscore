import React, { useState, useRef } from 'react';
import {
  View, Text, ScrollView, StyleSheet, Dimensions, TouchableOpacity,
  SafeAreaView, StatusBar,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../src/constants/colors';
import { ROUTES } from '../src/constants/routes';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

export default function OnboardingScreen({ navigation }: any) {
  const [current, setCurrent] = useState(0);
  const scrollRef = useRef<ScrollView>(null);

  const slides = [
    {
      icon: 'search',
      title: 'Find cases instantly',
      desc: 'Search thousands of Kenyan cases and statutes by keyword, subject, or court.',
    },
    {
      icon: 'document-text',
      title: 'Study smarter, not harder',
      desc: 'Get structured case briefs and study notes in one click. Built for law students.',
    },
    {
      icon: 'folder',
      title: 'Research, organized',
      desc: 'Save cases, build your notebook, and track your syllabus\u2014all in one place.',
      cta: true,
    },
  ];

  const handleNext = () => {
    if (current < slides.length - 1) {
      const next = current + 1;
      setCurrent(next);
      scrollRef.current?.scrollTo({ x: next * SCREEN_WIDTH, animated: true });
    } else {
      navigation.replace(ROUTES.SIGNUP);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="dark-content" backgroundColor={Colors.background} />
      <ScrollView
        ref={scrollRef}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onMomentumScrollEnd={(e) => {
          const idx = Math.round(e.nativeEvent.contentOffset.x / SCREEN_WIDTH);
          setCurrent(idx);
        }}
        scrollEnabled={false}
      >
        {slides.map((slide, i) => (
          <View key={i} style={[styles.slide, { width: SCREEN_WIDTH }]}>
            <View style={styles.iconCircle}>
              <Ionicons name={slide.icon as any} size={64} color={Colors.accent} />
            </View>
            <Text style={styles.title}>{slide.title}</Text>
            <Text style={styles.desc}>{slide.desc}</Text>
            {slide.cta && (
              <TouchableOpacity style={styles.button} onPress={handleNext}>
                <Text style={styles.buttonText}>Get Started</Text>
              </TouchableOpacity>
            )}
          </View>
        ))}
      </ScrollView>
      <View style={styles.dots}>
        {slides.map((_, i) => (
          <View
            key={i}
            style={[styles.dot, { backgroundColor: i === current ? Colors.primary : Colors.border }]}
          />
        ))}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  slide: {
    flex: 1, justifyContent: 'center', alignItems: 'center',
    paddingHorizontal: 40, paddingVertical: 60,
  },
  iconCircle: {
    width: 120, height: 120, borderRadius: 60,
    backgroundColor: '#F0E6D3', justifyContent: 'center', alignItems: 'center',
    marginBottom: 40,
  },
  title: {
    fontSize: 24, fontWeight: '700', color: Colors.textPrimary,
    textAlign: 'center', marginBottom: 16,
  },
  desc: {
    fontSize: 16, color: Colors.textSecondary, textAlign: 'center',
    lineHeight: 24, marginBottom: 32,
  },
  button: {
    backgroundColor: Colors.primary, paddingHorizontal: 48, paddingVertical: 14,
    borderRadius: 12, marginTop: 16,
  },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  dots: {
    flexDirection: 'row', justifyContent: 'center',
    paddingVertical: 24, gap: 10,
  },
  dot: { width: 10, height: 10, borderRadius: 5 },
});
