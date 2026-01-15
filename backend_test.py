#!/usr/bin/env python3
"""
Comprehensive Backend Testing for Saathi App
Tests all API endpoints with realistic elderly-focused data
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Backend URL from environment
BACKEND_URL = "https://elder-pal.preview.emergentagent.com/api"

class SaathiBackendTester:
    def __init__(self):
        self.base_url = BACKEND_URL
        self.session = requests.Session()
        self.test_results = []
        self.created_user_id = None
        self.created_reminder_ids = []
        
    def log_test(self, test_name: str, success: bool, details: str, response_data: Any = None):
        """Log test results"""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat(),
            "response_data": response_data
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {details}")
        
    def test_api_root(self):
        """Test API root endpoint"""
        try:
            response = self.session.get(f"{self.base_url}/")
            if response.status_code == 200:
                data = response.json()
                if "message" in data and "Saathi" in data["message"]:
                    self.log_test("API Root", True, f"API is running: {data['message']}")
                    return True
                else:
                    self.log_test("API Root", False, f"Unexpected response: {data}")
                    return False
            else:
                self.log_test("API Root", False, f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("API Root", False, f"Connection error: {str(e)}")
            return False
    
    def test_user_creation(self):
        """Test user creation with emergency contacts"""
        try:
            user_data = {
                "name": "Rajesh Kumar",
                "emergency_contacts": [
                    {"name": "Dr. Sharma", "phone": "+91-9876543210"},
                    {"name": "Son - Amit", "phone": "+91-9876543211"}
                ]
            }
            
            response = self.session.post(f"{self.base_url}/users", json=user_data)
            
            if response.status_code == 200:
                data = response.json()
                if "id" in data and data["name"] == "Rajesh Kumar":
                    self.created_user_id = data["id"]
                    self.log_test("User Creation", True, f"User created with ID: {data['id']}", data)
                    return True
                else:
                    self.log_test("User Creation", False, f"Invalid response structure: {data}")
                    return False
            else:
                self.log_test("User Creation", False, f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("User Creation", False, f"Error: {str(e)}")
            return False
    
    def test_user_retrieval(self):
        """Test getting user by ID"""
        if not self.created_user_id:
            self.log_test("User Retrieval", False, "No user ID available for testing")
            return False
            
        try:
            response = self.session.get(f"{self.base_url}/users/{self.created_user_id}")
            
            if response.status_code == 200:
                data = response.json()
                if data["id"] == self.created_user_id and data["name"] == "Rajesh Kumar":
                    self.log_test("User Retrieval", True, f"User retrieved successfully: {data['name']}", data)
                    return True
                else:
                    self.log_test("User Retrieval", False, f"Data mismatch: {data}")
                    return False
            else:
                self.log_test("User Retrieval", False, f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("User Retrieval", False, f"Error: {str(e)}")
            return False
    
    def test_users_list(self):
        """Test getting all users"""
        try:
            response = self.session.get(f"{self.base_url}/users")
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    self.log_test("Users List", True, f"Retrieved {len(data)} users", {"count": len(data)})
                    return True
                else:
                    self.log_test("Users List", False, f"Expected list, got: {type(data)}")
                    return False
            else:
                self.log_test("Users List", False, f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Users List", False, f"Error: {str(e)}")
            return False
    
    def test_reminder_creation_medicine(self):
        """Test creating medicine reminder"""
        try:
            reminder_data = {
                "type": "medicine",
                "title": "Blood Pressure Medicine - Amlodipine 5mg",
                "time": "09:00",
                "enabled": True
            }
            
            response = self.session.post(f"{self.base_url}/reminders?user_id=rajesh_kumar", json=reminder_data)
            
            if response.status_code == 200:
                data = response.json()
                if "id" in data and data["type"] == "medicine":
                    self.created_reminder_ids.append(data["id"])
                    self.log_test("Medicine Reminder Creation", True, f"Medicine reminder created: {data['title']}", data)
                    return True
                else:
                    self.log_test("Medicine Reminder Creation", False, f"Invalid response: {data}")
                    return False
            else:
                self.log_test("Medicine Reminder Creation", False, f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Medicine Reminder Creation", False, f"Error: {str(e)}")
            return False
    
    def test_reminder_creation_walk(self):
        """Test creating walk reminder"""
        try:
            reminder_data = {
                "type": "walk",
                "title": "Evening Walk in the Park",
                "time": "17:30",
                "enabled": True
            }
            
            response = self.session.post(f"{self.base_url}/reminders?user_id=rajesh_kumar", json=reminder_data)
            
            if response.status_code == 200:
                data = response.json()
                if "id" in data and data["type"] == "walk":
                    self.created_reminder_ids.append(data["id"])
                    self.log_test("Walk Reminder Creation", True, f"Walk reminder created: {data['title']}", data)
                    return True
                else:
                    self.log_test("Walk Reminder Creation", False, f"Invalid response: {data}")
                    return False
            else:
                self.log_test("Walk Reminder Creation", False, f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Walk Reminder Creation", False, f"Error: {str(e)}")
            return False
    
    def test_reminders_list(self):
        """Test getting all reminders for a user"""
        try:
            response = self.session.get(f"{self.base_url}/reminders?user_id=rajesh_kumar")
            
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) >= 2:
                    self.log_test("Reminders List", True, f"Retrieved {len(data)} reminders for user", {"count": len(data)})
                    return True
                else:
                    self.log_test("Reminders List", False, f"Expected at least 2 reminders, got: {len(data) if isinstance(data, list) else 'not a list'}")
                    return False
            else:
                self.log_test("Reminders List", False, f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Reminders List", False, f"Error: {str(e)}")
            return False
    
    def test_reminder_update(self):
        """Test updating a reminder"""
        if not self.created_reminder_ids:
            self.log_test("Reminder Update", False, "No reminder ID available for testing")
            return False
            
        try:
            reminder_id = self.created_reminder_ids[0]
            update_data = {
                "time": "08:30",
                "enabled": False
            }
            
            response = self.session.patch(f"{self.base_url}/reminders/{reminder_id}", json=update_data)
            
            if response.status_code == 200:
                data = response.json()
                if data["time"] == "08:30" and data["enabled"] == False:
                    self.log_test("Reminder Update", True, f"Reminder updated successfully: time={data['time']}, enabled={data['enabled']}", data)
                    return True
                else:
                    self.log_test("Reminder Update", False, f"Update not reflected: {data}")
                    return False
            else:
                self.log_test("Reminder Update", False, f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Reminder Update", False, f"Error: {str(e)}")
            return False
    
    def test_reminder_snooze(self):
        """Test snoozing a reminder"""
        if not self.created_reminder_ids:
            self.log_test("Reminder Snooze", False, "No reminder ID available for testing")
            return False
            
        try:
            reminder_id = self.created_reminder_ids[0]
            
            response = self.session.post(f"{self.base_url}/reminders/{reminder_id}/snooze?minutes=15")
            
            if response.status_code == 200:
                data = response.json()
                if "snoozed_until" in data and "15 minutes" in data["message"]:
                    self.log_test("Reminder Snooze", True, f"Reminder snoozed: {data['message']}", data)
                    return True
                else:
                    self.log_test("Reminder Snooze", False, f"Invalid snooze response: {data}")
                    return False
            else:
                self.log_test("Reminder Snooze", False, f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Reminder Snooze", False, f"Error: {str(e)}")
            return False
    
    def test_chat_basic_message(self):
        """Test basic chat functionality"""
        try:
            chat_data = {
                "message": "Hello, how are you today?",
                "user_id": "rajesh_kumar"
            }
            
            response = self.session.post(f"{self.base_url}/chat", json=chat_data)
            
            if response.status_code == 200:
                data = response.json()
                if "response" in data and len(data["response"]) > 0:
                    # Check if response is elderly-friendly (should be warm and simple)
                    response_text = data["response"].lower()
                    elderly_friendly = any(word in response_text for word in ["hello", "good", "well", "fine", "thank", "how", "feeling"])
                    
                    if elderly_friendly:
                        self.log_test("Chat Basic Message", True, f"AI responded appropriately: {data['response'][:100]}...", data)
                        return True
                    else:
                        self.log_test("Chat Basic Message", False, f"Response may not be elderly-friendly: {data['response']}")
                        return False
                else:
                    self.log_test("Chat Basic Message", False, f"No response in chat data: {data}")
                    return False
            else:
                self.log_test("Chat Basic Message", False, f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Chat Basic Message", False, f"Error: {str(e)}")
            return False
    
    def test_chat_context_persistence(self):
        """Test conversation context persistence"""
        try:
            # First message
            chat_data1 = {
                "message": "My name is Rajesh and I live in Mumbai",
                "user_id": "rajesh_kumar"
            }
            
            response1 = self.session.post(f"{self.base_url}/chat", json=chat_data1)
            
            if response1.status_code != 200:
                self.log_test("Chat Context Persistence", False, f"First message failed: HTTP {response1.status_code}")
                return False
            
            time.sleep(1)  # Small delay
            
            # Second message referencing first
            chat_data2 = {
                "message": "What city did I just mention?",
                "user_id": "rajesh_kumar"
            }
            
            response2 = self.session.post(f"{self.base_url}/chat", json=chat_data2)
            
            if response2.status_code == 200:
                data = response2.json()
                response_text = data["response"].lower()
                
                # Check if AI remembers Mumbai from previous message
                if "mumbai" in response_text:
                    self.log_test("Chat Context Persistence", True, f"AI remembered context: {data['response']}", data)
                    return True
                else:
                    self.log_test("Chat Context Persistence", False, f"AI didn't remember Mumbai: {data['response']}")
                    return False
            else:
                self.log_test("Chat Context Persistence", False, f"Second message failed: HTTP {response2.status_code}")
                return False
        except Exception as e:
            self.log_test("Chat Context Persistence", False, f"Error: {str(e)}")
            return False
    
    def test_conversation_history(self):
        """Test conversation history retrieval"""
        try:
            response = self.session.get(f"{self.base_url}/conversations/rajesh_kumar")
            
            if response.status_code == 200:
                data = response.json()
                if "messages" in data and len(data["messages"]) > 0:
                    self.log_test("Conversation History", True, f"Retrieved {len(data['messages'])} messages", {"message_count": len(data["messages"])})
                    return True
                else:
                    self.log_test("Conversation History", False, f"No messages found in conversation: {data}")
                    return False
            else:
                self.log_test("Conversation History", False, f"HTTP {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log_test("Conversation History", False, f"Error: {str(e)}")
            return False
    
    def test_error_handling(self):
        """Test error handling for invalid requests"""
        tests_passed = 0
        total_tests = 3
        
        # Test invalid user ID
        try:
            response = self.session.get(f"{self.base_url}/users/invalid_id")
            if response.status_code == 400:
                tests_passed += 1
                print("✅ Invalid user ID handled correctly")
            else:
                print(f"❌ Invalid user ID: Expected 400, got {response.status_code}")
        except Exception as e:
            print(f"❌ Invalid user ID test error: {str(e)}")
        
        # Test invalid reminder ID
        try:
            response = self.session.get(f"{self.base_url}/reminders/invalid_id")
            if response.status_code == 400:
                tests_passed += 1
                print("✅ Invalid reminder ID handled correctly")
            else:
                print(f"❌ Invalid reminder ID: Expected 400, got {response.status_code}")
        except Exception as e:
            print(f"❌ Invalid reminder ID test error: {str(e)}")
        
        # Test empty chat message
        try:
            response = self.session.post(f"{self.base_url}/chat", json={"message": ""})
            if response.status_code in [400, 422]:
                tests_passed += 1
                print("✅ Empty chat message handled correctly")
            else:
                print(f"❌ Empty chat message: Expected 400/422, got {response.status_code}")
        except Exception as e:
            print(f"❌ Empty chat message test error: {str(e)}")
        
        success = tests_passed == total_tests
        self.log_test("Error Handling", success, f"Passed {tests_passed}/{total_tests} error handling tests")
        return success
    
    def cleanup_test_data(self):
        """Clean up created test data"""
        # Delete created reminders
        for reminder_id in self.created_reminder_ids:
            try:
                response = self.session.delete(f"{self.base_url}/reminders/{reminder_id}")
                if response.status_code == 200:
                    print(f"✅ Cleaned up reminder: {reminder_id}")
                else:
                    print(f"⚠️ Failed to cleanup reminder {reminder_id}: {response.status_code}")
            except Exception as e:
                print(f"⚠️ Error cleaning up reminder {reminder_id}: {str(e)}")
    
    def run_all_tests(self):
        """Run all backend tests"""
        print(f"\n🚀 Starting Saathi Backend Tests")
        print(f"Backend URL: {self.base_url}")
        print("=" * 60)
        
        # Test sequence based on priority
        tests = [
            ("API Connectivity", self.test_api_root),
            ("User Creation", self.test_user_creation),
            ("User Retrieval", self.test_user_retrieval),
            ("Users List", self.test_users_list),
            ("Medicine Reminder Creation", self.test_reminder_creation_medicine),
            ("Walk Reminder Creation", self.test_reminder_creation_walk),
            ("Reminders List", self.test_reminders_list),
            ("Reminder Update", self.test_reminder_update),
            ("Reminder Snooze", self.test_reminder_snooze),
            ("Chat Basic Message", self.test_chat_basic_message),
            ("Chat Context Persistence", self.test_chat_context_persistence),
            ("Conversation History", self.test_conversation_history),
            ("Error Handling", self.test_error_handling),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                if test_func():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ {test_name}: Unexpected error - {str(e)}")
                failed += 1
            print()  # Add spacing between tests
        
        # Cleanup
        print("🧹 Cleaning up test data...")
        self.cleanup_test_data()
        
        # Summary
        print("\n" + "=" * 60)
        print(f"📊 TEST SUMMARY")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"📈 Success Rate: {(passed/(passed+failed)*100):.1f}%")
        
        return passed, failed, self.test_results

if __name__ == "__main__":
    tester = SaathiBackendTester()
    passed, failed, results = tester.run_all_tests()
    
    # Save detailed results
    with open("/app/backend_test_results.json", "w") as f:
        json.dump({
            "summary": {"passed": passed, "failed": failed, "total": passed + failed},
            "detailed_results": results,
            "timestamp": datetime.now().isoformat()
        }, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: /app/backend_test_results.json")