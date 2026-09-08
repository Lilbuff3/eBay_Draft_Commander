# eBay Draft Commander - Codebase Walkthrough

## Project Overview

eBay Draft Commander is a full-stack application that automates eBay listing creation using AI-powered image analysis. It processes product photos through Google Gemini Vision, generates listing details, uploads images to eBay, and creates inventory items with offers via the eBay Inventory API.

**Key Features:**
- AI-powered image analysis with Google Gemini 3
- Bulk inbox scanning with queue-based processing
- Real-time updates via WebSocket (Socket.IO)
- Mobile-first Progressive Web App (PWA)
- Template management for recurring listing patterns
- Price research and analytics
- Photo editing capabilities
- eBay OAuth integration

---

## Tech Stack

### Backend (Python)
- **Framework:** Flask 3.x with Application Factory pattern
- **Database:** SQLite with SQLAlchemy ORM
- **Real-time:** Flask-SocketIO (eventlet)
- **AI:** Google Generative AI (Gemini Vision)
- **APIs:** eBay REST APIs (Inventory, Media, Taxonomy, Browse, Analytics)
- **Auth:** eBay OAuth 2.0

### Frontend (React)
- **Framework:** React 18 + TypeScript
- **Build:** Vite 7
- **Styling:** Tailwind CSS 4
- **UI Components:** Radix UI primitives
- **State:** React hooks with Socket.IO for real-time sync
- **PWA:** vite-plugin-pwa with Workbox
- **Notifications:** Sonner (toast library)

### Desktop (Optional)
- **Electron:** Wraps the web app for native Windows/Mac distribution
- **Build:** electron-builder

---

## Architecture

### High-Level Data Flow

```
┌──────────────────────────────────────────────────────┐
│                   Frontend (React)                   │
│          Vite Dev Server / Built Static Files        │
│              (Port 5175 dev / 5000 prod)             │
└─────────────────────┬────────────────────────────────┘
                      │
                      │ HTTP REST + Socket.IO
                      ↓
┌──────────────────────────────────────────────────────┐
│              Backend (Flask + SocketIO)              │
│                  Port 5000 (wsgi.py)                 │
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │        Application Factory (__init__.py)     │  │
│  │  - Creates Flask app                         │  │
│  │  - Registers blueprints (ui, api)            │  │
│  │  │  - Initializes SocketIO                    │  │
│  │  - Injects QueueManager singleton            │  │
│  └──────────────┬───────────────────────────────┘  │
│                 │                                    │
│  ┌──────────────┴───────────────────────────────┐  │
│  │         Blueprints (URL Routing)             │  │
│  │  - ui_bp: Serves frontend static files       │  │
│  │  - api_bp: REST endpoints (/api/*)           │  │
│  └──────────────┬───────────────────────────────┘  │
│                 │                                    │
│  ┌──────────────┴───────────────────────────────┐  │
│  │          Services (Business Logic)           │  │
│  │  - QueueManager: Job queue + processing      │  │
│  │  - ProcessorService: Main listing workflow   │  │
│  │  - AIAnalyzer: Gemini Vision integration     │  │
│  │  - PricingEngine: AI price estimation        │  │
│  │  - eBay services (auth, inventory, media)    │  │
│  │  - TemplateManager: Save/load listing data   │  │
│  └──────────────┬───────────────────────────────┘  │
│                 │                                    │
│  ┌──────────────┴───────────────────────────────┐  │
│  │      Database (SQLite + SQLAlchemy)          │  │
│  │  - JobModel: Queue job state                 │  │
│  │  - TemplateModel: Saved listing templates    │  │
│  └──────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
                      │
                      │ External APIs
                      ↓
         ┌────────────────────────┐
         │    eBay REST APIs      │
         │  - Inventory API       │
         │  - Media API           │
         │  - Taxonomy API        │
         │  - Browse API          │
         │  - Analytics API       │
         └────────────────────────┘
                      │
         ┌────────────┴───────────┐
         │  Google Gemini API     │
         │  - Image Analysis      │
         │  - Price Research      │
         └────────────────────────┘
```

### Request Flow Example: Creating a Listing

1. **User uploads photos** → Frontend (`QuickListingForm.tsx`)
2. **POST /api/upload** → Backend API blueprint ([api.py:29](backend/app/blueprints/api.py#L29))
3. **Creates job folder** in `inbox/` directory
4. **QueueManager.add_folder()** → Adds job to database ([queue_manager.py:300](backend/app/services/queue_manager.py#L300))
5. **Socket.IO emits 'job_added'** → Frontend updates in real-time ([App.tsx:80](frontend/src/App.tsx#L80))
6. **Background thread processes job** → `QueueManager._process_jobs()` ([queue_manager.py:434](backend/app/services/queue_manager.py#L434))
7. **ProcessorService.process_item()** → Main workflow ([processor_service.py](backend/app/services/processor_service.py))
   - Load user overrides from `job.json`
   - AI analysis with Gemini Vision
   - Upload images to eBay Media API
   - Determine category and aspects
   - Create inventory item + offer
   - Publish to eBay
8. **Socket.IO emits 'job_update'** → Frontend shows completion ([App.tsx:84](frontend/src/App.tsx#L84))

---

## Directory Structure

```
ebay-draft-commander/
├── backend/                    # Python Flask backend
│   ├── app/                    # Application factory package
│   │   ├── __init__.py        # create_app() factory
│   │   ├── blueprints/        # Flask blueprints (routing)
│   │   │   ├── api.py         # REST API endpoints (/api/*)
│   │   │   └── ui.py          # Serves frontend static files
│   │   ├── core/              # Core utilities
│   │   │   ├── constants.py   # App-wide constants
│   │   │   ├── database.py    # SQLAlchemy models
│   │   │   ├── logger.py      # Logging configuration
│   │   │   ├── paths.py       # Path resolution helpers
│   │   │   ├── settings_manager.py  # Settings persistence
│   │   │   └── validator.py   # Input validation
│   │   ├── models/            # Database models (empty, in core/database.py)
│   │   ├── services/          # Business logic
│   │   │   ├── ai_analyzer.py      # Gemini Vision integration
│   │   │   ├── ai_price.py         # AI price estimation
│   │   │   ├── book_service.py     # ISBN lookup service
│   │   │   ├── category_mapper.py  # eBay category mapping
│   │   │   ├── ebay_service.py     # Legacy eBay wrapper
│   │   │   ├── image_service.py    # Image processing
│   │   │   ├── isbn_scanner.py     # Barcode scanning
│   │   │   ├── mcp_client.py       # MCP server client
│   │   │   ├── pricing_engine.py   # Main pricing logic
│   │   │   ├── processor_service.py # Main listing workflow
│   │   │   ├── queue_manager.py    # Job queue + processing
│   │   │   ├── scanner_service.py  # Inbox folder scanner
│   │   │   ├── template_manager.py # Template CRUD
│   │   │   └── ebay/               # eBay API modules
│   │   │       ├── analytics.py    # Analytics API
│   │   │       ├── auth.py         # OAuth flow
│   │   │       ├── browse.py       # Browse API
│   │   │       ├── inventory.py    # Inventory API
│   │   │       ├── media.py        # Media API (image upload)
│   │   │       ├── policies.py     # Fulfillment/Payment/Return
│   │   │       ├── researcher.py   # Price research
│   │   │       └── taxonomy.py     # Category/Aspects
│   │   └── static/            # Static assets served by Flask
│   ├── config.py              # Configuration class
│   └── wsgi.py                # Production entry point
│
├── frontend/                  # React TypeScript frontend
│   ├── public/                # Static assets
│   ├── src/
│   │   ├── components/        # React components
│   │   │   ├── ActiveListings.tsx     # Inventory management
│   │   │   ├── AnalyticsDashboard.tsx # Sales analytics
│   │   │   ├── InstallPrompt.tsx      # PWA install banner
│   │   │   ├── PhotoEditor.tsx        # Image editing tool
│   │   │   ├── PriceResearch.tsx      # AI pricing tool
│   │   │   ├── PreviewPanel.tsx       # Listing preview
│   │   │   ├── QueueCard.tsx          # Job card component
│   │   │   ├── QuickListingForm.tsx   # Manual listing form
│   │   │   ├── ScannerModal.tsx       # Barcode scanner
│   │   │   ├── TemplateManager.tsx    # Template UI
│   │   │   └── ui/                    # Radix UI components
│   │   ├── hooks/             # React hooks
│   │   │   └── usePullToRefresh.tsx
│   │   ├── lib/               # Utilities
│   │   │   ├── api.ts         # API client functions
│   │   │   ├── pwa.ts         # Service worker registration
│   │   │   ├── sanitizer.ts   # HTML sanitization
│   │   │   └── utils.ts       # Helpers
│   │   ├── pages/             # Top-level pages
│   │   │   ├── Dashboard.tsx  # Main queue view
│   │   │   ├── BatchScan.tsx  # Bulk inbox scan
│   │   │   └── Settings.tsx   # Settings page
│   │   ├── App.tsx            # Root component
│   │   ├── main.tsx           # React entry point
│   │   └── index.css          # Global styles
│   ├── electron/              # Electron wrapper
│   │   └── main.cjs           # Electron main process
│   ├── package.json           # Dependencies
│   ├── vite.config.ts         # Vite configuration
│   └── tsconfig.json          # TypeScript config
│
├── data/                      # Runtime data (gitignored)
│   ├── commander.db           # SQLite database
│   └── logs/                  # Application logs
│
├── inbox/                     # Item folders to process
│   └── [item_folder]/         # Each folder = 1 job
│       ├── *.jpg              # Product photos
│       ├── ai_data.json       # Cached AI analysis
│       └── job.json           # User overrides
│
├── scripts/                   # Build/utility scripts
├── tests/                     # Test suite
├── .env                       # Environment variables
├── requirements.txt           # Python dependencies
├── manage.py                  # CLI management commands
└── README.md                  # Project documentation
```

---

## Key Entry Points

### Backend
- **[backend/wsgi.py](backend/wsgi.py)** - Production entry point, starts Flask server
  - Calls `create_app()` from `backend/app/__init__.py`
  - Initializes `QueueManager` singleton
  - Runs `socketio.run(app, port=5000)`

- **[backend/app/__init__.py](backend/app/__init__.py)** - Application factory
  - Creates Flask app with config
  - Registers blueprints (`ui_bp`, `api_bp`)
  - Initializes SocketIO
  - Injects `queue_manager` into app context

### Frontend
- **[frontend/src/main.tsx](frontend/src/main.tsx)** - React entry point
  - Renders `<App />` to DOM
  - Imports global CSS

- **[frontend/src/App.tsx](frontend/src/App.tsx)** - Root component
  - Manages global state (jobs, queue stats, selected job)
  - Establishes Socket.IO connection for real-time updates
  - Handles tab navigation
  - Renders page components based on active tab

---

## Core Workflow: Processing a Listing

### 1. Job Creation
**Location:** [backend/app/services/queue_manager.py](backend/app/services/queue_manager.py)

```python
# QueueManager.add_folder() - Line ~300
def add_folder(self, folder_path: str, metadata: dict = None) -> QueueJob:
    # Create job record
    job = QueueJob(
        id=generate_job_id(),
        folder_path=str(folder_path),
        folder_name=Path(folder_path).name,
        status=JobStatus.PENDING,
        job_metadata=metadata or {}
    )

    # Save to database
    with self.SessionFactory() as session:
        db_job = self.JobModel(...)
        session.add(db_job)
        session.commit()

    # Emit real-time event
    self.emit_event('job_added', job.to_dict())

    return job
```

### 2. Queue Processing
**Location:** [backend/app/services/queue_manager.py:434](backend/app/services/queue_manager.py#L434)

```python
# Background thread continuously processes pending jobs
def _process_jobs(self):
    while self._processing:
        if self._paused:
            time.sleep(1)
            continue

        # Get next pending job
        job = self._get_next_job()
        if not job:
            break

        # Process with ProcessorService
        from backend.app.services.processor_service import ProcessorService
        processor = ProcessorService()
        result = processor.process_item(job, log_callback=self._log_to_job)

        # Update job status
        self._update_job_from_result(job, result)
```

### 3. Main Processing Logic
**Location:** [backend/app/services/processor_service.py](backend/app/services/processor_service.py)

```python
def process_item(self, job: QueueJob, log_callback=None) -> dict:
    """Main workflow for creating an eBay listing"""

    # 1. Load user overrides from job.json
    user_overrides = self._load_user_overrides(folder_path)

    # 2. Perform AI analysis (or load cached ai_data.json)
    ai_result = self._perform_enhanced_ai_analysis(
        folder_path, images, condition, user_overrides
    )

    # 3. Upload images to eBay Media API
    image_urls = upload_folder(
        str(folder_path),
        max_images=MAX_IMAGES_PER_LISTING
    )

    # 4. Determine category (AI suggestion or default)
    category_id = self._determine_category(ai_data, user_overrides)

    # 5. Get category-specific aspects from eBay Taxonomy API
    aspects = self._build_item_specifics(category_id, ai_data)

    # 6. Create inventory item on eBay
    inventory_result = self.ebay_service.inventory.create_inventory_item(
        sku=generate_sku(),
        title=title,
        description=description_html,
        image_urls=image_urls,
        aspects=aspects,
        condition=condition
    )

    # 7. Create offer with pricing
    offer_result = self.ebay_service.inventory.create_offer(
        sku=sku,
        price=final_price,
        quantity=1,
        category_id=category_id,
        fulfillment_policy_id=fulfillment_policy,
        payment_policy_id=payment_policy,
        return_policy_id=return_policy
    )

    # 8. Publish to eBay (optional, based on auto_publish setting)
    if should_auto_publish:
        publish_result = self.ebay_service.inventory.publish_offer(offer_id)

    return {
        'success': True,
        'listing_id': inventory_result['sku'],
        'offer_id': offer_result['offerId'],
        'price': final_price
    }
```

### 4. AI Analysis
**Location:** [backend/app/services/ai_analyzer.py](backend/app/services/ai_analyzer.py)

Uses Google Gemini Vision to analyze product images:
- Extract title, description, condition
- Identify brand, model, features
- Generate item specifics (color, size, material, etc.)
- Research mode: Uses Google Search Grounding for pricing

### 5. eBay API Integration
**Location:** [backend/app/services/ebay/](backend/app/services/ebay/)

Modular services for each eBay API:
- **[auth.py](backend/app/services/ebay/auth.py)** - OAuth 2.0 flow, token refresh
- **[inventory.py](backend/app/services/ebay/inventory.py)** - Create items, offers, publish
- **[media.py](backend/app/services/ebay/media.py)** - Upload images to Picture Services
- **[taxonomy.py](backend/app/services/ebay/taxonomy.py)** - Get categories, aspects
- **[browse.py](backend/app/services/ebay/browse.py)** - Search listings for pricing
- **[analytics.py](backend/app/services/ebay/analytics.py)** - Sales metrics

---

## Important Patterns

### 1. Application Factory Pattern
The backend uses Flask's application factory pattern for testability and modularity.

**[backend/app/__init__.py](backend/app/__init__.py):**
```python
def create_app(config_class=Config, queue_manager=None):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    socketio.init_app(app)

    # Inject dependencies
    app.queue_manager = queue_manager

    # Register blueprints
    app.register_blueprint(ui_bp)
    app.register_blueprint(api_bp, url_prefix='/api')

    return app
```

### 2. Real-Time Updates (Socket.IO)
All queue events are broadcast to connected clients for instant UI updates.

**Backend emits events:**
```python
# queue_manager.py
self.emit_event('job_added', job.to_dict())
self.emit_event('job_update', job.to_dict())
self.emit_event('job_log', log_entry)
```

**Frontend listens:**
```typescript
// App.tsx
socket.on('job_added', (newJob: Job) => {
    setJobs(prev => [...prev, newJob])
})

socket.on('job_update', (updatedJob: Job) => {
    setJobs(prev => prev.map(j => j.id === updatedJob.id ? updatedJob : j))
})
```

### 3. Caching Strategy
AI analysis results are cached to avoid redundant API calls:

```
inbox/item_folder/
├── photo1.jpg
├── photo2.jpg
├── ai_data.json      # Cached AI response
└── job.json          # User overrides
```

If `ai_data.json` exists, skip Gemini API call and use cached data.

### 4. User Overrides
Users can create `job.json` in any folder to override AI suggestions:

```json
{
    "user_title": "Custom Title",
    "user_price": "29.99",
    "user_description": "<p>Custom description</p>",
    "condition": "USED_EXCELLENT",
    "category_id": "12345"
}
```

Priority: User Override > Queue Metadata > AI Suggestion > Default

### 5. Template System
**Location:** [backend/app/services/template_manager.py](backend/app/services/template_manager.py)

Save recurring listing configurations:
```python
template = {
    'fulfillment_policy': 'policy_id_123',
    'payment_policy': 'policy_id_456',
    'return_policy': 'policy_id_789',
    'default_price': '19.99',
    'description_template': '<p>...</p>'
}

template_manager.save_template('Electronics Default', template)
```

### 6. Error Recovery
Jobs track `attempts` and `max_attempts` (default: 3):
- Failed jobs can be retried via `/api/retry`
- Errors are logged with `error_type` and `error_message`
- Frontend displays error details in job cards

---

## Key Configuration

### Environment Variables (.env)
```bash
# eBay API Credentials
EBAY_APP_ID=your-app-id
EBAY_CERT_ID=your-cert-id
EBAY_RU_NAME=your-runame

# eBay Policies (from eBay Seller Hub)
EBAY_FULFILLMENT_POLICY=policy_id
EBAY_PAYMENT_POLICY=policy_id
EBAY_RETURN_POLICY=policy_id
EBAY_MERCHANT_LOCATION=US  # Two-letter country code

# Google Gemini API
GOOGLE_API_KEY=your-gemini-key

# Feature Flags
EBAY_AUTO_PUBLISH=false  # Auto-publish listings
CONFIDENCE_THRESHOLD=85  # Min AI confidence for auto-publish
AUTO_PUBLISH_MIN_PRICE=15.00  # Min price for auto-publish

# Custom Paths (optional)
INBOX_PATH=/custom/path/to/inbox
```

### Database Schema
**[backend/app/core/database.py](backend/app/core/database.py)**

```python
class JobModel(Base):
    __tablename__ = 'jobs'

    id = Column(String(10), primary_key=True)
    folder_path = Column(Text, nullable=False)
    folder_name = Column(String(255), nullable=False)
    status = Column(String(20), default='pending')
    listing_id = Column(String(50))
    offer_id = Column(String(50))
    price = Column(String(20))
    error_type = Column(String(100))
    error_message = Column(Text)
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    timing_json = Column(Text)  # JSON timing data
    metadata_json = Column(Text)  # Job metadata
```

---

## API Endpoints

### Queue Management
- `GET /api/jobs` - List all jobs
- `GET /api/status` - Queue status + stats
- `POST /api/start` - Start queue processing
- `POST /api/pause` - Pause queue
- `POST /api/resume` - Resume queue
- `POST /api/retry` - Retry all failed jobs
- `POST /api/clear` - Clear completed jobs
- `POST /api/scan` - Scan inbox for new folders

### Job Operations
- `GET /api/job/<id>/details` - Get job details with AI data
- `POST /api/job/<id>/update` - Update job metadata
- `DELETE /api/job/<id>` - Delete job
- `POST /api/upload` - Upload photos (creates job)

### eBay Integration
- `GET /api/ebay/status` - Check eBay auth status
- `GET /api/ebay/auth/url` - Get OAuth URL
- `POST /api/ebay/auth/callback` - OAuth callback handler
- `GET /api/ebay/policies` - Get fulfillment/payment/return policies
- `GET /api/ebay/inventory` - List active listings
- `POST /api/ebay/inventory/<id>/update` - Update listing price/title

### Utilities
- `GET /api/settings` - Get user settings
- `POST /api/settings` - Save settings
- `POST /api/lookup/book` - ISBN lookup
- `GET /api/templates` - List templates
- `POST /api/templates` - Save template
- `DELETE /api/templates/<id>` - Delete template

---

## Frontend Architecture

### State Management
Uses React hooks + Socket.IO for real-time sync:
- Global state in `App.tsx`
- Props drilling to child components
- Socket.IO listeners update state automatically

### Key Components

**[Dashboard.tsx](frontend/src/pages/Dashboard.tsx)** - Main queue view
- Job list with status indicators
- Queue controls (start/pause/scan)
- Selected job details panel
- Real-time progress updates

**[ActiveListings.tsx](frontend/src/components/ActiveListings.tsx)** - Inventory management
- Fetch active eBay listings
- Bulk price/title updates
- Listing status (active/out-of-stock/ended)

**[AnalyticsDashboard.tsx](frontend/src/components/AnalyticsDashboard.tsx)** - Sales analytics
- Revenue charts (Recharts)
- Top sellers
- Inventory metrics

**[PhotoEditor.tsx](frontend/src/components/PhotoEditor.tsx)** - Image editing
- Brightness/Contrast/Saturation adjustments
- Crop/Rotate
- Preview and save

**[PriceResearch.tsx](frontend/src/components/PriceResearch.tsx)** - AI pricing
- Query Gemini with Google Search Grounding
- Show comparable listings
- Confidence scores

---

## Development Workflow

### Running the App

**Backend:**
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your API keys

# Run Flask server
python backend/wsgi.py
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev  # Vite dev server on port 5175
```

**Production Build:**
```bash
# Build frontend
cd frontend
npm run build  # Outputs to backend/app/static/

# Run production server
python backend/wsgi.py
# Access at http://localhost:5000/app
```

### Testing
```bash
# Run all tests
python run_all_tests.py

# Or use pytest directly
pytest tests/
```

---

## Common Tasks

### Adding a New API Endpoint
1. Add route to [backend/app/blueprints/api.py](backend/app/blueprints/api.py)
2. Add client function to [frontend/src/lib/api.ts](frontend/src/lib/api.ts)
3. Use in frontend component

### Adding a New eBay API Integration
1. Create module in `backend/app/services/ebay/`
2. Implement API calls with error handling
3. Add to `eBayService` or use directly in `ProcessorService`

### Adding a New Frontend Page
1. Create component in `frontend/src/pages/`
2. Add tab to `Sidebar.tsx` and `MobileNavBar.tsx`
3. Add route handler in `App.tsx`

### Modifying AI Analysis
1. Edit prompt in [backend/app/services/ai_analyzer.py](backend/app/services/ai_analyzer.py)
2. Update JSON schema for structured output
3. Clear `ai_data.json` caches in inbox folders to regenerate

---

## Debugging Tips

### Backend Logs
- Location: `data/logs/`
- Files: `backend.log`, `queue_manager.log`, `api.log`
- Level: Set via `backend/app/core/logger.py`

### Frontend Console
- Socket.IO connection status
- API call responses
- React component renders (React DevTools)

### Database Inspection
```bash
sqlite3 data/commander.db
.tables
SELECT * FROM jobs WHERE status = 'failed';
```

### Common Issues
- **eBay auth failed:** Check token expiration, run OAuth flow
- **AI analysis slow:** Gemini API rate limits, use cached `ai_data.json`
- **Images not uploading:** Check eBay Picture Services quota (12 images/listing)
- **Socket.IO not connecting:** CORS issues, check `socketio.init_app()` origins

---

## Architecture Decisions

### Why Flask Application Factory?
- Testability: Can create multiple app instances with different configs
- Modularity: Blueprints separate concerns (UI vs API)
- Dependency Injection: Queue manager and services are singletons

### Why Socket.IO?
- Real-time updates for queue processing
- Mobile-friendly (long polling fallback)
- Bi-directional communication

### Why SQLite?
- Simple setup, no external database server
- Sufficient for local desktop app
- Portable (single `.db` file)

### Why Vite?
- Fast HMR (Hot Module Replacement)
- Modern ES modules
- Built-in TypeScript support
- Better than CRA for 2025+

### Why Radix UI?
- Unstyled primitives (full control over design)
- Accessibility built-in (ARIA, keyboard nav)
- Headless components (works with Tailwind)

---

## Future Improvements

### Potential Enhancements
- [ ] Multi-user support (separate databases per user)
- [ ] Cloud sync (Supabase integration started but not active)
- [ ] Advanced image editing (background removal, AI upscaling)
- [ ] Bulk operations (multi-select, batch price updates)
- [ ] Draft scheduler (schedule listings for future)
- [ ] Cross-posting (eBay + Mercari + Poshmark)
- [ ] Mobile native app (React Native?)

### Known Limitations
- Single-user design (no auth system)
- eBay policies must be created manually in Seller Hub
- No inventory syncing (updates are one-way: app → eBay)
- Limited error recovery (manual retry required)

---

## Key Files Reference

| File | Purpose | Lines |
|------|---------|-------|
| [backend/wsgi.py](backend/wsgi.py) | Production entry point | 96 |
| [backend/app/__init__.py](backend/app/__init__.py) | Application factory | 47 |
| [backend/app/blueprints/api.py](backend/app/blueprints/api.py) | REST API routes | 1000+ |
| [backend/app/services/queue_manager.py](backend/app/services/queue_manager.py) | Job queue + processing | 700+ |
| [backend/app/services/processor_service.py](backend/app/services/processor_service.py) | Main listing workflow | 600+ |
| [backend/app/services/ai_analyzer.py](backend/app/services/ai_analyzer.py) | Gemini Vision integration | 600+ |
| [backend/app/services/pricing_engine.py](backend/app/services/pricing_engine.py) | AI pricing | 500+ |
| [backend/app/services/ebay/inventory.py](backend/app/services/ebay/inventory.py) | eBay Inventory API | 400+ |
| [frontend/src/App.tsx](frontend/src/App.tsx) | Root component | 257 |
| [frontend/src/pages/Dashboard.tsx](frontend/src/pages/Dashboard.tsx) | Main queue view | 800+ |
| [frontend/src/lib/api.ts](frontend/src/lib/api.ts) | API client functions | 196 |

---

## Summary

eBay Draft Commander is a well-architected full-stack application that demonstrates modern web development practices:

**Strengths:**
- Clean separation of concerns (blueprints, services, components)
- Real-time updates via Socket.IO
- Comprehensive AI integration (Gemini Vision + Search Grounding)
- Mobile-first PWA design
- Robust error handling and retry logic
- Template system for power users

**Architecture Highlights:**
- Flask Application Factory for testability
- SQLAlchemy ORM for database abstraction
- Background threading for async job processing
- React hooks for state management
- Vite for modern frontend tooling
- TypeScript for type safety

**Next Steps for Learning:**
1. Run the app locally and explore the queue workflow
2. Read through `processor_service.py` to understand the listing creation flow
3. Inspect the eBay API modules to learn REST API integration patterns
4. Study the Socket.IO setup for real-time communication
5. Explore the frontend components to see modern React patterns

This walkthrough should give you a solid foundation for contributing to the project!
