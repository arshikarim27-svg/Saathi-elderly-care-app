import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  Alert,
  Platform,
  ActivityIndicator,
  Linking,
  Modal,
  TextInput,
  Dimensions,
  KeyboardAvoidingView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Speech from 'expo-speech';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Notifications from 'expo-notifications';

const API_URL = process.env.EXPO_PUBLIC_BACKEND_URL;
const { width, height } = Dimensions.get('window');

// Configure notifications
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

interface Reminder {
  id: string;
  type: string;
  title: string;
  time: string;
  enabled: boolean;
  snoozed_until?: string;
}

interface SuggestionCard {
  text: string;
  icon: string;
}

interface ChatHistory {
  message: string;
  response: string;
  time: string;
}

export default function Index() {
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [currentMessage, setCurrentMessage] = useState('');
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [showReminderModal, setShowReminderModal] = useState(false);
  const [newReminder, setNewReminder] = useState({
    type: 'medicine',
    title: '',
    time: '',
  });
  const [loading, setLoading] = useState(false);
  const [userName, setUserName] = useState('');
  const [showNameModal, setShowNameModal] = useState(false);
  const [tempName, setTempName] = useState('');
  const [recentChats, setRecentChats] = useState<ChatHistory[]>([]);
  const [greeting, setGreeting] = useState('');

  const suggestions: SuggestionCard[] = [
    { text: 'Tell me a story from your childhood', icon: 'book' },
    { text: 'What should I cook today?', icon: 'restaurant' },
    { text: 'Tell me a joke to brighten my day', icon: 'happy' },
    { text: 'Share a health tip with me', icon: 'heart' },
  ];

  useEffect(() => {
    initializeApp();
  }, []);

  useEffect(() => {
    if (userName) {
      updateGreeting();
    }
  }, [userName]);

  const initializeApp = async () => {
    await requestPermissions();
    await loadUserName();
    await loadReminders();
    await loadChatHistory();
    await setupNotifications();
  };

  const updateGreeting = () => {
    const hour = new Date().getHours();
    let timeGreeting = '';
    
    if (hour < 12) {
      timeGreeting = 'Good morning';
    } else if (hour < 17) {
      timeGreeting = 'Good afternoon';
    } else {
      timeGreeting = 'Good evening';
    }
    
    setGreeting(`${timeGreeting}, ${userName}!`);
  };

  const loadUserName = async () => {
    try {
      const stored = await AsyncStorage.getItem('userName');
      if (stored) {
        setUserName(stored);
      } else {
        setShowNameModal(true);
      }
    } catch (error) {
      console.error('Error loading user name:', error);
    }
  };

  const saveUserName = async () => {
    if (tempName.trim()) {
      await AsyncStorage.setItem('userName', tempName.trim());
      setUserName(tempName.trim());
      setShowNameModal(false);
      setTempName('');
    }
  };

  const loadChatHistory = async () => {
    try {
      const stored = await AsyncStorage.getItem('chatHistory');
      if (stored) {
        const history = JSON.parse(stored);
        setRecentChats(history.slice(0, 3)); // Show last 3 conversations
      }
    } catch (error) {
      console.error('Error loading chat history:', error);
    }
  };

  const saveChatHistory = async (message: string, response: string) => {
    try {
      const stored = await AsyncStorage.getItem('chatHistory');
      const history = stored ? JSON.parse(stored) : [];
      
      const newChat: ChatHistory = {
        message,
        response,
        time: new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
      };
      
      const updatedHistory = [newChat, ...history].slice(0, 10); // Keep last 10
      await AsyncStorage.setItem('chatHistory', JSON.stringify(updatedHistory));
      setRecentChats(updatedHistory.slice(0, 3));
    } catch (error) {
      console.error('Error saving chat history:', error);
    }
  };

  const requestPermissions = async () => {
    const { status } = await Notifications.requestPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission needed', 'Please enable notifications to receive reminders');
    }
  };

  const setupNotifications = async () => {
    const storedReminders = await AsyncStorage.getItem('reminders');
    if (storedReminders) {
      const remindersList: Reminder[] = JSON.parse(storedReminders);
      remindersList.forEach(async (reminder) => {
        if (reminder.enabled) {
          await scheduleNotification(reminder);
        }
      });
    }
  };

  const scheduleNotification = async (reminder: Reminder) => {
    const [hours, minutes] = reminder.time.split(':').map(Number);
    const now = new Date();
    const scheduledTime = new Date();
    scheduledTime.setHours(hours, minutes, 0, 0);

    if (scheduledTime < now) {
      scheduledTime.setDate(scheduledTime.getDate() + 1);
    }

    await Notifications.scheduleNotificationAsync({
      content: {
        title: reminder.type === 'medicine' ? '💊 Medicine Time' : '🚶 Time for a Walk',
        body: reminder.title,
        sound: true,
      },
      trigger: {
        hour: hours,
        minute: minutes,
        repeats: true,
      },
    });
  };

  const loadReminders = async () => {
    try {
      const stored = await AsyncStorage.getItem('reminders');
      if (stored) {
        setReminders(JSON.parse(stored));
      }
    } catch (error) {
      console.error('Error loading reminders:', error);
    }
  };

  const speak = (text: string) => {
    setIsSpeaking(true);
    Speech.speak(text, {
      language: 'en-US',
      pitch: 1.0,
      rate: 0.75,
      onDone: () => setIsSpeaking(false),
      onStopped: () => setIsSpeaking(false),
      onError: () => setIsSpeaking(false),
    });
  };

  const handleTalk = async () => {
    if (isListening) {
      setIsListening(false);
      return;
    }

    Alert.prompt(
      `Talk to me, ${userName}`,
      'What would you like to talk about?',
      async (text) => {
        if (text && text.trim()) {
          await sendMessage(text);
        }
      },
      'plain-text'
    );
  };

  const sendMessage = async (message: string) => {
    setLoading(true);
    setCurrentMessage('');

    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: `My name is ${userName}. ${message}`,
          user_id: userName.toLowerCase().replace(/\s+/g, '_'),
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to get response');
      }

      const data = await response.json();
      speak(data.response);
      setCurrentMessage(data.response);
      await saveChatHistory(message, data.response);
    } catch (error) {
      console.error('Error sending message:', error);
      Alert.alert('Sorry', 'I had trouble connecting. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSuggestion = (text: string) => {
    sendMessage(text);
  };

  const handleSOS = () => {
    Alert.alert(
      '🚨 Emergency',
      'Would you like to call for help?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Call Emergency',
          style: 'destructive',
          onPress: () => {
            Linking.openURL('tel:911');
          },
        },
      ]
    );
  };

  const addReminder = async () => {
    if (!newReminder.title || !newReminder.time) {
      Alert.alert('Oops', 'Please fill in all the details');
      return;
    }

    const reminder: Reminder = {
      id: Date.now().toString(),
      ...newReminder,
      enabled: true,
    };

    const updatedReminders = [...reminders, reminder];
    setReminders(updatedReminders);
    await AsyncStorage.setItem('reminders', JSON.stringify(updatedReminders));
    await scheduleNotification(reminder);

    setShowReminderModal(false);
    setNewReminder({ type: 'medicine', title: '', time: '' });
    Alert.alert('Done!', 'Your reminder has been set');
  };

  const deleteReminder = async (id: string) => {
    const updatedReminders = reminders.filter((r) => r.id !== id);
    setReminders(updatedReminders);
    await AsyncStorage.setItem('reminders', JSON.stringify(updatedReminders));
    await Notifications.cancelAllScheduledNotificationsAsync();
    setupNotifications();
  };

  const snoozeReminder = async (id: string, minutes: number) => {
    Alert.alert('Snoozed', `I'll remind you again in ${minutes} minutes`);
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
      
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>Saathi</Text>
          {userName && <Text style={styles.headerSubtitle}>Your companion</Text>}
        </View>
        <TouchableOpacity
          style={styles.sosButton}
          onPress={handleSOS}
          activeOpacity={0.8}
        >
          <Ionicons name="warning" size={24} color="#fff" />
          <Text style={styles.sosText}>SOS</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Personalized Greeting */}
        {userName && greeting && (
          <View style={styles.greetingCard}>
            <Text style={styles.greetingText}>{greeting}</Text>
            <Text style={styles.greetingSubtext}>How can I help you today?</Text>
          </View>
        )}

        {/* Active Reminders */}
        {reminders.length > 0 && (
          <View style={styles.remindersSection}>
            <Text style={styles.sectionTitle}>Your Reminders Today</Text>
            {reminders.slice(0, 2).map((reminder) => (
              <View key={reminder.id} style={styles.reminderCard}>
                <View style={styles.reminderIcon}>
                  <Ionicons
                    name={reminder.type === 'medicine' ? 'medical' : 'walk'}
                    size={22}
                    color="#4A90E2"
                  />
                </View>
                <View style={styles.reminderInfo}>
                  <Text style={styles.reminderTitle}>{reminder.title}</Text>
                  <Text style={styles.reminderTime}>{reminder.time}</Text>
                </View>
                <View style={styles.reminderActions}>
                  <TouchableOpacity
                    onPress={() => snoozeReminder(reminder.id, 15)}
                    style={styles.iconButton}
                  >
                    <Ionicons name="time-outline" size={20} color="#666" />
                  </TouchableOpacity>
                  <TouchableOpacity
                    onPress={() => deleteReminder(reminder.id)}
                    style={styles.iconButton}
                  >
                    <Ionicons name="close-circle-outline" size={20} color="#999" />
                  </TouchableOpacity>
                </View>
              </View>
            ))}
          </View>
        )}

        {/* Recent Conversations */}
        {recentChats.length > 0 && (
          <View style={styles.historySection}>
            <Text style={styles.sectionTitle}>Recent Conversations</Text>
            {recentChats.map((chat, index) => (
              <TouchableOpacity
                key={index}
                style={styles.historyCard}
                onPress={() => {
                  setCurrentMessage(chat.response);
                  speak(chat.response);
                }}
              >
                <Text style={styles.historyTime}>{chat.time}</Text>
                <Text style={styles.historyMessage} numberOfLines={2}>
                  You: {chat.message}
                </Text>
                <Text style={styles.historyResponse} numberOfLines={2}>
                  Me: {chat.response}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* Main Talk Section */}
        <View style={styles.mainSection}>
          {currentMessage ? (
            <View style={styles.messageContainer}>
              <Ionicons name="chatbubble-ellipses" size={28} color="#4A90E2" />
              <Text style={styles.messageText}>{currentMessage}</Text>
            </View>
          ) : (
            <View style={styles.welcomeContainer}>
              <Text style={styles.welcomeText}>
                {userName ? `I'm here to listen, ${userName}.` : "I'm here to listen."}
              </Text>
              <Text style={styles.welcomeSubtext}>
                Tap the button below to start talking
              </Text>
            </View>
          )}

          <TouchableOpacity
            style={[
              styles.talkButton,
              (isListening || isSpeaking || loading) && styles.talkButtonActive,
            ]}
            onPress={handleTalk}
            activeOpacity={0.8}
            disabled={loading || isSpeaking}
          >
            {loading ? (
              <ActivityIndicator size="large" color="#fff" />
            ) : (
              <>
                <Ionicons
                  name={isListening ? 'mic' : isSpeaking ? 'volume-high' : 'chatbubbles'}
                  size={56}
                  color="#fff"
                />
                <Text style={styles.talkButtonText}>
                  {isListening ? 'Listening...' : isSpeaking ? 'Speaking...' : 'Talk to me'}
                </Text>
              </>
            )}
          </TouchableOpacity>
        </View>

        {/* Suggestion Cards */}
        <View style={styles.suggestionsSection}>
          <Text style={styles.suggestionsTitle}>Some things we can talk about:</Text>
          <View style={styles.suggestionsGrid}>
            {suggestions.map((suggestion, index) => (
              <TouchableOpacity
                key={index}
                style={styles.suggestionCard}
                onPress={() => handleSuggestion(suggestion.text)}
                activeOpacity={0.7}
              >
                <Ionicons name={suggestion.icon as any} size={22} color="#4A90E2" />
                <Text style={styles.suggestionText}>{suggestion.text}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>

        {/* Add Reminder Button */}
        <TouchableOpacity
          style={styles.addReminderButton}
          onPress={() => setShowReminderModal(true)}
        >
          <Ionicons name="add-circle-outline" size={24} color="#4A90E2" />
          <Text style={styles.addReminderText}>Set a New Reminder</Text>
        </TouchableOpacity>
      </ScrollView>

      {/* Name Setup Modal */}
      <Modal
        visible={showNameModal}
        animationType="fade"
        transparent={true}
        onRequestClose={() => {}}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.nameModalContent}>
            <Ionicons name="person-circle" size={64} color="#4A90E2" />
            <Text style={styles.nameModalTitle}>Welcome to Saathi!</Text>
            <Text style={styles.nameModalSubtext}>
              What should I call you?
            </Text>
            <TextInput
              style={styles.nameInput}
              placeholder="Your name"
              placeholderTextColor="#999"
              value={tempName}
              onChangeText={setTempName}
              autoFocus
            />
            <TouchableOpacity
              style={styles.nameModalButton}
              onPress={saveUserName}
            >
              <Text style={styles.nameModalButtonText}>Let's Begin</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      {/* Add Reminder Modal */}
      <Modal
        visible={showReminderModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowReminderModal(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.modalOverlay}
        >
          <View style={styles.modalContent}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>Set a Reminder</Text>
              <TouchableOpacity onPress={() => setShowReminderModal(false)}>
                <Ionicons name="close" size={28} color="#666" />
              </TouchableOpacity>
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Type</Text>
              <View style={styles.typeSelector}>
                <TouchableOpacity
                  style={[
                    styles.typeButton,
                    newReminder.type === 'medicine' && styles.typeButtonActive,
                  ]}
                  onPress={() => setNewReminder({ ...newReminder, type: 'medicine' })}
                >
                  <Ionicons name="medical" size={20} color={newReminder.type === 'medicine' ? '#fff' : '#4A90E2'} />
                  <Text style={[styles.typeButtonText, newReminder.type === 'medicine' && styles.typeButtonTextActive]}>
                    Medicine
                  </Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[
                    styles.typeButton,
                    newReminder.type === 'walk' && styles.typeButtonActive,
                  ]}
                  onPress={() => setNewReminder({ ...newReminder, type: 'walk' })}
                >
                  <Ionicons name="walk" size={20} color={newReminder.type === 'walk' ? '#fff' : '#4A90E2'} />
                  <Text style={[styles.typeButtonText, newReminder.type === 'walk' && styles.typeButtonTextActive]}>
                    Walk
                  </Text>
                </TouchableOpacity>
              </View>
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>What should I remind you about?</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g., Take blood pressure medicine"
                placeholderTextColor="#999"
                value={newReminder.title}
                onChangeText={(text) => setNewReminder({ ...newReminder, title: text })}
              />
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>What time? (HH:MM)</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g., 09:00"
                placeholderTextColor="#999"
                value={newReminder.time}
                onChangeText={(text) => setNewReminder({ ...newReminder, time: text })}
              />
            </View>

            <TouchableOpacity
              style={styles.saveButton}
              onPress={addReminder}
            >
              <Text style={styles.saveButtonText}>Set Reminder</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5F8FC',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
    backgroundColor: '#2C5F8D',
  },
  headerTitle: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#fff',
  },
  headerSubtitle: {
    fontSize: 14,
    color: '#B8D4E8',
    marginTop: 2,
  },
  sosButton: {
    backgroundColor: '#E74C3C',
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 25,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    shadowColor: '#E74C3C',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  sosText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 40,
  },
  greetingCard: {
    backgroundColor: '#fff',
    borderRadius: 20,
    padding: 24,
    marginBottom: 20,
    borderLeftWidth: 4,
    borderLeftColor: '#4A90E2',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 3,
  },
  greetingText: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#2C5F8D',
    marginBottom: 6,
  },
  greetingSubtext: {
    fontSize: 16,
    color: '#666',
  },
  remindersSection: {
    marginBottom: 24,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#2C5F8D',
    marginBottom: 12,
  },
  reminderCard: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 16,
    marginBottom: 12,
    flexDirection: 'row',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  reminderIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#E8F4FD',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  reminderInfo: {
    flex: 1,
  },
  reminderTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  reminderTime: {
    fontSize: 14,
    color: '#4A90E2',
    fontWeight: '500',
  },
  reminderActions: {
    flexDirection: 'row',
    gap: 8,
  },
  iconButton: {
    padding: 8,
  },
  historySection: {
    marginBottom: 24,
  },
  historyCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    borderLeftWidth: 3,
    borderLeftColor: '#4A90E2',
  },
  historyTime: {
    fontSize: 12,
    color: '#999',
    marginBottom: 6,
  },
  historyMessage: {
    fontSize: 14,
    color: '#666',
    marginBottom: 4,
  },
  historyResponse: {
    fontSize: 14,
    color: '#2C5F8D',
    fontWeight: '500',
  },
  mainSection: {
    alignItems: 'center',
    marginVertical: 28,
  },
  welcomeContainer: {
    alignItems: 'center',
    marginBottom: 28,
  },
  welcomeText: {
    fontSize: 22,
    color: '#2C5F8D',
    textAlign: 'center',
    fontWeight: '600',
    marginBottom: 8,
  },
  welcomeSubtext: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
  },
  messageContainer: {
    backgroundColor: '#fff',
    borderRadius: 20,
    padding: 24,
    marginBottom: 28,
    alignItems: 'center',
    maxWidth: width - 60,
    shadowColor: '#4A90E2',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 16,
    elevation: 4,
  },
  messageText: {
    fontSize: 18,
    color: '#333',
    lineHeight: 28,
    textAlign: 'center',
    marginTop: 12,
  },
  talkButton: {
    width: 170,
    height: 170,
    borderRadius: 85,
    backgroundColor: '#4A90E2',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#4A90E2',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.4,
    shadowRadius: 20,
    elevation: 12,
  },
  talkButtonActive: {
    backgroundColor: '#2C5F8D',
  },
  talkButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
    marginTop: 10,
  },
  suggestionsSection: {
    marginTop: 28,
  },
  suggestionsTitle: {
    fontSize: 17,
    fontWeight: '600',
    color: '#2C5F8D',
    marginBottom: 14,
  },
  suggestionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  suggestionCard: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 16,
    width: (width - 52) / 2,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
    borderWidth: 1,
    borderColor: '#E8F4FD',
  },
  suggestionText: {
    fontSize: 14,
    color: '#333',
    textAlign: 'center',
    marginTop: 10,
    lineHeight: 19,
  },
  addReminderButton: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 18,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 20,
    borderWidth: 2,
    borderColor: '#4A90E2',
    borderStyle: 'dashed',
  },
  addReminderText: {
    fontSize: 17,
    fontWeight: '600',
    color: '#4A90E2',
    marginLeft: 10,
  },
  modalOverlay: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(44, 95, 141, 0.7)',
  },
  nameModalContent: {
    backgroundColor: '#fff',
    borderRadius: 28,
    padding: 32,
    width: width - 60,
    maxWidth: 360,
    alignItems: 'center',
  },
  nameModalTitle: {
    fontSize: 26,
    fontWeight: 'bold',
    color: '#2C5F8D',
    marginTop: 16,
    marginBottom: 8,
  },
  nameModalSubtext: {
    fontSize: 16,
    color: '#666',
    marginBottom: 24,
    textAlign: 'center',
  },
  nameInput: {
    backgroundColor: '#F5F8FC',
    borderRadius: 14,
    padding: 18,
    fontSize: 18,
    color: '#333',
    width: '100%',
    borderWidth: 2,
    borderColor: '#E8F4FD',
    marginBottom: 24,
    textAlign: 'center',
  },
  nameModalButton: {
    backgroundColor: '#4A90E2',
    paddingHorizontal: 40,
    paddingVertical: 16,
    borderRadius: 14,
    width: '100%',
  },
  nameModalButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#fff',
    textAlign: 'center',
  },
  modalContent: {
    backgroundColor: '#fff',
    borderTopLeftRadius: 28,
    borderTopRightRadius: 28,
    padding: 24,
    width: width,
    maxHeight: height * 0.8,
    marginTop: 'auto',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  modalTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#2C5F8D',
  },
  inputGroup: {
    marginBottom: 20,
  },
  inputLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: '#2C5F8D',
    marginBottom: 10,
  },
  input: {
    backgroundColor: '#F5F8FC',
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    color: '#333',
    borderWidth: 1,
    borderColor: '#E8F4FD',
  },
  typeSelector: {
    flexDirection: 'row',
    gap: 12,
  },
  typeButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 16,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: '#4A90E2',
    backgroundColor: '#fff',
    gap: 8,
  },
  typeButtonActive: {
    backgroundColor: '#4A90E2',
  },
  typeButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#4A90E2',
  },
  typeButtonTextActive: {
    color: '#fff',
  },
  saveButton: {
    backgroundColor: '#4A90E2',
    padding: 18,
    borderRadius: 14,
    alignItems: 'center',
    marginTop: 12,
  },
  saveButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#fff',
  },
});
