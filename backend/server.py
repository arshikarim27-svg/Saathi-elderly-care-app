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
        
        1. REMINDER COMMANDS:
        "REMINDER_COMMAND:{type}:{title}:{time}"
        Example: "Remind me to call son at 3pm" → "REMINDER_COMMAND:call:Call son:15:00"
        
        2. LOCATION QUERIES:
        "LOCATION_QUERY:{type}"
        Examples: "Where is nearest hospital?" → "LOCATION_QUERY:hospital"
        
        3. NEWS QUERIES:
        "NEWS_QUERY:{category}"
        Examples:
        - "Tell me the news" / "What's happening?" → "NEWS_QUERY:general"
        - "Sports news" → "NEWS_QUERY:sports"
        - "Health news" → "NEWS_QUERY:health"
        
        4. WEATHER QUERIES:
        "WEATHER_QUERY"
        Examples: "What's the weather?" / "Should I take umbrella?" → "WEATHER_QUERY"
        
        5. RECIPE QUERIES:
        "RECIPE_QUERY:{ingredients or dish name}"
        Examples:
        - "What can I cook with potatoes?" → "RECIPE_QUERY:potatoes"
        - "Show me dal recipe" → "RECIPE_QUERY:dal"
        - "Diabetic friendly recipe" → "RECIPE_QUERY:diabetic"
        
        6. YOUTUBE/VIDEO QUERIES:
        "YOUTUBE_QUERY:{search term}"
        Examples:
        - "Play morning prayers" → "YOUTUBE_QUERY:morning prayers"
        - "Show me yoga videos" → "YOUTUBE_QUERY:yoga for seniors"
        - "Play Hanuman Chalisa" → "YOUTUBE_QUERY:Hanuman Chalisa"
        
        7. CONFIRMATIONS:
        "Wonderful! I'm so proud of you."
        
        8. SNOOZE:
        "SNOOZE_COMMAND:15"
        
        For all other conversations, be warm, supportive, and helpful."""
        
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

# News API Integration (India-focused)
@api_router.get("/news/headlines")
async def get_news_headlines(category: str = "general", country: str = "in"):
    """Get top news headlines for India"""
    try:
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "category": category,
            "country": country,  # Default to India
            "apiKey": NEWS_API_KEY,
            "pageSize": 5
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if data.get("status") != "ok":
            raise HTTPException(status_code=400, detail="News API error")
        
        # Format for elderly-friendly display
        articles = []
        for article in data.get("articles", []):
            articles.append({
                "title": article["title"],
                "description": article.get("description", "")[:150] + "..." if article.get("description") else "",
                "source": article["source"]["name"],
                "published": article["publishedAt"]
            })
        
        return {"articles": articles, "count": len(articles)}
    except Exception as e:
        logging.error(f"News error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/news/search")
async def search_news(query: str, language: str = "en"):
    """Search news by keyword"""
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "language": language,
            "sortBy": "publishedAt",
            "apiKey": NEWS_API_KEY,
            "pageSize": 5
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if data.get("status") != "ok":
            raise HTTPException(status_code=400, detail="News search error")
        
        articles = []
        for article in data.get("articles", []):
            articles.append({
                "title": article["title"],
                "description": article.get("description", "")[:150] + "...",
                "source": article["source"]["name"]
            })
        
        return {"articles": articles, "query": query}
    except Exception as e:
        logging.error(f"News search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Weather API Integration
@api_router.get("/weather/current")
async def get_current_weather(lat: float, lng: float):
    """Get current weather"""
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": lat,
            "lon": lng,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric"
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Weather API error")
        
        return {
            "temperature": round(data["main"]["temp"]),
            "feels_like": round(data["main"]["feels_like"]),
            "description": data["weather"][0]["description"],
            "humidity": data["main"]["humidity"],
            "wind_speed": data["wind"]["speed"],
            "city": data.get("name", "Your location")
        }
    except Exception as e:
        logging.error(f"Weather error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/weather/forecast")
async def get_weather_forecast(lat: float, lng: float):
    """Get 3-day weather forecast"""
    try:
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {
            "lat": lat,
            "lon": lng,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
            "cnt": 24  # 3 days (8 per day)
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Forecast API error")
        
        # Group by day
        daily_forecast = []
        for i in range(0, len(data["list"]), 8):
            day_data = data["list"][i]
            daily_forecast.append({
                "date": day_data["dt_txt"].split(" ")[0],
                "temperature": round(day_data["main"]["temp"]),
                "description": day_data["weather"][0]["description"]
            })
        
        return {"forecast": daily_forecast[:3]}
    except Exception as e:
        logging.error(f"Forecast error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Recipe API Integration
@api_router.get("/recipes/search")
async def search_recipes(query: str, diet: str = None):
    """Search recipes by ingredients or name"""
    try:
        url = "https://api.spoonacular.com/recipes/complexSearch"
        params = {
            "query": query,
            "apiKey": SPOONACULAR_API_KEY,
            "number": 5,
            "addRecipeInformation": True
        }
        
        if diet:
            params["diet"] = diet
        
        response = requests.get(url, params=params)
        data = response.json()
        
        recipes = []
        for recipe in data.get("results", []):
            recipes.append({
                "id": recipe["id"],
                "title": recipe["title"],
                "ready_in_minutes": recipe.get("readyInMinutes", "N/A"),
                "servings": recipe.get("servings", "N/A"),
                "image": recipe.get("image", "")
            })
        
        return {"recipes": recipes, "count": len(recipes)}
    except Exception as e:
        logging.error(f"Recipe search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/recipes/{recipe_id}")
async def get_recipe_details(recipe_id: int):
    """Get detailed recipe instructions"""
    try:
        url = f"https://api.spoonacular.com/recipes/{recipe_id}/information"
        params = {
            "apiKey": SPOONACULAR_API_KEY
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        # Extract simple instructions
        instructions = []
        if "analyzedInstructions" in data and data["analyzedInstructions"]:
            for step in data["analyzedInstructions"][0]["steps"]:
                instructions.append({
                    "step": step["number"],
                    "instruction": step["step"]
                })
        
        return {
            "title": data["title"],
            "ready_in_minutes": data.get("readyInMinutes", "N/A"),
            "servings": data.get("servings", "N/A"),
            "instructions": instructions,
            "ingredients": [ing["original"] for ing in data.get("extendedIngredients", [])]
        }
    except Exception as e:
        logging.error(f"Recipe details error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# YouTube API Integration
@api_router.get("/youtube/search")
async def search_youtube(query: str, max_results: int = 5):
    """Search YouTube videos"""
    try:
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "key": YOUTUBE_API_KEY
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        if "error" in data:
            raise HTTPException(status_code=400, detail=data["error"]["message"])
        
        videos = []
        for item in data.get("items", []):
            videos.append({
                "video_id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"][:150] + "...",
                "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"],
                "channel": item["snippet"]["channelTitle"]
            })
        
        return {"videos": videos, "count": len(videos)}
    except Exception as e:
        logging.error(f"YouTube search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Mood Tracking
class MoodEntry(BaseModel):
    user_id: str
    mood: str  # happy, sad, anxious, calm, energetic, tired
    note: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

@api_router.post("/mood/log")
async def log_mood(entry: MoodEntry):
    """Log daily mood"""
    mood_data = entry.dict()
    result = await db.moods.insert_one(mood_data)
    mood_data['id'] = str(result.inserted_id)
    return {"message": "Mood logged successfully", "mood": mood_data}

@api_router.get("/mood/history/{user_id}")
async def get_mood_history(user_id: str, days: int = 7):
    """Get mood history"""
    from_date = datetime.utcnow() - timedelta(days=days)
    moods = await db.moods.find({
        "user_id": user_id,
        "timestamp": {"$gte": from_date}
    }).to_list(100)
    
    return {"moods": [serialize_doc(m) for m in moods], "days": days}

# Daily Affirmations (India-focused)
AFFIRMATIONS_HINDI_ENGLISH = [
    "You are strong and capable. आप मजबूत और सक्षम हैं।",
    "Today will be a wonderful day. आज एक अद्भुत दिन होगा।",
    "Your family loves you deeply. आपका परिवार आपको बहुत प्यार करता है।",
    "You bring joy to others. आप दूसरों के लिए खुशी लाते हैं।",
    "Age is just a number, wisdom is forever. उम्र सिर्फ एक संख्या है, ज्ञान हमेशा के लिए है।",
    "You are blessed and loved. आप धन्य और प्रिय हैं।",
    "Every day is a new beginning. हर दिन एक नई शुरुआत है।",
    "Your health is improving. आपका स्वास्थ्य सुधर रहा है।",
    "You deserve happiness and peace. आप खुशी और शांति के योग्य हैं।",
    "You are precious to your family. आप अपने परिवार के लिए अनमोल हैं।"
]

@api_router.get("/enrichment/affirmation")
async def get_daily_affirmation():
    """Get random affirmation"""
    import random
    affirmation = random.choice(AFFIRMATIONS_HINDI_ENGLISH)
    return {"affirmation": affirmation}

# Jokes Database (India-focused, family-friendly)
INDIAN_JOKES = [
    {"joke": "Why did the samosa go to school? To get a little butter! (batter!)", "type": "food"},
    {"joke": "What do you call a sleeping bull? A bulldozer!", "type": "animal"},
    {"joke": "Why did the cricket player go to the bank? To get his boundary!", "type": "cricket"},
    {"joke": "What's a computer's favorite snack? Microchips and data!", "type": "tech"},
    {"joke": "Why don't secrets work in India? Because chai and gossip travel faster than internet!", "type": "culture"},
    {"joke": "What did the chapati say to the dal? Without you, life is so dry!", "type": "food"},
    {"joke": "Why was the math book sad? It had too many problems!", "type": "general"},
    {"joke": "What do you call a funny mountain? Hill-arious!", "type": "general"},
    {"joke": "Why did the bicycle fall over? It was two-tired!", "type": "general"},
    {"joke": "What do clouds wear under their clothes? Thunderwear!", "type": "weather"}
]

@api_router.get("/enrichment/joke")
async def get_joke():
    """Get random joke"""
    import random
    joke = random.choice(INDIAN_JOKES)
    return joke

# Trivia Database (India-focused)
INDIAN_TRIVIA = [
    {
        "question": "Which Indian city is known as the Pink City?",
        "options": ["Jaipur", "Udaipur", "Jodhpur", "Agra"],
        "answer": "Jaipur",
        "category": "geography"
    },
    {
        "question": "Who is known as the Father of the Nation in India?",
        "options": ["Jawaharlal Nehru", "Mahatma Gandhi", "Sardar Patel", "Subhash Chandra Bose"],
        "answer": "Mahatma Gandhi",
        "category": "history"
    },
    {
        "question": "What is India's national flower?",
        "options": ["Rose", "Lotus", "Jasmine", "Marigold"],
        "answer": "Lotus",
        "category": "general"
    },
    {
        "question": "In which year did India gain independence?",
        "options": ["1942", "1945", "1947", "1950"],
        "answer": "1947",
        "category": "history"
    },
    {
        "question": "Which is the longest river in India?",
        "options": ["Yamuna", "Brahmaputra", "Ganga", "Godavari"],
        "answer": "Ganga",
        "category": "geography"
    },
    {
        "question": "Who was the first Prime Minister of India?",
        "options": ["Dr. Rajendra Prasad", "Jawaharlal Nehru", "Indira Gandhi", "Lal Bahadur Shastri"],
        "answer": "Jawaharlal Nehru",
        "category": "history"
    },
    {
        "question": "What is the capital of India?",
        "options": ["Mumbai", "Kolkata", "New Delhi", "Chennai"],
        "answer": "New Delhi",
        "category": "geography"
    },
    {
        "question": "Which festival is known as the festival of lights?",
        "options": ["Holi", "Diwali", "Dussehra", "Eid"],
        "answer": "Diwali",
        "category": "culture"
    }
]

@api_router.get("/enrichment/trivia")
async def get_trivia(category: str = "all"):
    """Get random trivia question"""
    import random
    if category == "all":
        questions = INDIAN_TRIVIA
    else:
        questions = [q for q in INDIAN_TRIVIA if q["category"] == category]
    
    if not questions:
        questions = INDIAN_TRIVIA
    
    question = random.choice(questions)
    return question

@api_router.post("/enrichment/trivia/answer")
async def check_trivia_answer(user_answer: str, correct_answer: str):
    """Check if trivia answer is correct"""
    is_correct = user_answer.lower().strip() == correct_answer.lower().strip()
    if is_correct:
        responses = [
            "Shabash! Correct answer! शाबाश!",
            "Excellent! You're so smart! बहुत अच्छा!",
            "Perfect! That's right! बिल्कुल सही!",
            "Wonderful! You got it! कमाल है!"
        ]
    else:
        responses = [
            f"Close! The correct answer is {correct_answer}. No worries, you'll get the next one!",
            f"Not quite! It's {correct_answer}. Keep trying, you're doing great!",
            f"Almost! The answer is {correct_answer}. Practice makes perfect!"
        ]
    
    import random
    return {"correct": is_correct, "message": random.choice(responses)}

# Gratitude Journal
class GratitudeEntry(BaseModel):
    user_id: str
    gratitude_text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

@api_router.post("/enrichment/gratitude")
async def log_gratitude(entry: GratitudeEntry):
    """Log gratitude entry"""
    gratitude_data = entry.dict()
    result = await db.gratitude.insert_one(gratitude_data)
    gratitude_data['id'] = str(result.inserted_id)
    
    responses = [
        "Thank you for sharing. Gratitude brings peace. धन्यवाद।",
        "Beautiful! Being grateful makes us happy. बहुत अच्छा!",
        "Wonderful! Count your blessings every day. शानदार!"
    ]
    
    import random
    return {"message": random.choice(responses), "entry": gratitude_data}

@api_router.get("/enrichment/gratitude/{user_id}")
async def get_gratitude_history(user_id: str, days: int = 30):
    """Get gratitude history"""
    from_date = datetime.utcnow() - timedelta(days=days)
    entries = await db.gratitude.find({
        "user_id": user_id,
        "timestamp": {"$gte": from_date}
    }).sort("timestamp", -1).to_list(100)
    
    return {"entries": [serialize_doc(e) for e in entries]}

# Inspirational Quotes (India-focused)
INSPIRATIONAL_QUOTES = [
    {"quote": "Arise, awake and stop not till the goal is reached.", "author": "Swami Vivekananda"},
    {"quote": "The best time to plant a tree was 20 years ago. The second best time is now.", "author": "Ancient Indian Proverb"},
    {"quote": "You must be the change you wish to see in the world.", "author": "Mahatma Gandhi"},
    {"quote": "In a gentle way, you can shake the world.", "author": "Mahatma Gandhi"},
    {"quote": "The mind is everything. What you think, you become.", "author": "Buddha"},
    {"quote": "Health is the greatest gift, contentment the greatest wealth.", "author": "Buddha"},
    {"quote": "Yesterday is history, tomorrow is mystery, today is a gift.", "author": "Ancient Wisdom"},
    {"quote": "A journey of a thousand miles begins with a single step.", "author": "Lao Tzu"},
    {"quote": "The soul is neither born nor does it ever die.", "author": "Bhagavad Gita"},
    {"quote": "Where there is love, there is life.", "author": "Mahatma Gandhi"}
]

@api_router.get("/enrichment/quote")
async def get_inspirational_quote():
    """Get random inspirational quote"""
    import random
    quote = random.choice(INSPIRATIONAL_QUOTES)
    return quote

# Breathing Exercises
BREATHING_EXERCISES = [
    {
        "name": "Simple Deep Breathing",
        "name_hindi": "सरल गहरी सांस",
        "steps": [
            "Sit comfortably with your back straight",
            "Close your eyes gently",
            "Breathe in slowly through your nose for 4 counts",
            "Hold for 2 counts",
            "Breathe out slowly through your mouth for 6 counts",
            "Repeat 5 times"
        ],
        "duration": "2 minutes",
        "benefits": "Reduces stress and anxiety"
    },
    {
        "name": "Alternate Nostril Breathing (Anulom Vilom)",
        "name_hindi": "अनुलोम विलोम प्राणायाम",
        "steps": [
            "Sit in a comfortable position",
            "Close right nostril with thumb",
            "Breathe in through left nostril",
            "Close left nostril, open right nostril",
            "Breathe out through right nostril",
            "Breathe in through right nostril",
            "Switch and breathe out through left",
            "Repeat 10 times"
        ],
        "duration": "5 minutes",
        "benefits": "Balances mind and body, improves concentration"
    },
    {
        "name": "Belly Breathing",
        "name_hindi": "पेट की सांस",
        "steps": [
            "Lie down or sit comfortably",
            "Place one hand on belly, one on chest",
            "Breathe deeply so your belly rises",
            "Chest should stay still",
            "Breathe out slowly",
            "Repeat 10 times"
        ],
        "duration": "3 minutes",
        "benefits": "Calms nervous system, helps sleep"
    }
]

@api_router.get("/enrichment/breathing")
async def get_breathing_exercise():
    """Get breathing exercise"""
    import random
    exercise = random.choice(BREATHING_EXERCISES)
    return exercise

# Birthday Tracker
class Birthday(BaseModel):
    user_id: str
    person_name: str
    relation: str
    birth_date: str  # MM-DD format
    phone: Optional[str] = None

@api_router.post("/enrichment/birthday")
async def add_birthday(birthday: Birthday):
    """Add birthday to tracker"""
    birthday_data = birthday.dict()
    birthday_data['created_at'] = datetime.utcnow()
    result = await db.birthdays.insert_one(birthday_data)
    birthday_data['id'] = str(result.inserted_id)
    return {"message": "Birthday added successfully", "birthday": birthday_data}

@api_router.get("/enrichment/birthdays/{user_id}")
async def get_upcoming_birthdays(user_id: str, days: int = 30):
    """Get upcoming birthdays"""
    birthdays = await db.birthdays.find({"user_id": user_id}).to_list(100)
    
    # Check which birthdays are coming up
    today = datetime.utcnow()
    upcoming = []
    
    for bday in birthdays:
        try:
            month, day = map(int, bday['birth_date'].split('-'))
            this_year = today.year
            bday_this_year = datetime(this_year, month, day)
            
            # If birthday passed, check next year
            if bday_this_year < today:
                bday_this_year = datetime(this_year + 1, month, day)
            
            days_until = (bday_this_year - today).days
            
            if 0 <= days_until <= days:
                bday_copy = serialize_doc(bday)
                bday_copy['days_until'] = days_until
                upcoming.append(bday_copy)
        except:
            continue
    
    # Sort by days until
    upcoming.sort(key=lambda x: x['days_until'])
    
    return {"upcoming_birthdays": upcoming, "count": len(upcoming)}

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
