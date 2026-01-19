# eBay Draft Commander Pro

A complete solution for automating eBay listing creation using AI-powered image analysis and the eBay Inventory API.

## Features

- 🤖 **AI Image Analysis** - Uses Google Gemini to extract product details from photos
- 🔑 **OAuth Authentication** - Secure eBay API access with user authorization
- 📦 **Inventory API Integration** - Creates listings via the modern eBay REST API
- 🖼️ **Image Upload** - Uploads photos via the Media API
- 📋 **Category & Aspects** - Auto-detects categories and fills required item specifics
- 🎨 **Modern Web Dashboard** - React 19 + Vite + Tailwind CSS interface
- 📱 **Mobile-Friendly** - Responsive design accessible from any device
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
- Inventory            - Google Gemini
- Media Upload         - Image Recognition
- Fulfillment          - Price Estimation
- Orders
```

**Workflow:**
```
eBay_Inbox/             → Drop product photos here
    └── item_folder/    → Each item in its own folder
        └── *.jpg       → Product images
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
   pip install requests google-generativeai
   ```

2. **Configure credentials:**
   Create a `.env` file with your eBay API credentials:
   ```
   EBAY_APP_ID=your-app-id
   EBAY_CERT_ID=your-cert-id
   EBAY_RU_NAME=your-runame
   ```

3. **Authorize eBay access:**
   ```bash
   python ebay_auth.py
   ```
   Follow the prompts to authorize the app to access your eBay account.

## Usage

### Quick Single Listing
```python
from ebay_complete import create_ebay_listing

listing_id = create_ebay_listing(
    title="Product Title Here",
    description="Product description...",
    price="29.99",
    image_urls=["https://your-image-url.jpg"],
    item_specifics={
        'Brand': 'YourBrand',
        'Model': 'YourModel'
    }
)
```

### Web Dashboard (Recommended)
```bash
python web_server.py
```
Then open your browser to `http://localhost:5000/app`

**Features:**
- Queue management and monitoring
- Active listings editor (bulk price/title updates)
- Sales analytics dashboard  
- Photo editor with adjustments
- Price research tool
- Template manager
- Mobile-friendly interface

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
| `ebay_api.py` | eBay API client (Taxonomy, token) |
| `ai_analyzer.py` | Gemini-powered image analysis |
| `queue_manager.py` | Job queue with persistence |
| `create_from_folder.py` | Main listing creation logic |
| `frontend/` | React + Vite web app |
| `draft_commander.py` | Legacy Tkinter GUI |

## API Documentation

This project uses the following eBay APIs:
- **Inventory API** - Create/manage inventory items and offers
- **Taxonomy API** - Get categories and item specifics
- **Media API** - Upload images to eBay Picture Services

## License

MIT
