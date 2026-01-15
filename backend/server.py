from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta
from bson import ObjectId
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Define Models
class EmergencyContact(BaseModel):
    name: str
    phone: str

class User(BaseModel):
    id: Optional[str] = None
    name: str
    emergency_contacts: List[EmergencyContact] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserCreate(BaseModel):
    name: str
    emergency_contacts: List[EmergencyContact] = []

class Reminder(BaseModel):
    id: Optional[str] = None
    user_id: str
    type: str  # "medicine" or "walk"
    title: str
    time: str  # HH:MM format
    enabled: bool = True
    snoozed_until: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ReminderCreate(BaseModel):
    type: str
    title: str
    time: str
    enabled: bool = True

class ReminderUpdate(BaseModel):
    title: Optional[str] = None
    time: Optional[str] = None
    enabled: Optional[bool] = None
    snoozed_until: Optional[datetime] = None

class ChatMessage(BaseModel):
    message: str
    user_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class Conversation(BaseModel):
    id: Optional[str] = None
    user_id: str
    messages: List[dict] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# Helper function to convert ObjectId to string
def serialize_doc(doc):
    if doc and '_id' in doc:
        doc['id'] = str(doc['_id'])
        del doc['_id']
    return doc

# Initialize LLM Chat
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

@api_router.get("/")
async def root():
    return {"message": "Saathi API is running"}

# User endpoints
@api_router.post("/users", response_model=User)
async def create_user(user: UserCreate):
    user_dict = user.dict()
    user_dict['created_at'] = datetime.utcnow()
    result = await db.users.insert_one(user_dict)
    user_dict['id'] = str(result.inserted_id)
    return User(**user_dict)

@api_router.get("/users/{user_id}", response_model=User)
async def get_user(user_id: str):
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return User(**serialize_doc(user))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.get("/users", response_model=List[User])
async def get_users():
    users = await db.users.find().to_list(100)
    return [User(**serialize_doc(user)) for user in users]

# Reminder endpoints
@api_router.post("/reminders", response_model=Reminder)
async def create_reminder(reminder: ReminderCreate, user_id: str = "default"):
    reminder_dict = reminder.dict()
    reminder_dict['user_id'] = user_id
    reminder_dict['created_at'] = datetime.utcnow()
    result = await db.reminders.insert_one(reminder_dict)
    reminder_dict['id'] = str(result.inserted_id)
    return Reminder(**reminder_dict)

@api_router.get("/reminders", response_model=List[Reminder])
async def get_reminders(user_id: str = "default"):
    reminders = await db.reminders.find({"user_id": user_id}).to_list(100)
    return [Reminder(**serialize_doc(reminder)) for reminder in reminders]

@api_router.get("/reminders/{reminder_id}", response_model=Reminder)
async def get_reminder(reminder_id: str):
    try:
        reminder = await db.reminders.find_one({"_id": ObjectId(reminder_id)})
        if not reminder:
            raise HTTPException(status_code=404, detail="Reminder not found")
        return Reminder(**serialize_doc(reminder))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.patch("/reminders/{reminder_id}", response_model=Reminder)
async def update_reminder(reminder_id: str, update: ReminderUpdate):
    try:
        update_dict = {k: v for k, v in update.dict().items() if v is not None}
        if not update_dict:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        result = await db.reminders.update_one(
            {"_id": ObjectId(reminder_id)},
            {"$set": update_dict}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Reminder not found")
        
        reminder = await db.reminders.find_one({"_id": ObjectId(reminder_id)})
        return Reminder(**serialize_doc(reminder))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.delete("/reminders/{reminder_id}")
async def delete_reminder(reminder_id: str):
    try:
        result = await db.reminders.delete_one({"_id": ObjectId(reminder_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Reminder not found")
        return {"message": "Reminder deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Snooze reminder
@api_router.post("/reminders/{reminder_id}/snooze")
async def snooze_reminder(reminder_id: str, minutes: int = 15):
    try:
        snoozed_until = datetime.utcnow() + timedelta(minutes=minutes)
        result = await db.reminders.update_one(
            {"_id": ObjectId(reminder_id)},
            {"$set": {"snoozed_until": snoozed_until}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Reminder not found")
        
        return {"message": f"Reminder snoozed for {minutes} minutes", "snoozed_until": snoozed_until}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Chat endpoint
@api_router.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    try:
        user_id = message.user_id or "default"
        
        # Get or create conversation
        conversation = await db.conversations.find_one({"user_id": user_id})
        
        if not conversation:
            conversation = {
                "user_id": user_id,
                "messages": [],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            result = await db.conversations.insert_one(conversation)
            conversation['_id'] = result.inserted_id
        
        # Initialize LLM Chat with system message
        system_message = """You are Saathi, a calm, warm, and empathetic voice companion for elderly parents. 
        You speak like a caring friend - simple, clear, and comforting. 
        Keep responses short (2-3 sentences max) and age-appropriate.
        
        IMPORTANT - Voice Command Detection:
        If the user asks to set a reminder or mentions any activity with a time, respond ONLY with:
        "REMINDER_COMMAND:{type}:{title}:{time}"
        
        Examples:
        - "Remind me to take my blood pressure medicine at 9am" → "REMINDER_COMMAND:medicine:Take blood pressure medicine:09:00"
        - "Set a reminder to call my son at 3pm" → "REMINDER_COMMAND:call:Call my son:15:00"
        - "I need to do yoga at 6 in the morning" → "REMINDER_COMMAND:exercise:Do yoga:06:00"
        - "Remind me to pray at 7pm" → "REMINDER_COMMAND:prayer:Time to pray:19:00"
        - "Set alarm for breakfast at 8am" → "REMINDER_COMMAND:meal:Breakfast time:08:00"
        
        Supported types: medicine, walk, call, exercise, prayer, meal, appointment, or any custom activity
        
        For confirmation responses (when they say they took medicine or completed task):
        - If they say "I took it", "done", "finished", "yes I did" → Respond warmly: "Wonderful! I'm so proud of you. Taking care of your health is important."
        
        For snooze requests:
        - If they say "snooze", "remind me later", "not now", "5 more minutes" → "SNOOZE_COMMAND:15"
        
        For all other conversations, be warm, supportive, and helpful.
        Focus on being supportive, patient, and understanding.
        Avoid technical jargon. Use warm, friendly language."""
        
        llm_chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=str(conversation['_id']),
            system_message=system_message
        ).with_model("openai", "gpt-5.2")
        
        # Send message
        user_message = UserMessage(text=message.message)
        response = await llm_chat.send_message(user_message)
        
        # Save conversation
        conversation['messages'].append({
            "role": "user",
            "content": message.message,
            "timestamp": datetime.utcnow()
        })
        conversation['messages'].append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.utcnow()
        })
        conversation['updated_at'] = datetime.utcnow()
        
        # Keep only last 10 messages for context
        if len(conversation['messages']) > 20:
            conversation['messages'] = conversation['messages'][-20:]
        
        await db.conversations.update_one(
            {"_id": conversation['_id']},
            {"$set": {"messages": conversation['messages'], "updated_at": conversation['updated_at']}}
        )
        
        return ChatResponse(response=response, timestamp=datetime.utcnow())
    except Exception as e:
        logging.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

# Get conversation history
@api_router.get("/conversations/{user_id}")
async def get_conversation(user_id: str):
    conversation = await db.conversations.find_one({"user_id": user_id})
    if not conversation:
        return {"messages": []}
    return serialize_doc(conversation)

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
