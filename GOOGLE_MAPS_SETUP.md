# 🗺️ Google Maps Integration for Saathi

## ✅ Status: Backend Integrated, API Key Needs Configuration

Your Google Maps API key has been added to Saathi! However, it needs to be enabled for specific APIs in Google Cloud Console.

---

## 🔧 Setup Required (One-Time)

### Step 1: Enable Required APIs

Go to [Google Cloud Console](https://console.cloud.google.com/) and enable these APIs:

1. **Places API** (for finding nearby hospitals, pharmacies)
2. **Directions API** (for navigation)
3. **Geocoding API** (for address lookup)

**How to Enable:**
1. Go to https://console.cloud.google.com/apis/library
2. Search for "Places API" → Click → Enable
3. Search for "Directions API" → Click → Enable  
4. Search for "Geocoding API" → Click → Enable

### Step 2: Verify API Key Restrictions (Optional but Recommended)

1. Go to https://console.cloud.google.com/apis/credentials
2. Click on your API key
3. Under "API restrictions", select "Restrict key"
4. Choose:
   - Places API
   - Directions API
   - Geocoding API

---

## 🎯 Features Implemented

### 1. Find Nearby Places
**Endpoint:** `GET /api/maps/nearby`

**Parameters:**
- `lat` (float): Latitude
- `lng` (float): Longitude
- `type` (string): "hospital", "pharmacy", "doctor"
- `radius` (int): Search radius in meters (default: 5000)

**Example:**
```bash
curl "http://localhost:8001/api/maps/nearby?lat=40.7128&lng=-74.0060&type=hospital&radius=5000"
```

**Response:**
```json
{
  "places": [
    {
      "name": "New York-Presbyterian Hospital",
      "address": "525 E 68th St, New York",
      "rating": 4.2,
      "open_now": true,
      "lat": 40.7649,
      "lng": -73.9540
    }
  ],
  "count": 5
}
```

### 2. Get Walking Directions
**Endpoint:** `GET /api/maps/directions`

**Parameters:**
- `origin_lat` (float): Starting latitude
- `origin_lng` (float): Starting longitude
- `dest_lat` (float): Destination latitude
- `dest_lng` (float): Destination longitude

**Example:**
```bash
curl "http://localhost:8001/api/maps/directions?origin_lat=40.7128&origin_lng=-74.0060&dest_lat=40.7580&dest_lng=-73.9855"
```

**Response:**
```json
{
  "total_distance": "5.2 km",
  "total_duration": "1 hour 4 mins",
  "steps": [
    {
      "instruction": "Head north on Broadway toward W 3rd St",
      "distance": "0.2 km",
      "duration": "3 mins"
    }
  ]
}
```

### 3. Geocode Address
**Endpoint:** `GET /api/maps/geocode`

**Parameters:**
- `address` (string): Full address to convert

**Example:**
```bash
curl "http://localhost:8001/api/maps/geocode?address=Times+Square+New+York"
```

**Response:**
```json
{
  "lat": 40.7580,
  "lng": -73.9855,
  "formatted_address": "Times Square, Manhattan, NY 10036, USA"
}
```

---

## 🎙️ Voice Integration

### AI Voice Commands
Once APIs are enabled, parents can say:

- "Where is the nearest hospital?"
- "Find pharmacy near me"
- "Show me doctors nearby"
- "Where can I buy medicine?"

**AI Response Format:**
```
LOCATION_QUERY:hospital
LOCATION_QUERY:pharmacy
LOCATION_QUERY:doctor
```

### Frontend Handling (To Be Implemented)
```typescript
if (aiResponse.startsWith('LOCATION_QUERY:')) {
  const type = aiResponse.split(':')[1];
  // Get user's current location
  const location = await Location.getCurrentPositionAsync({});
  
  // Find nearby places
  const response = await fetch(
    `${API_URL}/api/maps/nearby?lat=${location.coords.latitude}&lng=${location.coords.longitude}&type=${type}`
  );
  
  const data = await response.json();
  
  // Speak the results
  const places = data.places.slice(0, 3);
  speak(`I found ${places.length} ${type}s near you. The closest is ${places[0].name} at ${places[0].address}`);
}
```

---

## 📱 Mobile Location Services

### Required Package
```bash
cd /app/frontend
yarn add expo-location
```

### Permission Setup (Already Added)
In `/app/frontend/app.json`:
```json
{
  "expo": {
    "ios": {
      "infoPlist": {
        "NSLocationWhenInUseUsageDescription": "Saathi needs your location to find nearby hospitals and pharmacies"
      }
    },
    "android": {
      "permissions": [
        "ACCESS_FINE_LOCATION",
        "ACCESS_COARSE_LOCATION"
      ]
    }
  }
}
```

---

## 🚀 Use Cases for Elderly Parents

### 1. Emergency Situations
**"Where is the nearest hospital?"**
- Gets current location
- Finds 5 closest hospitals
- Shows distance and directions
- One-tap to call hospital

### 2. Medication Needs
**"Find pharmacy near me"**
- Locates nearby pharmacies
- Shows which are open now
- Provides walking directions
- Can set reminder when arrived

### 3. Doctor Appointments
**"Navigate to Dr. Smith's office"**
- Converts address to coordinates
- Provides step-by-step walking directions
- Clear, large text instructions
- Voice guidance

### 4. Walk Tracking
**"Track my walk"**
- Records walking route
- Calculates distance covered
- Shows on map
- Saves to history

---

## 🔐 Security Notes

- ✅ API key stored in backend `.env` (secure)
- ✅ Never exposed to frontend
- ✅ All requests go through backend proxy
- ⚠️ Consider adding rate limiting for production

---

## 📊 Cost Estimate (Google Maps Pricing)

**Free Tier (Monthly):**
- Places API: $200 credit (≈ 40,000 requests)
- Directions API: $200 credit (≈ 40,000 requests)
- Geocoding API: $200 credit (≈ 40,000 requests)

**For Saathi Users:**
Assuming 10 location queries per user per month:
- 100 users = 1,000 requests/month = **FREE**
- 1,000 users = 10,000 requests/month = **FREE**
- 10,000 users = 100,000 requests/month = **~$25/month**

---

## 🧪 Testing Checklist

Once APIs are enabled:

1. **Test Nearby Places:**
```bash
curl "http://localhost:8001/api/maps/nearby?lat=40.7128&lng=-74.0060&type=hospital"
```

2. **Test Directions:**
```bash
curl "http://localhost:8001/api/maps/directions?origin_lat=40.7128&origin_lng=-74.0060&dest_lat=40.7580&dest_lng=-73.9855"
```

3. **Test Geocoding:**
```bash
curl "http://localhost:8001/api/maps/geocode?address=1600+Amphitheatre+Parkway+Mountain+View+CA"
```

4. **Test Voice Command:**
```bash
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Where is the nearest hospital?", "user_id": "test"}'
```
Expected response: `"LOCATION_QUERY:hospital"`

---

## 🎯 Next Steps

### Immediate (After Enabling APIs):
1. Enable the 3 APIs in Google Cloud Console
2. Test all endpoints
3. Implement frontend location handler
4. Add expo-location package
5. Test voice commands end-to-end

### Future Enhancements:
1. **Emergency Contact Location Sharing**
   - Send current location via SMS when SOS pressed
   
2. **Walk Route Tracking**
   - Save walking routes
   - Show distance/time statistics
   
3. **Appointment Reminders with Navigation**
   - "Time for doctor appointment" → Auto-start navigation
   
4. **Family Location Sharing**
   - Let family members see parent's location (with permission)

---

## 📝 Implementation Status

- ✅ Backend endpoints created
- ✅ API key configured
- ✅ AI voice command detection added
- ⚠️ APIs need to be enabled in Google Cloud Console
- ⏳ Frontend location handler (needs implementation)
- ⏳ expo-location package (needs installation)
- ⏳ UI for showing maps/places (needs implementation)

---

## 🆘 Troubleshooting

**Error: "REQUEST_DENIED"**
- Solution: Enable Places API, Directions API, Geocoding API in Google Cloud Console

**Error: "API key not valid"**
- Solution: Check API key in `/app/backend/.env`
- Verify key has correct APIs enabled

**Error: "ZERO_RESULTS"**
- Solution: Try different location coordinates
- Check if location has requested type of place nearby

**Error: "OVER_QUERY_LIMIT"**
- Solution: You've exceeded free tier
- Enable billing in Google Cloud Console

---

## 📞 Support

If you need help:
1. Verify API key is working in [Google Cloud Console](https://console.cloud.google.com/)
2. Check that all 3 APIs are enabled
3. Test with the curl commands above
4. Share any error messages for debugging

The foundation is ready - just enable the APIs and Saathi will have full location capabilities! 🗺️
