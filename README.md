# eBay Draft Commander Pro

A complete solution for automating eBay listing creation using AI-powered image analysis and the eBay Inventory API.

## Features

- 🤖 **AI Image Analysis** - Uses Google Gemini to extract product details from photos
- 🔑 **OAuth Authentication** - Secure eBay API access with user authorization
- 📦 **Inventory API Integration** - Creates listings via the modern eBay REST API
- 🖼️ **Image Upload** - Uploads photos via the Media API
- 📋 **Category & Aspects** - Auto-detects categories and fills required item specifics

## Architecture (2026 Modern Approach)

```
eBay_Inbox/             → Drop product photos here
    └── item_folder/    → Each item in its own folder
        └── *.jpg       → Product images

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

### Batch Processing
```bash
python draft_commander.py
```
This opens the GUI for batch processing items from your eBay_Inbox folder.

## Files

| File | Purpose |
|------|---------|
| `ebay_auth.py` | OAuth user authorization |
| `ebay_api.py` | eBay API client (Taxonomy, token) |
| `ebay_complete.py` | Complete listing creator |
| `ai_analyzer.py` | Gemini-powered image analysis |
| `draft_commander.py` | GUI application |
| `bookmarklet.js` | Browser form filler |

## API Documentation

This project uses the following eBay APIs:
- **Inventory API** - Create/manage inventory items and offers
- **Taxonomy API** - Get categories and item specifics
- **Media API** - Upload images to eBay Picture Services

## License

MIT
