import { Stack } from 'expo-router';
import { AuthProvider, useAuth } from '../src/contexts/AuthContext';
import { ActivityIndicator, View, StyleSheet } from 'react-native';
import { useEffect, useState } from 'react';
import { supabase } from '../src/services/supabase';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Colors } from '../src/constants/colors';

function RootLayoutNav() {
  const { user, loading } = useAuth();
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(() => {
      setInitialized(true);
    });
  }, []);

  if (loading || !initialized) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color={Colors.primary} />
      </View>
    );
  }

  return (
    <Stack screenOptions={{ headerShown: false }}>
      {!user ? (
        <>
          <Stack.Screen name="auth/OnboardingScreen" options={{ headerShown: false }} />
          <Stack.Screen name="auth/LoginScreen" options={{ headerShown: false }} />
          <Stack.Screen name="auth/SignUpScreen" options={{ headerShown: false }} />
        </>
      ) : (
        <>
          <Stack.Screen name="tabs/MainTabs" options={{ headerShown: false }} />
          <Stack.Screen name="case/CaseDetailScreen" options={{ headerShown: false, presentation: 'card' }} />
          <Stack.Screen name="study-session/StudySessionScreen" options={{ headerShown: false, presentation: 'fullScreenModal' }} />
        </>
      )}
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <RootLayoutNav />
    </AuthProvider>
  );
}

const styles = StyleSheet.create({
  loading: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: Colors.background },
});
