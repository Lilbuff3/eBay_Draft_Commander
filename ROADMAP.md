# eBay Draft Commander Pro - Project Roadmap

> **Vision**: A complete eBay selling dashboard that makes selling not just easier, but more **profitable and measured**.

## 🎯 Project Goals

1. **Automate listing creation** - Drop photos → AI analysis → Published listing
2. **Edit existing listings** - Bulk update prices, titles, inventory
3. **Measure profitability** - Track sales, fees, profit margins, ROI
4. **Analytics dashboard** - Conversion rates, best sellers, pricing insights
5. **Mobile access** - Manage listings on the go

---

## 📊 Market Viability (Honest Assessment)

### The Good
- **Real pain point**: eBay's Seller Hub is clunky; power sellers need better tools
- **AI differentiation**: Gemini-powered analysis is genuinely useful for unique items
- **You're the target user**: Building for yourself = authentic product decisions
- **Market exists**: Listing tools like Vendoo, List Perfectly charge $20-100/mo

### The Challenges
- **Crowded space**: Many listing tools exist (though most lack AI)
- **eBay API limits**: Some features require enterprise tier access
- **Support burden**: SaaS requires customer support infrastructure

### Recommendation
**Start as a personal tool, validate through your own usage, then consider:**
1. Open-source with optional paid features (freemium)
2. One-time purchase (avoid recurring support obligation)
3. YouTube content showing the tool → organic marketing

---

## 🛠 Tech Stack (2026)

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.12+ | Core backend |
| Flask | 3.x | Web server / REST API |
| `google-genai` | Latest | Gemini 3 Flash Preview + Google Search grounding |
| eBay REST APIs | 2026 | Inventory, Browse, Taxonomy, Media, Account APIs |

### Frontend
| Technology | Version | Purpose |
|------------|---------|---------|
| React | 19 | UI framework |
| Vite | 7.x | Build tool / dev server |
| TypeScript | 5.x | Type safety |
| Shadcn/ui | Latest | Component library (Radix-based) |
| Framer Motion | 11.x | Animations |
| Tailwind CSS | 4.x | Styling |

### Future (Mobile)
| Technology | Purpose |
|------------|---------|
| React Native / Expo | Cross-platform mobile app |
| Supabase | Auth + real-time sync (optional) |

---

## 📅 Development Phases

### Phase 1: Foundation ✅ (Complete)
*Python-only script, no GUI, no Git*
- [x] eBay OAuth authentication (`ebay_auth.py`)
- [x] Basic API integration (Inventory, Media, Taxonomy)
- [x] AI image analysis with Gemini (`ai_analyzer.py`)
- [x] Single listing creation from folder

### Phase 2: Desktop GUI ✅ (Complete)
*Tkinter-based interface*
- [x] Queue management GUI (`draft_commander.py`)
- [x] Batch processing multiple items
- [x] Settings dialog
- [x] Basic photo editing

### Phase 3: Git & Structure ✅ (Complete)
- [x] Version control initialized
- [x] Project structure organized
- [x] Environment configuration (`.env`)

### Phase 4: Modern Frontend ✅ (Complete)
*Migrated from Tkinter to Vite + React*
- [x] Vite project setup with React 19
- [x] Shadcn/ui component library
- [x] Dashboard layout with resizable panels
- [x] Tool components (Photo Editor, Price Research, Templates, Preview)

### Phase 5: Backend Integration ✅ (Complete)
- [x] Flask serves React build
- [x] REST API endpoints for tools
- [x] Real-time queue status polling

### Phase 6: Core Features ✅ (Complete)
- [x] **Price Research** - eBay Browse API integration
- [x] **AI Price Estimation** - Gemini 3 with Google Search grounding
- [x] **Shipping Selector** - Per-listing policy selection
- [x] **Create Listing Button** - End-to-end from dashboard
- [x] **Photo Editor** - Pillow-based image processing
- [x] **Template Manager** - Save/load listing presets
- [x] **Preview Panel** - Live HTML preview before publishing

### Phase 7: Polish & Personal Deploy ✅ (Complete)
- [x] **UI polish and error handling**
  - Production logging infrastructure (JSON + rotation)
  - Custom exception hierarchy
  - Improved error handling in critical endpoints
- [x] **PWA / Mobile Install**
  - Manifest.json configuration
  - Install prompt integration
- [x] **System Reliability**
  - Health check script (`verify_system_health.py`)
  - Gemini 3 Model Upgrade (Flash Preview)
  - Google Search Grounding for pricing
  - QR Code generator improvement

### Phase 8: Listing Management ✅ (Complete)
*Edit existing listings*
- [x] Fetch active listings from eBay
- [x] Bulk price editor
- [x] Bulk title optimizer
- [x] Inventory quantity sync
- [x] End/relist controls

### Phase 9: Analytics Dashboard ✅ (Complete)
*Profit and sales tracking*
- [x] Sales history sync (eBay Orders API)
- [x] Profit calculator (sale price - fees - cost)
- [x] Revenue charts over time
- [x] Best-selling items report
- [x] Sell-through rate by category

---

## 🚀 Upcoming Features (Post-MVP)

### Phase 10: Advanced Automation (In Progress)
- [x] **Bulk Inbox Scan** (Web/Mobile) - Queue multiple folders instantly
- [ ] Auto-background removal
- [ ] Cross-posting to Poshmark/Mercari
- [ ] Draft listing scheduling

### Phase 11: Mobile Native App (Future)
- [ ] React Native / Expo setup
- [ ] Push notifications for sales
- [ ] Barcode scanner for lookup

---

## 🎯 Success Criteria

### MVP Verification ✅
- [x] Can create 10+ listings/day without errors
- [x] Zero manual Seller Hub intervention needed
- [x] Mobile app installable and functional

### Profitability Goals
- [ ] Know profit margin on every sale
- [ ] Weekly revenue report auto-generated
- [ ] Identify underperforming inventory

---

## 📝 Notes

- **Started**: January 2026
- **Primary User**: Adam (eBay seller)
- **License**: MIT (personal) → TBD for commercial

---

*Last updated: January 20, 2026*
