from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import requests
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
        
        1. REMINDER COMMANDS - If user asks to set a reminder:
        "REMINDER_COMMAND:{type}:{title}:{time}"
        Examples: "Remind me to call my son at 3pm" → "REMINDER_COMMAND:call:Call my son:15:00"
        
        2. LOCATION QUERIES - If user asks about nearby places:
        "LOCATION_QUERY:{type}"
        Examples:
        - "Where is the nearest hospital?" → "LOCATION_QUERY:hospital"
        - "Find pharmacy near me" → "LOCATION_QUERY:pharmacy"
        - "Show me doctors nearby" → "LOCATION_QUERY:doctor"
        - "Where can I buy medicine?" → "LOCATION_QUERY:pharmacy"
        
        3. CONFIRMATIONS - When they confirm completion:
        "Wonderful! I'm so proud of you. Taking care of your health is important."
        
        4. SNOOZE - When they want to delay:
        "SNOOZE_COMMAND:15"
        
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

# Google Maps Integration
GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY')
NEWS_API_KEY = os.environ.get('NEWS_API_KEY')
SPOONACULAR_API_KEY = os.environ.get('SPOONACULAR_API_KEY')
OPENWEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY')
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')

@api_router.get("/maps/nearby")
async def find_nearby_places(
    lat: float,
    lng: float,
    type: str = "hospital",
    radius: int = 5000
):
    """Find nearby places (hospitals, pharmacies, doctors)"""
    try:
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "location": f"{lat},{lng}",
            "radius": radius,
            "type": type,
            "key": GOOGLE_MAPS_API_KEY
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if data.get("status") != "OK":
            raise HTTPException(status_code=400, detail=data.get("status"))
        
        # Format results for elderly-friendly display
        places = []
        for place in data.get("results", [])[:5]:  # Limit to 5 closest
            places.append({
                "name": place["name"],
                "address": place.get("vicinity", "Address not available"),
                "rating": place.get("rating", "No rating"),
                "open_now": place.get("opening_hours", {}).get("open_now", None),
                "lat": place["geometry"]["location"]["lat"],
                "lng": place["geometry"]["location"]["lng"]
            })
        
        return {"places": places, "count": len(places)}
    except Exception as e:
        logging.error(f"Maps error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/maps/directions")
async def get_directions(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float
):
    """Get directions from origin to destination"""
    try:
        url = "https://maps.googleapis.com/maps/api/directions/json"
        params = {
            "origin": f"{origin_lat},{origin_lng}",
            "destination": f"{dest_lat},{dest_lng}",
            "mode": "walking",  # Elderly-friendly walking directions
            "key": GOOGLE_MAPS_API_KEY
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if data.get("status") != "OK":
            raise HTTPException(status_code=400, detail=data.get("status"))
        
        route = data["routes"][0]
        leg = route["legs"][0]
        
        # Extract simple, clear instructions
        steps = []
        for step in leg["steps"]:
            steps.append({
                "instruction": step["html_instructions"].replace("<b>", "").replace("</b>", ""),
                "distance": step["distance"]["text"],
                "duration": step["duration"]["text"]
            })
        
        return {
            "total_distance": leg["distance"]["text"],
            "total_duration": leg["duration"]["text"],
            "steps": steps
        }
    except Exception as e:
        logging.error(f"Directions error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/maps/geocode")
async def geocode_address(address: str):
    """Convert address to coordinates"""
    try:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": address,
            "key": GOOGLE_MAPS_API_KEY
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if data.get("status") != "OK":
            raise HTTPException(status_code=400, detail="Address not found")
        
        location = data["results"][0]["geometry"]["location"]
        formatted_address = data["results"][0]["formatted_address"]
        
        return {
            "lat": location["lat"],
            "lng": location["lng"],
            "formatted_address": formatted_address
        }
    except Exception as e:
        logging.error(f"Geocode error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
