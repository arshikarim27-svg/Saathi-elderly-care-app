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

  const suggestions: SuggestionCard[] = [
    { text: 'Tell me a story', icon: 'book' },
    { text: 'Remind me to take medicine', icon: 'medical' },
    { text: 'How is the weather today?', icon: 'sunny' },
    { text: 'Share a health tip', icon: 'heart' },
  ];

  useEffect(() => {
    requestPermissions();
    loadReminders();
    setupNotifications();
  }, []);

  const requestPermissions = async () => {
    const { status } = await Notifications.requestPermissionsAsync();
    if (status !== 'granted') {
      Alert.alert('Permission needed', 'Please enable notifications to receive reminders');
    }
  };

  const setupNotifications = async () => {
    // Schedule notifications for reminders
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
        title: reminder.type === 'medicine' ? '💊 Medicine Reminder' : '🚶 Walk Reminder',
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
      rate: 0.8,
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

    // For MVP, we'll show a simple input for now
    Alert.prompt(
      'Talk to Saathi',
      'What would you like to say?',
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
    setCurrentMessage(message);

    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: message,
          user_id: 'default',
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to get response');
      }

      const data = await response.json();
      speak(data.response);
      setCurrentMessage(data.response);
    } catch (error) {
      console.error('Error sending message:', error);
      Alert.alert('Error', 'Could not connect to Saathi. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSuggestion = (text: string) => {
    sendMessage(text);
  };

  const handleSOS = () => {
    Alert.alert(
      '🚨 Emergency SOS',
      'Call emergency services?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Call 911',
          onPress: () => {
            Linking.openURL('tel:911');
          },
        },
      ]
    );
  };

  const addReminder = async () => {
    if (!newReminder.title || !newReminder.time) {
      Alert.alert('Error', 'Please fill in all fields');
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
    Alert.alert('Success', 'Reminder added successfully!');
  };

  const deleteReminder = async (id: string) => {
    const updatedReminders = reminders.filter((r) => r.id !== id);
    setReminders(updatedReminders);
    await AsyncStorage.setItem('reminders', JSON.stringify(updatedReminders));
    await Notifications.cancelAllScheduledNotificationsAsync();
    setupNotifications();
  };

  const snoozeReminder = async (id: string, minutes: number) => {
    Alert.alert('Snoozed', `Reminder snoozed for ${minutes} minutes`);
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="dark" />
      
      {/* Header with SOS */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Saathi</Text>
        <TouchableOpacity
          style={styles.sosButton}
          onPress={handleSOS}
          activeOpacity={0.8}
        >
          <Ionicons name="warning" size={28} color="#fff" />
          <Text style={styles.sosText}>SOS</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Active Reminders */}
        {reminders.length > 0 && (
          <View style={styles.remindersSection}>
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>Today's Reminders</Text>
            </View>
            {reminders.slice(0, 2).map((reminder) => (
              <View key={reminder.id} style={styles.reminderCard}>
                <View style={styles.reminderIcon}>
                  <Ionicons
                    name={reminder.type === 'medicine' ? 'medical' : 'walk'}
                    size={24}
                    color="#FF9966"
                  />
                </View>
                <View style={styles.reminderInfo}>
                  <Text style={styles.reminderTitle}>{reminder.title}</Text>
                  <Text style={styles.reminderTime}>{reminder.time}</Text>
                </View>
                <View style={styles.reminderActions}>
                  <TouchableOpacity
                    onPress={() => snoozeReminder(reminder.id, 15)}
                    style={styles.snoozeButton}
                  >
                    <Ionicons name="time" size={20} color="#666" />
                  </TouchableOpacity>
                  <TouchableOpacity
                    onPress={() => deleteReminder(reminder.id)}
                    style={styles.deleteButton}
                  >
                    <Ionicons name="close-circle" size={20} color="#999" />
                  </TouchableOpacity>
                </View>
              </View>
            ))}
          </View>
        )}

        {/* Main Talk Button */}
        <View style={styles.mainSection}>
          {currentMessage ? (
            <View style={styles.messageContainer}>
              <Text style={styles.messageText}>{currentMessage}</Text>
            </View>
          ) : (
            <Text style={styles.welcomeText}>
              Hi! I'm Saathi, your friendly companion. {'\n'}
              Tap the button below to talk to me.
            </Text>
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
                  size={60}
                  color="#fff"
                />
                <Text style={styles.talkButtonText}>
                  {isListening ? 'Listening...' : isSpeaking ? 'Speaking...' : 'Talk to Saathi'}
                </Text>
              </>
            )}
          </TouchableOpacity>
        </View>

        {/* Suggestion Cards */}
        <View style={styles.suggestionsSection}>
          <Text style={styles.suggestionsTitle}>You can ask me about:</Text>
          <View style={styles.suggestionsGrid}>
            {suggestions.map((suggestion, index) => (
              <TouchableOpacity
                key={index}
                style={styles.suggestionCard}
                onPress={() => handleSuggestion(suggestion.text)}
                activeOpacity={0.7}
              >
                <Ionicons name={suggestion.icon as any} size={24} color="#FF9966" />
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
          <Ionicons name="add-circle" size={24} color="#FF9966" />
          <Text style={styles.addReminderText}>Add Reminder</Text>
        </TouchableOpacity>
      </ScrollView>

      {/* Add Reminder Modal */}
      <Modal
        visible={showReminderModal}
        animationType="slide"
        transparent={true}
        onRequestClose={() => setShowReminderModal(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.modalContainer}
        >
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Add New Reminder</Text>

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
                  <Ionicons name="medical" size={20} color={newReminder.type === 'medicine' ? '#fff' : '#FF9966'} />
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
                  <Ionicons name="walk" size={20} color={newReminder.type === 'walk' ? '#fff' : '#FF9966'} />
                  <Text style={[styles.typeButtonText, newReminder.type === 'walk' && styles.typeButtonTextActive]}>
                    Walk
                  </Text>
                </TouchableOpacity>
              </View>
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Title</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g., Take blood pressure medicine"
                placeholderTextColor="#999"
                value={newReminder.title}
                onChangeText={(text) => setNewReminder({ ...newReminder, title: text })}
              />
            </View>

            <View style={styles.inputGroup}>
              <Text style={styles.inputLabel}>Time (HH:MM)</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g., 09:00"
                placeholderTextColor="#999"
                value={newReminder.time}
                onChangeText={(text) => setNewReminder({ ...newReminder, time: text })}
              />
            </View>

            <View style={styles.modalButtons}>
              <TouchableOpacity
                style={[styles.modalButton, styles.cancelButton]}
                onPress={() => setShowReminderModal(false)}
              >
                <Text style={styles.cancelButtonText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.modalButton, styles.saveButton]}
                onPress={addReminder}
              >
                <Text style={styles.saveButtonText}>Add Reminder</Text>
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFF5E6',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#FFE4CC',
  },
  headerTitle: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#FF9966',
  },
  sosButton: {
    backgroundColor: '#FF4444',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 25,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    shadowColor: '#FF4444',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  sosText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: 'bold',
  },
  scrollContent: {
    padding: 20,
  },
  remindersSection: {
    marginBottom: 24,
  },
  sectionHeader: {
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#333',
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
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 3,
  },
  reminderIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: '#FFF5E6',
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
    color: '#666',
  },
  reminderActions: {
    flexDirection: 'row',
    gap: 12,
  },
  snoozeButton: {
    padding: 8,
  },
  deleteButton: {
    padding: 8,
  },
  mainSection: {
    alignItems: 'center',
    marginVertical: 32,
  },
  welcomeText: {
    fontSize: 20,
    color: '#666',
    textAlign: 'center',
    marginBottom: 32,
    lineHeight: 28,
    paddingHorizontal: 20,
  },
  messageContainer: {
    backgroundColor: '#fff',
    borderRadius: 20,
    padding: 24,
    marginBottom: 32,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 4,
  },
  messageText: {
    fontSize: 18,
    color: '#333',
    lineHeight: 26,
    textAlign: 'center',
  },
  talkButton: {
    width: 180,
    height: 180,
    borderRadius: 90,
    backgroundColor: '#FF9966',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#FF9966',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.4,
    shadowRadius: 16,
    elevation: 12,
  },
  talkButtonActive: {
    backgroundColor: '#FF7744',
  },
  talkButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
    marginTop: 8,
  },
  suggestionsSection: {
    marginTop: 32,
  },
  suggestionsTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginBottom: 16,
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
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 3,
  },
  suggestionText: {
    fontSize: 14,
    color: '#333',
    textAlign: 'center',
    marginTop: 8,
    lineHeight: 18,
  },
  addReminderButton: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 20,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 24,
    marginBottom: 32,
    borderWidth: 2,
    borderColor: '#FF9966',
    borderStyle: 'dashed',
  },
  addReminderText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FF9966',
    marginLeft: 12,
  },
  modalContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
  },
  modalContent: {
    backgroundColor: '#fff',
    borderRadius: 24,
    padding: 24,
    width: width - 48,
    maxWidth: 400,
  },
  modalTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 24,
    textAlign: 'center',
  },
  inputGroup: {
    marginBottom: 20,
  },
  inputLabel: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#FFF5E6',
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    color: '#333',
    borderWidth: 1,
    borderColor: '#FFE4CC',
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
    borderColor: '#FF9966',
    backgroundColor: '#fff',
    gap: 8,
  },
  typeButtonActive: {
    backgroundColor: '#FF9966',
  },
  typeButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FF9966',
  },
  typeButtonTextActive: {
    color: '#fff',
  },
  modalButtons: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 24,
  },
  modalButton: {
    flex: 1,
    padding: 16,
    borderRadius: 12,
    alignItems: 'center',
  },
  cancelButton: {
    backgroundColor: '#f0f0f0',
  },
  cancelButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#666',
  },
  saveButton: {
    backgroundColor: '#FF9966',
  },
  saveButtonText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#fff',
  },
});
