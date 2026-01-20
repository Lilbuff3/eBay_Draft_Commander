# eBay Draft Commander Pro

A complete solution for automating eBay listing creation using AI-powered image analysis and the eBay Inventory API.

## Features

- 🤖 **AI Image Analysis** - Uses Google Gemini 3 (Fast & Accurate) to extract details
- 📱 **Mobile PWA** - Installable on iOS/Android for native-like experience
- 📥 **Bulk Inbox Scan** - Drop folders -> Scan -> Queue multiple items instantly
- 🔑 **OAuth Authentication** - Secure eBay API access with user authorization
- 📦 **Inventory API Integration** - Creates listings via the modern eBay REST API
- 🖼️ **Image Upload** - Uploads photos via the Media API
- 📋 **Category & Aspects** - Auto-detects categories and fills required item specifics
- 🎨 **Modern Web Dashboard** - React 19 + Vite + Tailwind CSS interface
- 📊 **Analytics** - Track sales, revenue, and inventory performance

## Architecture (2026 Modern Approach)

```
┌─────────────────┐
│  React Frontend │ ← Vite + TypeScript + Tailwind CSS
│  (Port 5000/app)│ 
└────────┬────────┘
         │ REST API
         ↓
┌─────────────────┐
│  Flask Backend  │ ← Python + eBay APIs + Google Gemini
│  (Port 5000)    │
└────────┬────────┘
         │
    ┌────┴─────────────────┐
    ↓                      ↓
eBay APIs              AI Analysis
- Inventory            - Google Gemini 3
- Media Upload         - Image Recognition
- Fulfillment          - Price Estimation (G-Search Grounding)
- Orders
```

**Workflow:**
```
eBay_Inbox/             → Drop multiple folders here
    ├── shoe_folder/    → Images for item 1
    └── camera_folder/  → Images for item 2
         ↓
"Scan Inbox" (UI)       → Auto-queues all folders
         ↓
AI Analyzer             → Extracts title, description, specs from images
         ↓
Media API               → Uploads images to eBay Picture Services
         ↓
Inventory API           → Creates inventory items + offers
         ↓
Publish                 → Creates live eBay listing
```

## Setup

1. **Install dependencies:**
   ```bash
   pip install requests google-generativeai flask
   ```

2. **Configure credentials:**
   Create a `.env` file with your eBay API credentials:
   ```
   EBAY_APP_ID=your-app-id
   EBAY_CERT_ID=your-cert-id
   EBAY_RU_NAME=your-runame
   GOOGLE_API_KEY=your-gemini-key
   ```

3. **Authorize eBay access:**
   ```bash
   python ebay_auth.py
   ```
   Follow the prompts to authorize the app to access your eBay account.

## Usage

### Web Dashboard & Mobile App (Recommended)
```bash
python web_server.py
```
Then open your browser to `http://localhost:5000/app`

**Mobile Access:**  
Scan the QR code printed in the terminal to access on your phone.  
**To Install:** Tap "Share" -> "Add to Home Screen" (iOS) or "Install App" (Android).

**Features:**
- **Bulk Inbox Scanning:** Process multiple items at once
- **Queue Management:** Monitor AI analysis progress
- **Active Listings:** Bulk price/title updates
- **Analytics:** Sales & revenue tracking
- **Photo Editor:** Adjust brightness/contrast/crop
- **Price Research:** AI-powered estimates with Google Search grounding
- **Templates:** Save/load listing presets

### Build Frontend (Development)
```bash
cd frontend
npm install
npm run build   # Builds to ../static/app
```

### Legacy Desktop GUI
```bash
python draft_commander.py
```
Opens Tkinter-based GUI for batch processing (legacy interface).

## Files

| File | Purpose |
|------|---------|
| `web_server.py` | Flask API server + serves frontend |
| `ebay_auth.py` | OAuth user authorization |
| `ai_analyzer.py` | Gemini 3 image analysis |
| `pricing_engine.py`| AI pricing with Google Search grounding |
| `queue_manager.py` | Job queue with persistence |
| `create_from_folder.py` | Main listing creation logic |
| `frontend/` | React + Vite web app (PWA) |
| `draft_commander.py` | Legacy Tkinter GUI |

## API Documentation

This project uses the following eBay APIs:
- **Inventory API** - Create/manage inventory items and offers
- **Taxonomy API** - Get categories and item specifics
- **Media API** - Upload images to eBay Picture Services
- **Browse API** - Search for similar items (Pricing)

## License

MIT
