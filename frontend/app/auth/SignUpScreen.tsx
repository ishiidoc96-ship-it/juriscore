import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet, SafeAreaView, KeyboardAvoidingView, Platform, ScrollView, Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Colors } from '../../src/constants/colors';
import { useAuth } from '../../src/contexts/AuthContext';
import { ROUTES } from '../../src/constants/routes';

const UNIVERSITIES = ['Kabarak University', 'Strathmore University', 'University of Nairobi', 'JKUAT', 'Moi University', 'Others'];

export default function SignUpScreen({ navigation }: any) {
  const [name, setName] = useState('');
  const [university, setUniversity] = useState('Kabarak University');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPass, setConfirmPass] = useState('');
  const [loading, setLoading] = useState(false);
  const { signUp, loginWithGoogle } = useAuth();

  const handleSignUp = async () => {
    if (!name || !email || !password) return Alert.alert('Error', 'Please fill all required fields.');
    if (password !== confirmPass) return Alert.alert('Error', 'Passwords do not match.');
    setLoading(true);
    try { await signUp(name, email, university, password); }
    catch (e: any) { Alert.alert('Error', e.message || 'Sign up failed'); }
    finally { setLoading(false); }
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={styles.scrollContent}>
          <View style={styles.header}>
            <Ionicons name="scale" size={48} color={Colors.accent} />
            <Text style={styles.brand}>Juriscore</Text>
            <Text style={styles.tagline}>Create your account</Text>
          </View>
          <View style={styles.form}>
            <TextInput style={styles.input} placeholder="Full Name" placeholderTextColor={Colors.textSecondary} value={name} onChangeText={setName} />
            <View style={styles.pickerRow}>
              {UNIVERSITIES.map((u) => (
                <TouchableOpacity
                  key={u}
                  style={[styles.uniChip, university === u && styles.uniChipActive]}
                  onPress={() => setUniversity(u)}
                >
                  <Text style={[styles.uniText, university === u && styles.uniTextActive]}>{u}</Text>
                </TouchableOpacity>
              ))}
            </View>
            <TextInput style={styles.input} placeholder="University Email" placeholderTextColor={Colors.textSecondary} autoCapitalize="none" keyboardType="email-address" value={email} onChangeText={setEmail} />
            <TextInput style={styles.input} placeholder="Password" placeholderTextColor={Colors.textSecondary} secureTextEntry value={password} onChangeText={setPassword} />
            <TextInput style={styles.input} placeholder="Confirm Password" placeholderTextColor={Colors.textSecondary} secureTextEntry value={confirmPass} onChangeText={setConfirmPass} />
            <TouchableOpacity style={styles.button} onPress={handleSignUp} disabled={loading}>
              <Text style={styles.buttonText}>{loading ? 'Creating account...' : 'Create Account'}</Text>
            </TouchableOpacity>
            <View style={styles.dividerRow}>
              <View style={styles.line} />
              <Text style={styles.dividerText}>or</Text>
              <View style={styles.line} />
            </View>
            <TouchableOpacity style={styles.googleBtn} onPress={loginWithGoogle}>
              <Ionicons name="logo-google" size={20} color={Colors.textPrimary} />
              <Text style={styles.googleText}>Continue with Google</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => navigation.navigate(ROUTES.LOGIN)}>
              <Text style={styles.link}>Already have an account? Log In</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.background },
  scrollContent: { flexGrow: 1, justifyContent: 'center', paddingHorizontal: 28, paddingVertical: 40 },
  header: { alignItems: 'center', marginBottom: 32 },
  brand: { fontSize: 28, fontWeight: '700', color: Colors.primary, marginTop: 12 },
  tagline: { fontSize: 14, color: Colors.textSecondary, marginTop: 4 },
  form: { gap: 14 },
  input: {
    backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border,
    borderRadius: 10, paddingHorizontal: 16, paddingVertical: 13, fontSize: 15, color: Colors.textPrimary,
  },
  pickerRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  uniChip: {
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20,
    backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border,
  },
  uniChipActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  uniText: { fontSize: 12, color: Colors.textSecondary },
  uniTextActive: { color: '#fff', fontWeight: '600' },
  button: {
    backgroundColor: Colors.primary, borderRadius: 10, paddingVertical: 14,
    alignItems: 'center', marginTop: 8,
  },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  dividerRow: { flexDirection: 'row', alignItems: 'center', gap: 12, marginVertical: 8 },
  line: { flex: 1, height: 1, backgroundColor: Colors.border },
  dividerText: { color: Colors.textSecondary, fontSize: 14 },
  googleBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 12, backgroundColor: Colors.surface, borderWidth: 1, borderColor: Colors.border,
    borderRadius: 10, paddingVertical: 14,
  },
  googleText: { fontSize: 16, color: Colors.textPrimary, fontWeight: '500' },
  link: { textAlign: 'center', color: Colors.primary, fontSize: 14, marginTop: 8 },
});
