# 🔗 Saathi Integration Guide

## Overview
Saathi is built with a flexible architecture that allows seamless integration with external APIs, n8n workflows, and AI agents. This guide will help you extend Saathi's capabilities.

---

## 📋 Table of Contents
1. [Current Architecture](#current-architecture)
2. [Adding External APIs](#adding-external-apis)
3. [n8n Integration](#n8n-integration)
4. [AI Agent Integration](#ai-agent-integration)
5. [Webhook Setup](#webhook-setup)
6. [Database Schema](#database-schema)

---

## 🏗️ Current Architecture

### Backend Stack
- **Framework**: FastAPI (Python)
- **Database**: MongoDB
- **AI**: OpenAI GPT-5.2 via Emergent LLM Key
- **Port**: 8001
- **Base URL**: `http://localhost:8001/api`

### Frontend Stack
- **Framework**: React Native (Expo)
- **State Management**: AsyncStorage + React State
- **Voice**: Expo Speech API
- **Notifications**: Expo Notifications
- **Port**: 3000

### Existing API Endpoints
```
POST   /api/chat                    # AI conversation
GET    /api/reminders              # Get reminders
POST   /api/reminders              # Create reminder
PATCH  /api/reminders/{id}         # Update reminder
DELETE /api/reminders/{id}         # Delete reminder
POST   /api/reminders/{id}/snooze  # Snooze reminder
GET    /api/users                  # Get users
POST   /api/users                  # Create user
GET    /api/conversations/{user_id}# Get chat history
```

---

## 🔌 Adding External APIs

### Step 1: Add External API Endpoint

**Example: Weather API Integration**

1. Add endpoint to `/app/backend/server.py`:

```python
import requests

@api_router.get("/weather")
async def get_weather(city: str = "London"):
    try:
        # Replace with your weather API
        api_key = os.environ.get('WEATHER_API_KEY')
        url = f"https://api.weatherapi.com/v1/current.json?key={api_key}&q={city}"
        response = requests.get(url)
        data = response.json()
        
        return {
            "city": city,
            "temperature": data["current"]["temp_c"],
            "condition": data["current"]["condition"]["text"],
            "humidity": data["current"]["humidity"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

2. Add API key to `/app/backend/.env`:
```
WEATHER_API_KEY=your_api_key_here
```

3. Update AI system message to use weather:
```python
# In /app/backend/server.py, update the system_message
"When user asks about weather, respond with: WEATHER_QUERY:{city}"
```

4. Handle weather query in frontend:
```typescript
// In /app/frontend/app/index.tsx
if (aiResponse.startsWith('WEATHER_QUERY:')) {
  const city = aiResponse.split(':')[1];
  const weather = await fetch(`${API_URL}/api/weather?city=${city}`);
  const data = await weather.json();
  speak(`The weather in ${city} is ${data.condition} with ${data.temperature} degrees`);
}
```

### Step 2: Generic API Integration Pattern

```python
# /app/backend/server.py
class ExternalAPICall(BaseModel):
    service: str
    endpoint: str
    method: str
    data: dict = {}

@api_router.post("/external/call")
async def call_external_api(api_call: ExternalAPICall):
    """Generic endpoint for calling external APIs"""
    try:
        api_key = os.environ.get(f'{api_call.service.upper()}_API_KEY')
        headers = {"Authorization": f"Bearer {api_key}"}
        
        if api_call.method == "GET":
            response = requests.get(api_call.endpoint, headers=headers)
        elif api_call.method == "POST":
            response = requests.post(api_call.endpoint, json=api_call.data, headers=headers)
        
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 🤖 n8n Integration

### Architecture Options

#### Option 1: n8n calls Saathi (Recommended)
```
n8n Workflow → HTTP Request → Saathi API
```

#### Option 2: Saathi calls n8n
```
Saathi → Webhook → n8n Workflow
```

### Setup Guide

#### 1. n8n Webhook Endpoint

**Create n8n workflow:**
1. Add "Webhook" node
2. Set Method: POST
3. Get webhook URL: `https://your-n8n-instance.com/webhook/saathi`

**In Saathi backend:**
```python
import requests

@api_router.post("/trigger/n8n")
async def trigger_n8n_workflow(workflow_data: dict):
    """Trigger n8n workflow"""
    n8n_webhook_url = os.environ.get('N8N_WEBHOOK_URL')
    
    try:
        response = requests.post(n8n_webhook_url, json=workflow_data)
        return {
            "status": "triggered",
            "response": response.json()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Add to `.env`:**
```
N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/saathi
```

#### 2. Bi-directional Communication

**n8n → Saathi (Create reminder from external source):**
```javascript
// n8n HTTP Request Node
{
  "method": "POST",
  "url": "{{$env.SAATHI_API_URL}}/api/reminders",
  "body": {
    "type": "appointment",
    "title": "Doctor appointment from calendar",
    "time": "14:00",
    "user_id": "parent_1"
  }
}
```

**Saathi → n8n (Send activity logs):**
```python
# When parent completes a task
@api_router.post("/log/activity")
async def log_activity(activity: dict):
    # Log to database
    await db.activity_logs.insert_one(activity)
    
    # Send to n8n for processing
    await trigger_n8n_workflow({
        "event": "activity_completed",
        "data": activity
    })
    
    return {"status": "logged"}
```

### Common n8n Use Cases

1. **Calendar Sync**: Sync Google Calendar events as reminders
2. **Family Notifications**: Send SMS to family when parent misses medicine
3. **Health Tracking**: Log medicine intake to Google Sheets
4. **Smart Home**: Trigger lights/alarms based on reminders

---

## 🤖 AI Agent Integration

### Architecture

```
Saathi GPT-5.2 → Agent Router → Specialized Agents
```

### Implementation

#### 1. Agent Router Pattern

```python
# /app/backend/server.py

class AgentRouter:
    def __init__(self):
        self.agents = {
            "health": HealthAgent(),
            "cooking": CookingAgent(),
            "meditation": MeditationAgent()
        }
    
    async def route(self, message: str, context: dict):
        # Determine which agent to use
        if "medicine" in message or "health" in message:
            return await self.agents["health"].process(message, context)
        elif "cook" in message or "recipe" in message:
            return await self.agents["cooking"].process(message, context)
        # ... more routing logic
        else:
            # Default to main Saathi AI
            return await self.default_response(message, context)

agent_router = AgentRouter()

@api_router.post("/chat/routed")
async def routed_chat(message: ChatMessage):
    response = await agent_router.route(message.message, {"user_id": message.user_id})
    return {"response": response}
```

#### 2. Specialized Agent Example

```python
class HealthAgent:
    def __init__(self):
        self.llm = LlmChat(
            api_key=os.environ['EMERGENT_LLM_KEY'],
            session_id="health_agent",
            system_message="""You are a health advisor for elderly parents.
            Provide simple, safe health tips. Always recommend consulting doctors."""
        ).with_model("openai", "gpt-5.2")
    
    async def process(self, message: str, context: dict):
        # Get user health history
        user_data = await db.users.find_one({"_id": context["user_id"]})
        
        # Add context to message
        enriched_message = f"User health data: {user_data.get('health_notes', 'None')}. Question: {message}"
        
        response = await self.llm.send_message(UserMessage(text=enriched_message))
        return response
```

#### 3. Multi-Agent Collaboration

```python
class AgentCollaboration:
    async def handle_complex_query(self, message: str):
        # Step 1: Planning agent decides steps
        plan = await planning_agent.create_plan(message)
        
        # Step 2: Execute with specialized agents
        results = []
        for step in plan['steps']:
            agent = self.get_agent(step['agent_type'])
            result = await agent.execute(step['action'])
            results.append(result)
        
        # Step 3: Synthesis agent combines results
        final_response = await synthesis_agent.combine(results)
        return final_response
```

---

## 🔗 Webhook Setup

### Receiving Webhooks

```python
# /app/backend/server.py

@api_router.post("/webhooks/{service}")
async def receive_webhook(service: str, payload: dict):
    """Generic webhook receiver"""
    
    if service == "calendar":
        # Handle calendar events
        await handle_calendar_event(payload)
    elif service == "iot":
        # Handle IoT device events
        await handle_iot_event(payload)
    elif service == "health_monitor":
        # Handle health device data
        await handle_health_data(payload)
    
    return {"status": "received"}

async def handle_calendar_event(event: dict):
    """Create reminder from calendar event"""
    reminder = {
        "type": "appointment",
        "title": event["summary"],
        "time": event["start_time"],
        "user_id": event["user_id"]
    }
    await db.reminders.insert_one(reminder)
```

### Sending Webhooks

```python
@api_router.post("/webhooks/send")
async def send_webhook(webhook_url: str, data: dict):
    """Send data to external webhook"""
    try:
        response = requests.post(
            webhook_url,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        return {"status": "sent", "response": response.status_code}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## 💾 Database Schema

### Current Collections

```javascript
// users
{
  _id: ObjectId,
  name: String,
  emergency_contacts: [{name: String, phone: String}],
  created_at: DateTime
}

// reminders
{
  _id: ObjectId,
  user_id: String,
  type: String,  // "medicine", "walk", "call", "exercise", etc.
  title: String,
  time: String,  // "HH:MM"
  enabled: Boolean,
  snoozed_until: DateTime,
  created_at: DateTime
}

// conversations
{
  _id: ObjectId,
  user_id: String,
  messages: [{
    role: String,  // "user" or "assistant"
    content: String,
    timestamp: DateTime
  }],
  created_at: DateTime,
  updated_at: DateTime
}
```

### Extending Schema for Integrations

```javascript
// activity_logs (for n8n/analytics)
{
  _id: ObjectId,
  user_id: String,
  activity_type: String,  // "medicine_taken", "exercise_completed", etc.
  timestamp: DateTime,
  metadata: Object
}

// external_services (for API tokens)
{
  _id: ObjectId,
  user_id: String,
  service_name: String,
  api_token: String,  // Encrypted
  config: Object,
  created_at: DateTime
}

// agent_sessions (for AI agent tracking)
{
  _id: ObjectId,
  session_id: String,
  agent_type: String,
  conversation_history: Array,
  created_at: DateTime
}
```

---

## 🚀 Quick Integration Examples

### 1. Add SMS Notifications (Twilio)

```python
from twilio.rest import Client

@api_router.post("/notify/sms")
async def send_sms(phone: str, message: str):
    client = Client(
        os.environ['TWILIO_ACCOUNT_SID'],
        os.environ['TWILIO_AUTH_TOKEN']
    )
    
    client.messages.create(
        to=phone,
        from_=os.environ['TWILIO_PHONE_NUMBER'],
        body=message
    )
    return {"status": "sent"}
```

### 2. Add Email Notifications (SendGrid)

```python
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

@api_router.post("/notify/email")
async def send_email(to: str, subject: str, body: str):
    message = Mail(
        from_email='saathi@yourdomain.com',
        to_emails=to,
        subject=subject,
        html_content=body
    )
    
    sg = SendGridAPIClient(os.environ['SENDGRID_API_KEY'])
    sg.send(message)
    return {"status": "sent"}
```

### 3. Add IoT Integration (Smart Home)

```python
@api_router.post("/iot/trigger")
async def trigger_iot_device(device_id: str, action: str):
    """Trigger smart home devices"""
    iot_api_url = os.environ['IOT_API_URL']
    
    response = requests.post(
        f"{iot_api_url}/devices/{device_id}/actions",
        json={"action": action},
        headers={"Authorization": f"Bearer {os.environ['IOT_API_KEY']}"}
    )
    
    return response.json()
```

---

## 🛡️ Security Best Practices

1. **Environment Variables**: Store ALL API keys in `.env`
2. **Encryption**: Encrypt sensitive user data in MongoDB
3. **Rate Limiting**: Add rate limits to prevent abuse
4. **Authentication**: Add API key authentication for webhooks
5. **Validation**: Validate all external API responses

---

## 📞 Next Steps

When you're ready to integrate:

1. **Share your API documentation** - I'll help create the integration
2. **Provide webhook URLs** - For n8n or other services
3. **Describe the agent behavior** - What specialized agents you need
4. **Test endpoints** - I'll help test integrations thoroughly

Let me know which integration you'd like to start with!
