import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { sendChatMessage, ChatResponse, searchCases, SearchResult, SearchFilters } from '../../lib/api';

const SOURCE_LABELS: Record<string, string> = {
  vector_search: 'Vector',
  crawled_db: 'Crawled',
  local_db: 'Local',
  brain: 'AI',
  kenyalaw: 'KenyaLaw',
};

const DOC_TYPE_LABELS: Record<string, string> = {
  case: 'Case',
  statute: 'Statute',
  constitution: 'Constitution',
  case_digest: 'Digest',
  publication: 'Publication',
  gazette: 'Gazette',
  law_report: 'Law Report',
  bench_bulletin: 'Bulletin',
  annual_report: 'Annual Report',
  commission_report: 'Commission',
  journal: 'Journal',
  law_related_article: 'Article',
};

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  results?: SearchResult[];
  sourcesUsed?: string[];
  resultCount?: number;
  timestamp: Date;
}

const FILTER_OPTIONS: { label: string; value: string }[] = [
  { label: 'All', value: '' },
  { label: 'Cases', value: 'case' },
  { label: 'Statutes', value: 'statute' },
  { label: 'Digests', value: 'case_digest' },
  { label: 'Reports', value: 'law_report' },
  { label: 'Gazettes', value: 'gazette' },
];

export default function SearchScreen() {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [activeFilter, setActiveFilter] = useState('');
  const flatListRef = useRef<FlatList>(null);

  const handleSearch = async () => {
    if (!query.trim() || loading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: query.trim(),
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setQuery('');
    setLoading(true);

    try {
      const response: ChatResponse = await sendChatMessage(query.trim(), sessionId);

      if (!sessionId) {
        setSessionId(response.session_id);
      }

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.response,
        results: response.results,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      // If chat endpoint fails, try the regular search endpoint as fallback
      try {
        const filters: SearchFilters = { jurisdiction: 'kenya' };
        if (activeFilter) filters.doc_type = activeFilter;
        const searchResponse = await searchCases(query.trim(), filters);
        if (searchResponse && searchResponse.results) {
          const sourceInfo = searchResponse.sources_used?.length
            ? ` Sources: ${searchResponse.sources_used.map(s => SOURCE_LABELS[s] || s).join(', ')}.`
            : '';
          const assistantMessage: Message = {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: `Found ${searchResponse.count || searchResponse.results.length} results for your search:${sourceInfo}`,
            results: searchResponse.results,
            sourcesUsed: searchResponse.sources_used,
            resultCount: searchResponse.count,
            timestamp: new Date(),
          };
          setMessages(prev => [...prev, assistantMessage]);
        } else {
          const errorMessage: Message = {
            id: (Date.now() + 1).toString(),
            role: 'assistant',
            content: 'Search failed. Please try again.',
            timestamp: new Date(),
          };
          setMessages(prev => [...prev, errorMessage]);
        }
      } catch (searchError) {
        const errorMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: 'Search failed. Please try again.',
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, errorMessage]);
      }
    } finally {
      setLoading(false);
    }
  };

  const openLink = (url: string, title?: string) => {
    if (url) {
      router.push({ pathname: '/document', params: { url, title: title || 'Document' } });
    }
  };

  const renderMessage = ({ item }: { item: Message }) => (
    <View style={[styles.messageBubble, item.role === 'user' ? styles.userBubble : styles.assistantBubble]}>
      {item.role === 'assistant' && (
        <View style={styles.assistantIcon}>
          <Ionicons name="flask" size={16} color="#4a9eff" />
        </View>
      )}
      <View style={item.role === 'user' ? styles.userContent : styles.assistantContent}>
        <Text style={[styles.messageText, item.role === 'user' ? styles.userText : styles.assistantText]}>
          {item.content}
        </Text>

        {item.results && item.results.length > 0 && (
          <View style={styles.resultsContainer}>
            <Text style={styles.resultsHeader}>Related Sources</Text>
            {item.results.slice(0, 8).map((result, index) => (
              <TouchableOpacity
                key={index}
                style={styles.resultCard}
                onPress={() => openLink(result.url || result.search_url || '', result.title)}
              >
                <View style={styles.resultTitleRow}>
                  <Text style={styles.resultTitle} numberOfLines={2}>
                    {result.title}
                  </Text>
                  {result.score != null && result.score > 0 && (
                    <View style={styles.scoreBadge}>
                      <Text style={styles.scoreText}>{Math.round(result.score * 100)}%</Text>
                    </View>
                  )}
                </View>
                {result.citation ? (
                  <Text style={styles.resultCitation} numberOfLines={1}>
                    {result.citation}
                  </Text>
                ) : null}
                <View style={styles.resultMeta}>
                  {result.court ? (
                    <Text style={styles.resultCourt}>{result.court}</Text>
                  ) : null}
                  {result.year ? (
                    <Text style={styles.resultYear}>{result.year}</Text>
                  ) : null}
                  {result.doc_type ? (
                    <View style={styles.docTypeBadge}>
                      <Text style={styles.docTypeText}>{DOC_TYPE_LABELS[result.doc_type] || result.doc_type}</Text>
                    </View>
                  ) : null}
                  {result.source ? (
                    <View style={styles.sourceBadge}>
                      <Text style={styles.sourceText}>{SOURCE_LABELS[result.source] || result.source}</Text>
                    </View>
                  ) : null}
                </View>
                {result.excerpt ? (
                  <Text style={styles.resultExcerpt} numberOfLines={3}>
                    {result.excerpt}
                  </Text>
                ) : null}
              </TouchableOpacity>
            ))}
          </View>
        )}
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Juriscore</Text>
        <Text style={styles.headerSubtitle}>Legal Research</Text>
      </View>

      <View style={styles.filterBar}>
        <FlatList
          data={FILTER_OPTIONS}
          horizontal
          showsHorizontalScrollIndicator={false}
          keyExtractor={item => item.value}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={[styles.filterChip, activeFilter === item.value && styles.filterChipActive]}
              onPress={() => setActiveFilter(item.value)}
            >
              <Text style={[styles.filterChipText, activeFilter === item.value && styles.filterChipTextActive]}>
                {item.label}
              </Text>
            </TouchableOpacity>
          )}
        />
      </View>

      {messages.length === 0 ? (
        <View style={styles.emptyState}>
          <Ionicons name="search" size={48} color="#2a2a4a" />
          <Text style={styles.emptyTitle}>What are you researching?</Text>
          <Text style={styles.emptySubtitle}>
            Search Kenyan case law, statutes, and legal resources
          </Text>
        </View>
      ) : (
        <FlatList
          ref={flatListRef}
          data={messages}
          renderItem={renderMessage}
          keyExtractor={item => item.id}
          contentContainerStyle={styles.messagesList}
          onContentSizeChange={() => flatListRef.current?.scrollToEnd()}
        />
      )}

      {loading && (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="small" color="#4a9eff" />
          <Text style={styles.loadingText}>Researching...</Text>
        </View>
      )}

      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.inputContainer}
      >
        <TextInput
          style={styles.input}
          value={query}
          onChangeText={setQuery}
          placeholder="Search case law, statutes, legal concepts..."
          placeholderTextColor="#555"
          onSubmitEditing={handleSearch}
          editable={!loading}
        />
        <TouchableOpacity
          style={[styles.sendButton, (!query.trim() || loading) && styles.sendButtonDisabled]}
          onPress={handleSearch}
          disabled={!query.trim() || loading}
        >
          <Ionicons name="arrow-up" size={20} color="#fff" />
        </TouchableOpacity>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0a0f',
  },
  header: {
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#1a1a2e',
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: '700',
    color: '#fff',
    letterSpacing: -0.5,
  },
  headerSubtitle: {
    fontSize: 13,
    color: '#666',
    marginTop: 2,
  },
  filterBar: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#1a1a2e',
  },
  filterChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 14,
    backgroundColor: '#14142a',
    borderWidth: 1,
    borderColor: '#2a2a4a',
    marginRight: 8,
  },
  filterChipActive: {
    backgroundColor: '#1a2a4a',
    borderColor: '#4a9eff',
  },
  filterChipText: {
    fontSize: 12,
    color: '#888',
    fontWeight: '500',
  },
  filterChipTextActive: {
    color: '#4a9eff',
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 40,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#888',
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#555',
    textAlign: 'center',
    marginTop: 8,
  },
  messagesList: {
    padding: 16,
    paddingBottom: 8,
  },
  messageBubble: {
    marginBottom: 16,
    flexDirection: 'row',
  },
  userBubble: {
    justifyContent: 'flex-end',
  },
  assistantBubble: {
    justifyContent: 'flex-start',
  },
  assistantIcon: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#1a1a2e',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
    marginTop: 2,
  },
  userContent: {
    backgroundColor: '#4a9eff',
    borderRadius: 16,
    borderBottomRightRadius: 4,
    paddingHorizontal: 14,
    paddingVertical: 10,
    maxWidth: '85%',
    marginLeft: 'auto',
  },
  assistantContent: {
    backgroundColor: '#14142a',
    borderRadius: 16,
    borderBottomLeftRadius: 4,
    paddingHorizontal: 14,
    paddingVertical: 10,
    flex: 1,
  },
  messageText: {
    fontSize: 15,
    lineHeight: 22,
  },
  userText: {
    color: '#fff',
  },
  assistantText: {
    color: '#e0e0e0',
  },
  resultsContainer: {
    marginTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#2a2a4a',
    paddingTop: 12,
  },
  resultsHeader: {
    fontSize: 12,
    fontWeight: '600',
    color: '#4a9eff',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  resultCard: {
    backgroundColor: '#0d0d1a',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#1a1a2e',
  },
  resultTitleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 4,
  },
  resultTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#e0e0e0',
    flex: 1,
    marginRight: 8,
  },
  scoreBadge: {
    backgroundColor: '#1a3a2a',
    borderRadius: 8,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  scoreText: {
    fontSize: 10,
    color: '#4ade80',
    fontWeight: '600',
  },
  resultCitation: {
    fontSize: 12,
    color: '#4a9eff',
    marginBottom: 4,
  },
  resultMeta: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 6,
  },
  resultCourt: {
    fontSize: 11,
    color: '#888',
  },
  resultYear: {
    fontSize: 11,
    color: '#888',
  },
  resultType: {
    fontSize: 11,
    color: '#6a6aaa',
    textTransform: 'capitalize',
  },
  docTypeBadge: {
    backgroundColor: '#2a1a4a',
    borderRadius: 6,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  docTypeText: {
    fontSize: 10,
    color: '#a78bfa',
    fontWeight: '500',
  },
  sourceBadge: {
    backgroundColor: '#1a2a3a',
    borderRadius: 6,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  sourceText: {
    fontSize: 10,
    color: '#60a5fa',
    fontWeight: '500',
  },
  resultExcerpt: {
    fontSize: 13,
    color: '#999',
    lineHeight: 18,
  },
  loadingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 8,
    gap: 8,
  },
  loadingText: {
    fontSize: 13,
    color: '#666',
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: '#1a1a2e',
    backgroundColor: '#0a0a0f',
  },
  input: {
    flex: 1,
    backgroundColor: '#14142a',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 15,
    color: '#fff',
    borderWidth: 1,
    borderColor: '#2a2a4a',
  },
  sendButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#4a9eff',
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: 8,
  },
  sendButtonDisabled: {
    backgroundColor: '#2a2a4a',
  },
});
