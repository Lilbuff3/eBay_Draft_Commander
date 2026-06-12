# eBay Draft Commander Pro

A complete solution for automating eBay listing creation using AI-powered image analysis and the eBay Inventory API.

## Features

📘 **[Read the User Manual](USER_MANUAL.md)** for installation and usage instructions.

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

```text
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

```text
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

   ```env
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
python backend/wsgi.py        # or double-click launch_app.bat
```

Then open your browser to `http://localhost:5000/app`

### Phone Access

**Same Wi-Fi (works now):** open `http://<PC-LAN-IP>:5000/app` on the phone
(find the IP with `ipconfig` → IPv4 Address). Plain HTTP means no service
worker: the app works fully, but no offline cache and no real PWA install.
"Add to Home Screen" still gives a launcher icon.

**Anywhere + HTTPS + installable PWA (recommended):** install
[Tailscale](https://tailscale.com) on PC and phone (same account), then:

```powershell
tailscale serve --bg 5000
```

Open the printed `https://<pc-name>.<tailnet>.ts.net` URL on the phone.
HTTPS unlocks the service worker → offline support and full PWA install,
and the app works away from home over cell data. Traffic stays on your
private tailnet — the server is never exposed to the internet.

**Start server automatically at logon:** create
`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\start-draft-commander.bat`:

```bat
@echo off
cd /d "C:\Users\adam\Projects\ebay-draft-commander"
start "eBay Draft Commander Server" /min cmd /c "python backend\wsgi.py"
```

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
| :--- | :--- |
| `backend/` | **New** Modular Flask Application (App Factory, Blueprints, Services) |
| `backend/wsgi.py` | Production entry point for the web server |
| `web_server.py` | Legacy shim for `draft_commander.py` compatibility |
| `ebay_auth.py` | OAuth user authorization |
| `ai_analyzer.py` | Gemini 3 image analysis |
| `pricing_engine.py` | AI pricing with Google Search grounding |
| `queue_manager.py` | Job queue with persistence (Shared Core) |
| `create_from_folder.py` | Main listing creation logic (Shared Core) |
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
