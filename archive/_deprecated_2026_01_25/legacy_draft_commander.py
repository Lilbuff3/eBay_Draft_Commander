"""
eBay Draft Commander Pro
Main GUI Application with Bulk Queue Processing
"""
import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from tkinterdnd2 import DND_FILES, TkinterDnD
from pathlib import Path
from datetime import datetime
import threading
import webbrowser
import shutil

# Add parent and tools directories to path for imports
base_path = Path(__file__).parent
sys.path.insert(0, str(base_path))
sys.path.insert(0, str(base_path / "tools"))

from ebay_api import eBayAPIClient
from backend.app.services.ai_analyzer import AIAnalyzer
from create_from_folder import create_listing_from_folder, create_listing_structured
from backend.app.services.queue_manager import QueueManager, QueueJob, JobStatus
from queue_logger import get_logger, new_session
from report_generator import generate_batch_report, generate_summary_text
from backend.app.core.settings_manager import SettingsManager, get_settings_manager
from settings_dialog import SettingsDialog
from web_server import WebControlServer
from backend.app.services.template_manager import get_template_manager
from template_dialog import TemplateDialog, SaveTemplateDialog
from photo_editor_dialog import PhotoEditorDialog
from price_research import get_price_researcher
from price_chart_widget import PriceChartDialog
from preview_generator import PreviewGenerator
from preview_dialog import PreviewDialog
from inventory_sync import get_inventory_sync
from inventory_dialog import InventorySyncDialog
from ui_widgets import (Theme, StageIndicator, WorkflowStage, QueueCard, 
                        ToolCard, ActionBar, HeroImage)


class DraftCommanderApp:
    """Main application window"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("eBay Draft Commander Pro (AI Powered)")
        self.root.geometry("1300x850")
        self.root.configure(bg='#FAFAF9')  # Alabaster - warm off-white
        
        # Configure Drop Target
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.on_drop)
        
        # Initialize components
        self.ebay_api = None
        self.ai_analyzer = None
        self.items = []  # List of analyzed items
        self.current_item_index = 0
        self.current_item = None  # Currently selected item data
        
        # Paths
        self.base_path = Path(__file__).parent
        self.inbox_path = self.base_path / "inbox"
        self.ready_path = self.base_path / "ready"
        self.posted_path = self.base_path / "posted"
        
        # Queue Manager
        self.queue_manager = QueueManager(self.base_path)
        self.queue_manager.set_processor(create_listing_structured)
        self.queue_manager.on_job_start = self._on_job_start
        self.queue_manager.on_job_complete = self._on_job_complete
        self.queue_manager.on_job_error = self._on_job_error
        self.queue_manager.on_queue_complete = self._on_queue_complete
        self.queue_manager.on_progress = self._on_progress
        
        # Logger
        self.logger = get_logger()
        
        # Settings Manager
        self.settings_manager = get_settings_manager()
        
        # Web Control Server
        self.web_server = WebControlServer(self.queue_manager)
        self.web_server.start()
        
        # Setup UI
        self.setup_styles()
        self.create_menu()
        self.create_widgets()
        
        # Initialize APIs in background
        self.root.after(100, self.initialize_apis)
        
        # Check for Google API Key
        self.root.after(1000, self.check_google_key)
        
        # Refresh queue UI if there's existing state
        self.root.after(500, self._refresh_queue_display)

    def on_drop(self, event):
        """Handle dropped files/folders"""
        data = event.data
        if not data:
            return
            
        # Clean up path (tkinterdnd can wrap in {})
        paths = self.parse_drop_paths(data)
        
        count = 0
        for path in paths:
            p = Path(path)
            if p.is_dir():
                # Copy folder to inbox? Or just link it?
                # For now, let's copy to inbox to keep items organized
                dest = self.inbox_path / p.name
                if not dest.exists():
                    shutil.copytree(p, dest)
                    count += 1
            elif p.is_file() and p.suffix.lower() in ['.jpg', '.png', '.jpeg']:
                # Handle loose images - create new folder
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                new_folder = self.inbox_path / f"New_Item_{timestamp}"
                new_folder.mkdir(exist_ok=True)
                shutil.copy2(p, new_folder / p.name)
                count += 1
                
        if count > 0:
            self.scan_inbox()
            self.status_label.configure(text=f"📥 Imported {count} items", foreground='#4D7C5D')

    def parse_drop_paths(self, data):
        """Parse the weird string format from tkinterdnd"""
        # It comes as "{path with spaces} path_no_spaces"
        paths = []
        if data.startswith('{'):
            # Complex parsing needed for multiple paths with spaces
            parts = data.split('} {')
            for part in parts:
                paths.append(part.replace('{', '').replace('}', ''))
        else:
            paths = [data]
        return paths

    def check_google_key(self):
        """Check if Google API Key is configured"""
        env_path = self.base_path / ".env"
        has_key = False
        if env_path.exists():
            with open(env_path, 'r') as f:
                if 'GOOGLE_API_KEY=' in f.read():
                    has_key = True
        
        if not has_key:
            key = simpledialog.askstring("Setup", "Enter your Google Gemini API Key to enable AI features:", parent=self.root)
            if key:
                with open(env_path, 'a') as f:
                    f.write(f"\nGOOGLE_API_KEY={key.strip()}")
                messagebox.showinfo("Saved", "API Key saved! Restarting AI services...")
                self.initialize_apis()

    def setup_styles(self):
        """Configure ttk styles - Bright & Natural Theme"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Natural theme color palette
        ALABASTER = '#FAFAF9'      # Background
        WHITE = '#FFFFFF'           # Surface/Cards
        SAGE_GREEN = '#4D7C5D'     # Primary actions
        WARM_CLAY = '#D97757'      # Alerts/warnings
        CHARCOAL = '#374151'       # Text
        SAND = '#E5E7EB'           # Borders/dividers
        BEIGE = '#F5F5F0'          # Sidebar
        MUTED_GOLD = '#C9A227'     # Warnings
        
        # Base frame styles
        style.configure('TFrame', background=ALABASTER)
        style.configure('Sidebar.TFrame', background=BEIGE)
        
        # Label styles
        style.configure('TLabel', background=ALABASTER, foreground=CHARCOAL, font=('Segoe UI', 10))
        style.configure('Title.TLabel', font=('Segoe UI', 16, 'bold'), foreground=SAGE_GREEN, background=ALABASTER)
        style.configure('Header.TLabel', font=('Segoe UI', 12, 'bold'), foreground=CHARCOAL, background=ALABASTER)
        style.configure('Sidebar.TLabel', background=BEIGE, foreground=CHARCOAL)
        
        # Button styles - Pill shaped with organic colors
        style.configure('TButton', 
                       font=('Segoe UI', 10),
                       background=WHITE,
                       foreground=CHARCOAL,
                       borderwidth=1,
                       relief='solid',
                       padding=(12, 6))
        style.map('TButton',
                 background=[('active', SAND), ('pressed', SAND)],
                 relief=[('pressed', 'sunken')])
        
        # Primary action buttons (Sage Green)
        style.configure('Primary.TButton',
                       font=('Segoe UI', 11, 'bold'),
                       background=SAGE_GREEN,
                       foreground=WHITE,
                       padding=(16, 8))
        style.map('Primary.TButton',
                 background=[('active', '#3D6349'), ('pressed', '#3D6349')])
        
        # Action buttons (standard)
        style.configure('Action.TButton', 
                       font=('Segoe UI', 11, 'bold'),
                       background=SAGE_GREEN,
                       foreground=WHITE,
                       padding=(14, 8))
        style.map('Action.TButton',
                 background=[('active', '#3D6349'), ('pressed', '#3D6349')])
        
        # Warning/Delete buttons (Warm Clay)
        style.configure('Warning.TButton',
                       font=('Segoe UI', 10),
                       background=WARM_CLAY,
                       foreground=WHITE,
                       padding=(12, 6))
        style.map('Warning.TButton',
                 background=[('active', '#C4593D'), ('pressed', '#C4593D')])
        
        # Entry styles
        style.configure('TEntry', 
                       font=('Segoe UI', 10),
                       fieldbackground=WHITE,
                       foreground=CHARCOAL,
                       borderwidth=1,
                       relief='solid')
        
        # Combobox styles
        style.configure('TCombobox',
                       font=('Segoe UI', 10),
                       fieldbackground=WHITE,
                       foreground=CHARCOAL)
        
        # Progress bar
        style.configure('TProgressbar',
                       background=SAGE_GREEN,
                       troughcolor=SAND,
                       borderwidth=0,
                       thickness=8)
        
        # Scrollbar
        style.configure('TScrollbar',
                       background=SAND,
                       troughcolor=ALABASTER,
                       borderwidth=0)
        
        # Store colors for use elsewhere
        self.colors = {
            'bg': ALABASTER,
            'surface': WHITE,
            'primary': SAGE_GREEN,
            'secondary': WARM_CLAY,
            'text': CHARCOAL,
            'border': SAND,
            'sidebar': BEIGE,
            'success': SAGE_GREEN,
            'error': WARM_CLAY,
            'warning': MUTED_GOLD
        }
    
    def create_menu(self):
        """Create menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Options menu
        options_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Options", menu=options_menu)
        options_menu.add_command(label="⚙️ Settings", command=self.open_settings)
        options_menu.add_separator()
        options_menu.add_command(label="📂 Open Inbox Folder", 
                                command=lambda: os.startfile(self.inbox_path))
        options_menu.add_command(label="📂 Open Posted Folder",
                                command=lambda: os.startfile(self.posted_path))
        
        # Mobile Control menu
        mobile_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="📱 Mobile", menu=mobile_menu)
        mobile_menu.add_command(label="🌐 Open Web Interface", 
                               command=lambda: webbrowser.open(self.web_server.get_url()))
        mobile_menu.add_command(label="📷 Show QR Code",
                               command=self.show_qr_code)
        mobile_menu.add_separator()
        mobile_menu.add_command(label=f"URL: {self.web_server.get_url()}",
                               state='disabled')
        
        # Tools menu (new features)
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="🛠️ Tools", menu=tools_menu)
        tools_menu.add_command(label="📋 Listing Templates", command=self.open_templates)
        tools_menu.add_command(label="🖼️ Photo Editor", command=self.open_photo_editor)
        tools_menu.add_command(label="📊 Price Research", command=self.open_price_research)
        tools_menu.add_command(label="👁️ Preview Listing", command=self.open_preview)
        tools_menu.add_separator()
        tools_menu.add_command(label="📦 Inventory Sync", command=self.open_inventory_sync)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="🌐 eBay Seller Hub",
                             command=lambda: webbrowser.open('https://www.ebay.com/sh/landing'))
        help_menu.add_command(label="📖 eBay API Docs",
                             command=lambda: webbrowser.open('https://developer.ebay.com/docs'))
        
    def create_widgets(self):
        """Create Bento-style UI layout with visual workflow"""
        # Main container with natural background
        main_frame = tk.Frame(self.root, bg=Theme.ALABASTER)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # =====================================================================
        # HEADER - Title + Settings
        # =====================================================================
        header_frame = tk.Frame(main_frame, bg=Theme.ALABASTER)
        header_frame.pack(fill=tk.X, padx=20, pady=(15, 5))
        
        title_label = tk.Label(header_frame, text="📦 eBay Draft Commander Pro",
                              font=('Segoe UI', 18, 'bold'),
                              bg=Theme.ALABASTER, fg=Theme.SAGE_GREEN)
        title_label.pack(side=tk.LEFT)
        
        # Settings button (right)
        settings_btn = tk.Button(header_frame, text="⚙️",
                                font=('Segoe UI', 14),
                                bg=Theme.ALABASTER, fg=Theme.CHARCOAL,
                                relief='flat', cursor='hand2',
                                command=self.open_settings)
        settings_btn.pack(side=tk.RIGHT, padx=10)
        
        # Mobile QR button
        qr_btn = tk.Button(header_frame, text="📱",
                          font=('Segoe UI', 14),
                          bg=Theme.ALABASTER, fg=Theme.CHARCOAL,
                          relief='flat', cursor='hand2',
                          command=self.show_qr_code)
        qr_btn.pack(side=tk.RIGHT)
        
        # Status label
        self.status_label = tk.Label(header_frame, text="Ready",
                                    font=('Segoe UI', 10),
                                    bg=Theme.ALABASTER, fg=Theme.LIGHT_GRAY)
        self.status_label.pack(side=tk.RIGHT, padx=20)
        
        # =====================================================================
        # STAGE INDICATOR - Workflow Pipeline
        # =====================================================================
        self.stage_indicator = StageIndicator(main_frame, 
                                             on_stage_click=self._on_stage_click)
        self.stage_indicator.pack(fill=tk.X, pady=10)
        
        # =====================================================================
        # MAIN CONTENT - Three Column Bento
        # =====================================================================
        content_frame = tk.Frame(main_frame, bg=Theme.ALABASTER)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # -----------------------------------------------------------------
        # LEFT: Queue Cards (scrollable)
        # -----------------------------------------------------------------
        left_panel = tk.Frame(content_frame, bg=Theme.BEIGE, width=220)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        left_panel.pack_propagate(False)
        
        # Queue header
        queue_header = tk.Frame(left_panel, bg=Theme.BEIGE)
        queue_header.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(queue_header, text="📋 Queue", 
                font=('Segoe UI', 12, 'bold'),
                bg=Theme.BEIGE, fg=Theme.CHARCOAL).pack(side=tk.LEFT)
        
        # Scan button
        scan_btn = tk.Button(queue_header, text="＋",
                            font=('Segoe UI', 12, 'bold'),
                            bg=Theme.SAGE_GREEN, fg=Theme.WHITE,
                            relief='flat', width=3, cursor='hand2',
                            command=self.scan_inbox)
        scan_btn.pack(side=tk.RIGHT)
        
        # Scrollable queue container
        queue_canvas = tk.Canvas(left_panel, bg=Theme.BEIGE, 
                                highlightthickness=0)
        queue_scrollbar = ttk.Scrollbar(left_panel, orient="vertical",
                                       command=queue_canvas.yview)
        
        self.queue_container = tk.Frame(queue_canvas, bg=Theme.BEIGE)
        
        queue_canvas.configure(yscrollcommand=queue_scrollbar.set)
        queue_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        queue_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        queue_canvas.create_window((0, 0), window=self.queue_container, anchor='nw')
        self.queue_container.bind('<Configure>',
            lambda e: queue_canvas.configure(scrollregion=queue_canvas.bbox('all')))
        
        # Store for queue cards
        self.queue_cards = []
        
        # Legacy listbox (hidden, for compatibility)
        self.items_listbox = tk.Listbox(left_panel)  # Hidden
        
        # -----------------------------------------------------------------
        # CENTER: Hero Image + Listing Data
        # -----------------------------------------------------------------
        center_panel = tk.Frame(content_frame, bg=Theme.ALABASTER)
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))
        
        # Top row: Image + Quick Fields
        top_row = tk.Frame(center_panel, bg=Theme.ALABASTER)
        top_row.pack(fill=tk.X, pady=(0, 15))
        
        # Hero image
        self.hero_image = HeroImage(top_row, size=250, 
                                    on_click=self._open_photo_editor_from_hero)
        self.hero_image.pack(side=tk.LEFT, padx=(0, 15))
        
        # Quick edit fields (card style)
        fields_card = tk.Frame(top_row, bg=Theme.WHITE,
                              highlightthickness=1,
                              highlightbackground=Theme.SAND)
        fields_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        fields_inner = tk.Frame(fields_card, bg=Theme.WHITE)
        fields_inner.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Title field
        tk.Label(fields_inner, text="📝 Title", font=('Segoe UI', 10, 'bold'),
                bg=Theme.WHITE, fg=Theme.CHARCOAL).pack(anchor='w')
        
        title_row = tk.Frame(fields_inner, bg=Theme.WHITE)
        title_row.pack(fill=tk.X, pady=(2, 10))
        
        self.title_var = tk.StringVar()
        self.title_entry = tk.Entry(title_row, textvariable=self.title_var,
                                   font=('Segoe UI', 11),
                                   bg=Theme.ALABASTER, fg=Theme.CHARCOAL,
                                   relief='flat', highlightthickness=1,
                                   highlightbackground=Theme.SAND)
        self.title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.char_count_label = tk.Label(title_row, text="0/80",
                                        font=('Segoe UI', 9),
                                        bg=Theme.WHITE, fg=Theme.LIGHT_GRAY)
        self.char_count_label.pack(side=tk.LEFT, padx=5)
        self.title_var.trace('w', self.update_char_count)
        
        # Price field
        tk.Label(fields_inner, text="💰 Price", font=('Segoe UI', 10, 'bold'),
                bg=Theme.WHITE, fg=Theme.CHARCOAL).pack(anchor='w')
        
        price_row = tk.Frame(fields_inner, bg=Theme.WHITE)
        price_row.pack(fill=tk.X, pady=(2, 10))
        
        tk.Label(price_row, text="$", font=('Segoe UI', 12),
                bg=Theme.WHITE, fg=Theme.CHARCOAL).pack(side=tk.LEFT)
        
        self.price_var = tk.StringVar()
        self.price_entry = tk.Entry(price_row, textvariable=self.price_var,
                                   font=('Segoe UI', 14, 'bold'),
                                   bg=Theme.ALABASTER, fg=Theme.SAGE_GREEN,
                                   relief='flat', width=8,
                                   highlightthickness=1,
                                   highlightbackground=Theme.SAND)
        self.price_entry.pack(side=tk.LEFT, padx=5)
        
        self.price_note_label = tk.Label(price_row, text="",
                                        font=('Segoe UI', 9),
                                        bg=Theme.WHITE, fg=Theme.LIGHT_GRAY)
        self.price_note_label.pack(side=tk.LEFT, padx=10)
        
        # Category field
        tk.Label(fields_inner, text="📂 Category", font=('Segoe UI', 10, 'bold'),
                bg=Theme.WHITE, fg=Theme.CHARCOAL).pack(anchor='w')
        
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(fields_inner, textvariable=self.category_var,
                                          font=('Segoe UI', 10), state='readonly')
        self.category_combo.pack(fill=tk.X, pady=(2, 10))
        self.category_combo.bind('<<ComboboxSelected>>', self.on_category_change)
        
        # Item Specifics (collapsible)
        specifics_frame = tk.Frame(fields_inner, bg=Theme.WHITE)
        specifics_frame.pack(fill=tk.X)
        
        tk.Label(specifics_frame, text="📋 Specifics", font=('Segoe UI', 10, 'bold'),
                bg=Theme.WHITE, fg=Theme.CHARCOAL).pack(anchor='w')
        
        self.specifics_container = tk.Frame(specifics_frame, bg=Theme.WHITE)
        self.specifics_container.pack(fill=tk.X, pady=5)
        self.specific_widgets = {}
        
        # -----------------------------------------------------------------
        # TOOL CARDS - Horizontal scroll
        # -----------------------------------------------------------------
        tools_section = tk.Frame(center_panel, bg=Theme.ALABASTER)
        tools_section.pack(fill=tk.X, pady=10)
        
        tk.Label(tools_section, text="🛠️ Tools",
                font=('Segoe UI', 12, 'bold'),
                bg=Theme.ALABASTER, fg=Theme.CHARCOAL).pack(anchor='w', pady=(0, 10))
        
        tools_row = tk.Frame(tools_section, bg=Theme.ALABASTER)
        tools_row.pack(fill=tk.X)
        
        # Create tool cards
        tool_definitions = [
            ('📷', 'Photo Editor', 'Edit & enhance', self.open_photo_editor),
            ('💰', 'Price Research', 'Check sold items', self.open_price_research),
            ('👁️', 'Preview', 'See listing', self.open_preview),
            ('📋', 'Templates', 'Quick apply', self.open_templates),
            ('📦', 'Inventory', 'Sync with eBay', self.open_inventory_sync),
        ]
        
        for icon, title, desc, callback in tool_definitions:
            card = ToolCard(tools_row, icon, title, desc, 
                           on_click=callback, width=130)
            card.pack(side=tk.LEFT, padx=(0, 10))
        
        # -----------------------------------------------------------------
        # DESCRIPTION - Expandable text area
        # -----------------------------------------------------------------
        desc_section = tk.Frame(center_panel, bg=Theme.WHITE,
                               highlightthickness=1,
                               highlightbackground=Theme.SAND)
        desc_section.pack(fill=tk.BOTH, expand=True, pady=10)
        
        desc_header = tk.Frame(desc_section, bg=Theme.WHITE)
        desc_header.pack(fill=tk.X, padx=15, pady=(10, 5))
        
        tk.Label(desc_header, text="📄 Description",
                font=('Segoe UI', 10, 'bold'),
                bg=Theme.WHITE, fg=Theme.CHARCOAL).pack(side=tk.LEFT)
        
        copy_btn = tk.Button(desc_header, text="📋 Copy",
                            font=('Segoe UI', 9),
                            bg=Theme.WHITE, fg=Theme.SAGE_GREEN,
                            relief='flat', cursor='hand2',
                            command=lambda: self.copy_to_clipboard(
                                self.desc_text.get('1.0', tk.END)))
        copy_btn.pack(side=tk.RIGHT)
        
        self.desc_text = tk.Text(desc_section, height=6, font=('Segoe UI', 10),
                                bg=Theme.WHITE, fg=Theme.CHARCOAL,
                                insertbackground=Theme.CHARCOAL,
                                relief='flat', wrap=tk.WORD,
                                padx=15, pady=10)
        self.desc_text.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        # -----------------------------------------------------------------
        # RIGHT: Quick Actions (optional sidebar)
        # -----------------------------------------------------------------
        # Simplified - actions moved to bottom bar
        
        # =====================================================================
        # ACTION BAR - Sticky Footer
        # =====================================================================
        self.action_bar = ActionBar(main_frame,
                                   on_start=self._toggle_queue,
                                   on_post=self.open_ebay_listing)
        self.action_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # =====================================================================
        # Progress indicator (inline with action bar)
        # =====================================================================
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_label = tk.Label(main_frame, text="0/0",
                                      font=('Segoe UI', 9),
                                      bg=Theme.ALABASTER, fg=Theme.LIGHT_GRAY)
        # Store reference but don't pack - updated by action bar
        
        # Legacy canvas reference for compatibility
        self.canvas = tk.Canvas(main_frame)  # Hidden, for scroll binding
        self.details_frame = tk.Frame(main_frame)  # Hidden, for compatibility
    
    def _on_stage_click(self, stage: WorkflowStage):
        """Handle workflow stage click - filter queue by stage"""
        self.status_label.configure(text=f"Viewing: {stage.name.title()} items",
                                   fg=Theme.SAGE_GREEN)
    
    def _toggle_queue(self):
        """Toggle queue processing (start/pause)"""
        if self.queue_manager.is_processing():
            self.pause_queue()
        else:
            self.start_queue()
    
    def _open_photo_editor_from_hero(self, image_paths: list):
        """Open photo editor from hero image click"""
        if image_paths:
            dialog = PhotoEditorDialog(self.root, image_paths)
            self.root.wait_window(dialog)
            if dialog.result:
                self.status_label.configure(text="🖼️ Photos edited", 
                                           fg=Theme.SAGE_GREEN)
        
    def create_detail_widgets(self):
        """Create the detail view widgets"""
        # Title section
        title_frame = ttk.Frame(self.details_frame)
        title_frame.pack(fill=tk.X, pady=5, padx=10)
        
        ttk.Label(title_frame, text="📝 Title", style='Header.TLabel').pack(anchor='w')
        
        title_row = ttk.Frame(title_frame)
        title_row.pack(fill=tk.X, pady=2)
        
        self.title_var = tk.StringVar()
        self.title_entry = ttk.Entry(title_row, textvariable=self.title_var, font=('Segoe UI', 11))
        self.title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.char_count_label = ttk.Label(title_row, text="0/80", foreground='#9CA3AF')
        self.char_count_label.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(title_row, text="📋 Copy", 
                   command=lambda: self.copy_to_clipboard(self.title_var.get())).pack(side=tk.LEFT)
        
        self.title_var.trace('w', self.update_char_count)
        
        # Category section
        category_frame = ttk.Frame(self.details_frame)
        category_frame.pack(fill=tk.X, pady=5, padx=10)
        
        ttk.Label(category_frame, text="📂 Category", style='Header.TLabel').pack(anchor='w')
        
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(category_frame, textvariable=self.category_var,
                                            font=('Segoe UI', 10), state='readonly')
        self.category_combo.pack(fill=tk.X, pady=2)
        self.category_combo.bind('<<ComboboxSelected>>', self.on_category_change)
        
        # Item Specifics section
        specifics_frame = ttk.Frame(self.details_frame)
        specifics_frame.pack(fill=tk.X, pady=5, padx=10)
        
        ttk.Label(specifics_frame, text="📋 Item Specifics", style='Header.TLabel').pack(anchor='w')
        
        self.specifics_container = ttk.Frame(specifics_frame)
        self.specifics_container.pack(fill=tk.X, pady=5)
        
        self.specific_widgets = {}  # Store references to specific entry widgets
        
        # Price section
        price_frame = ttk.Frame(self.details_frame)
        price_frame.pack(fill=tk.X, pady=5, padx=10)
        
        ttk.Label(price_frame, text="💰 Price", style='Header.TLabel').pack(anchor='w')
        
        price_row = ttk.Frame(price_frame)
        price_row.pack(fill=tk.X, pady=2)
        
        ttk.Label(price_row, text="$").pack(side=tk.LEFT)
        self.price_var = tk.StringVar()
        self.price_entry = ttk.Entry(price_row, textvariable=self.price_var, 
                                      font=('Segoe UI', 11), width=10)
        self.price_entry.pack(side=tk.LEFT, padx=5)
        
        self.price_note_label = ttk.Label(price_row, text="", foreground='#9CA3AF')
        self.price_note_label.pack(side=tk.LEFT, padx=10)
        
        # Description section
        desc_frame = ttk.Frame(self.details_frame)
        desc_frame.pack(fill=tk.X, pady=5, padx=10)
        
        desc_header = ttk.Frame(desc_frame)
        desc_header.pack(fill=tk.X)
        
        ttk.Label(desc_header, text="📄 Description", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(desc_header, text="📋 Copy", 
                   command=lambda: self.copy_to_clipboard(self.desc_text.get('1.0', tk.END))).pack(side=tk.RIGHT)
        
        self.desc_text = tk.Text(desc_frame, height=8, font=('Segoe UI', 10),
                                  bg='#FFFFFF',  # White paper-like surface
                                  fg='#374151',  # Charcoal text
                                  insertbackground='#374151',
                                  relief='solid',
                                  borderwidth=1,
                                  highlightthickness=0,
                                  wrap=tk.WORD,
                                  padx=8, pady=8)  # Inner padding for paper feel
        self.desc_text.pack(fill=tk.X, pady=5)
        
        # Action buttons
        action_frame = ttk.Frame(self.details_frame)
        action_frame.pack(fill=tk.X, pady=15, padx=10)
        
        ttk.Button(action_frame, text="📋 Copy All to Clipboard", 
                   command=self.copy_all, style='Action.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="🌐 Open eBay Listing", 
                   command=self.open_ebay_listing, style='Action.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="✅ Mark as Posted", 
                   command=self.mark_posted, style='Action.TButton').pack(side=tk.LEFT, padx=5)
    
    # =========================================================================
    # Settings Methods
    # =========================================================================
    
    def open_settings(self):
        """Open the Settings dialog"""
        dialog = SettingsDialog(self.root, self.settings_manager)
        self.root.wait_window(dialog)
        
        if dialog.result:
            # Settings were saved, reload configuration
            self.reload_settings()
            self.status_label.configure(text="⚙️ Settings updated", foreground='#4D7C5D')
    
    def reload_settings(self):
        """Reload settings and reinitialize API clients"""
        # Reload settings from file
        self.settings_manager.load()
        
        # Reinitialize API clients with new settings
        self.status_label.configure(text="🔄 Reloading APIs...", foreground='#C9A227')
        self.initialize_apis()
    
    def show_qr_code(self):
        """Show QR code window for mobile access"""
        try:
            import qrcode
            from PIL import ImageTk
            
            # Generate QR code
            url = self.web_server.get_url()
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            # Create popup window
            popup = tk.Toplevel(self.root)
            popup.title("📱 Scan to Connect")
            popup.configure(bg='#FAFAF9')
            popup.resizable(False, False)
            
            # Convert PIL image to Tkinter
            photo = ImageTk.PhotoImage(qr_img)
            
            # QR code label
            qr_label = tk.Label(popup, image=photo, bg='white')
            qr_label.image = photo  # Keep reference
            qr_label.pack(padx=20, pady=20)
            
            # URL label
            url_label = ttk.Label(popup, text=url, foreground='#4D7C5D',
                                 font=('Segoe UI', 12))
            url_label.pack(pady=(0, 10))
            
            # Instructions
            ttk.Label(popup, text="Scan with your phone camera to open",
                     foreground='#9CA3AF', font=('Segoe UI', 10)).pack(pady=(0, 15))
            
            # Center on parent
            popup.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() - popup.winfo_width()) // 2
            y = self.root.winfo_y() + (self.root.winfo_height() - popup.winfo_height()) // 2
            popup.geometry(f"+{x}+{y}")
            
        except ImportError:
            messagebox.showinfo("QR Code", 
                               f"Scan not available. Open this URL on your phone:\n\n{self.web_server.get_url()}")
    
    # =========================================================================
    # Tools Menu Handlers
    # =========================================================================
    
    def open_templates(self):
        """Open listing templates dialog"""
        dialog = TemplateDialog(self.root, get_template_manager())
        self.root.wait_window(dialog)
        
        if dialog.result:
            # Apply template to current item
            template_data = dialog.result
            self.status_label.configure(text=f"📋 Template applied", foreground='#4D7C5D')
            
            # If we have a current item, apply template values
            if hasattr(self, 'condition_combo') and template_data.get('condition'):
                self.condition_combo.set(template_data['condition'])
            if hasattr(self, 'price_entry') and template_data.get('default_price'):
                self.price_entry.delete(0, tk.END)
                self.price_entry.insert(0, template_data['default_price'])
    
    def open_photo_editor(self):
        """Open photo editor for current item"""
        if not self.current_item:
            messagebox.showwarning("No Item", "Please select an item first")
            return
        
        # Get images from current folder
        folder = self.current_item.get('path')  # items use 'path' key
        if not folder:
            messagebox.showwarning("No Folder", "No folder path for current item")
            return
        
        folder_path = Path(folder)
        image_paths = []
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG']:
            image_paths.extend(folder_path.glob(ext))
        
        if not image_paths:
            messagebox.showwarning("No Images", "No images found in item folder")
            return
        
        dialog = PhotoEditorDialog(self.root, [str(p) for p in image_paths])
        self.root.wait_window(dialog)
        
        if dialog.result:
            self.status_label.configure(text="🖼️ Photos edited", foreground='#4D7C5D')
    
    def open_price_research(self):
        """Open price research for current item"""
        # Get search query
        if self.current_item and (self.current_item.get('title') or self.current_item.get('name')):
            query = (self.current_item.get('title') or self.current_item.get('name'))[:50]
        else:
            query = simpledialog.askstring("Price Research", 
                                          "Enter search keywords:",
                                          parent=self.root)
        
        if not query:
            return
        
        self.status_label.configure(text="📊 Researching prices...", foreground='#C9A227')
        self.root.update()
        
        try:
            researcher = get_price_researcher()
            results = researcher.research(query)
            
            dialog = PriceChartDialog(self.root, results)
            self.root.wait_window(dialog)
            
            self.status_label.configure(text="Ready", foreground='#374151')
            
        except Exception as e:
            messagebox.showerror("Research Error", str(e))
            self.status_label.configure(text="Ready", foreground='#374151')
    
    def open_preview(self):
        """Open listing preview for current item"""
        if not self.current_item:
            messagebox.showwarning("No Item", "Please select an item to preview")
            return
        
        # Build listing data from current item
        listing_data = {
            'title': self.current_item.get('title') or self.current_item.get('name', 'Untitled'),
            'price': self.current_item.get('price', '29.99'),
            'condition': self.current_item.get('condition', 'USED_GOOD'),
            'description': self.current_item.get('description', 'No description'),
            'item_specifics': self.current_item.get('item_specifics', {}),
            'shipping_info': 'Free shipping, ships within 1 business day',
        }
        
        # Get images
        image_paths = []
        folder = self.current_item.get('path')  # items use 'path' key
        if folder:
            folder_path = Path(folder)
            for ext in ['*.jpg', '*.jpeg', '*.png']:
                image_paths.extend([str(p) for p in folder_path.glob(ext)])
        
        dialog = PreviewDialog(self.root, listing_data, image_paths[:8])
        self.root.wait_window(dialog)
    
    def open_inventory_sync(self):
        """Open inventory sync dialog"""
        dialog = InventorySyncDialog(self.root, get_inventory_sync())
        self.root.wait_window(dialog)
        
    def initialize_apis(self):
        """Initialize API clients in background"""
        def init():
            try:
                self.ebay_api = eBayAPIClient()
                self.ai_analyzer = AIAnalyzer()
                self.root.after(0, lambda: self.status_label.configure(
                    text="✅ Ready", foreground='#4D7C5D'))
            except Exception as e:
                self.root.after(0, lambda: self.status_label.configure(
                    text=f"⚠️ {str(e)[:50]}", foreground='#D97757'))
        
        threading.Thread(target=init, daemon=True).start()
        
    def scan_inbox(self):
        """Scan inbox folder for new items and add to queue"""
        self.status_label.configure(text="🔍 Scanning inbox...", foreground='#C9A227')
        
        folders = [f for f in self.inbox_path.iterdir() if f.is_dir()]
        
        added_count = 0
        for folder in folders:
            # Check if folder has images
            images = list(folder.glob('*.jpg')) + list(folder.glob('*.jpeg')) + \
                     list(folder.glob('*.png')) + list(folder.glob('*.JPG'))
            
            if images:
                # Check if already in queue
                existing = self.queue_manager.get_job_by_folder(folder.name)
                if not existing:
                    self.queue_manager.add_folder(str(folder))
                    added_count += 1
        
        # Refresh the display
        self._refresh_queue_display()
        
        stats = self.queue_manager.get_stats()
        if added_count > 0:
            self.status_label.configure(text=f"✅ Added {added_count} new items ({stats['pending']} pending)", foreground='#4D7C5D')
        else:
            self.status_label.configure(text=f"✅ {stats['pending']} items pending", foreground='#4D7C5D')
        
    def generate_all(self):
        """Generate listings for all pending items"""
        if not self.items:
            messagebox.showinfo("No Items", "Scan the inbox first to find items")
            return
            
        if not self.ai_analyzer:
            messagebox.showerror("Error", "AI Analyzer not initialized")
            return
        
        def generate():
            for i, item in enumerate(self.items):
                if item['status'] == 'pending':
                    self.root.after(0, lambda idx=i: self.status_label.configure(
                        text=f"🤖 Processing {idx+1}/{len(self.items)}...", foreground='#C9A227'))
                    
                    # Run full automation
                    try:
                        # Redirect print to nowhere or capture if possible?
                        # For now we rely on the function's internal logging
                        # We pass a callback or just check result
                        
                        listing_id = create_listing_from_folder(item['path'])
                        
                        if listing_id:
                            item['status'] = 'ready' # or 'posted' if fully posted
                            item['data'] = {'listing_id': listing_id, 'note': 'Draft/Listing Created'}
                            
                            # Move to posted?
                            self.root.after(0, lambda idx=i, name=item['name']: 
                                            self.items_listbox.delete(idx))
                            self.root.after(0, lambda idx=i, name=item['name']: 
                                            self.items_listbox.insert(idx, f"☁️ {name} (Draft Created)"))
                        else:
                            raise Exception("Listing creation returned None")
                            
                    except Exception as e:
                        item['status'] = 'error'
                        print(f"Error processing {item['name']}: {e}")
                        self.root.after(0, lambda idx=i, name=item['name']: 
                                        self.items_listbox.delete(idx))
                        self.root.after(0, lambda idx=i, name=item['name']: 
                                        self.items_listbox.insert(idx, f"❌ {name}"))
            
            self.root.after(0, lambda: self.status_label.configure(
                text="✅ Generation complete", foreground='#4D7C5D'))
            self.root.after(0, self.update_item_count)
        
        threading.Thread(target=generate, daemon=True).start()
        
    def on_item_select(self, event):
        """Handle item selection in listbox"""
        selection = self.items_listbox.curselection()
        if not selection:
            return
            
        self.current_item_index = selection[0]
        item = self.items[self.current_item_index]
        self.current_item = item  # Set current item for tools to access
        
        if item['data']:
            self.display_item(item['data'])
        else:
            # Clear display for pending items
            self.title_var.set("")
            self.price_var.set("")
            self.desc_text.delete('1.0', tk.END)
            
    def display_item(self, data):
        """Display item data in the detail view"""
        # Title
        listing = data.get('listing', {})
        self.title_var.set(listing.get('suggested_title', ''))
        
        # Price
        self.price_var.set(listing.get('suggested_price', ''))
        self.price_note_label.configure(text=listing.get('price_reasoning', '')[:50])
        
        # Description
        self.desc_text.delete('1.0', tk.END)
        self.desc_text.insert('1.0', listing.get('description', ''))
        
        # Get category suggestions
        if self.ebay_api:
            keywords = data.get('category_keywords', [])
            query = ' '.join(keywords[:3]) if keywords else listing.get('suggested_title', '')[:50]
            
            suggestions = self.ebay_api.get_category_suggestions(query)
            
            if suggestions:
                self.category_combo['values'] = [s['full_path'] for s in suggestions]
                self.category_combo.current(0)
                
                # Store category IDs
                self.category_ids = {s['full_path']: s['category_id'] for s in suggestions}
                
                # Load item aspects for first category
                self.load_item_aspects(suggestions[0]['category_id'])
        
        # Pre-fill item specifics from AI data
        identification = data.get('identification', {})
        specs = data.get('specifications', {})
        origin = data.get('origin', {})
        
        self.prefill_data = {
            'Brand': identification.get('brand'),
            'MPN': identification.get('mpn'),
            'Model': identification.get('model'),
            'Type': identification.get('product_type'),
            'Color': specs.get('color'),
            'Country/Region of Manufacture': origin.get('country_of_manufacture'),
        }
        
    def on_category_change(self, event):
        """Handle category selection change"""
        selected = self.category_var.get()
        
        if selected in self.category_ids:
            category_id = self.category_ids[selected]
            self.load_item_aspects(category_id)
            
    def load_item_aspects(self, category_id):
        """Load item aspects for a category and create form fields"""
        # Clear existing widgets
        for widget in self.specifics_container.winfo_children():
            widget.destroy()
        self.specific_widgets.clear()
        
        if not self.ebay_api:
            return
            
        aspects = self.ebay_api.get_item_aspects(category_id)
        
        # Required fields
        if aspects['required']:
            ttk.Label(self.specifics_container, text="Required Fields *", 
                      foreground='#D97757').pack(anchor='w', pady=(5, 2))
            
            for aspect in aspects['required']:
                self.create_aspect_widget(aspect, required=True)
        
        # Optional fields
        if aspects['optional']:
            ttk.Label(self.specifics_container, text="Optional Fields", 
                      foreground='#9CA3AF').pack(anchor='w', pady=(10, 2))
            
            for aspect in aspects['optional'][:8]:  # Limit to 8 optional
                self.create_aspect_widget(aspect, required=False)
                
    def create_aspect_widget(self, aspect, required=False):
        """Create a form widget for an item aspect"""
        name = aspect['name']
        
        row = ttk.Frame(self.specifics_container)
        row.pack(fill=tk.X, pady=2)
        
        # Label
        label_text = f"{name}{'*' if required else ''}"
        label = ttk.Label(row, text=label_text, width=25)
        label.pack(side=tk.LEFT)
        
        # Entry or combobox
        var = tk.StringVar()
        
        if aspect.get('values') and len(aspect['values']) < 20:
            # Use combobox for predefined values
            widget = ttk.Combobox(row, textvariable=var, values=aspect['values'])
        else:
            widget = ttk.Entry(row, textvariable=var)
        
        widget.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Pre-fill from AI data
        if hasattr(self, 'prefill_data') and name in self.prefill_data:
            prefill = self.prefill_data[name]
            if prefill:
                var.set(prefill)
        
        self.specific_widgets[name] = var
        
    def update_char_count(self, *args):
        """Update title character count"""
        count = len(self.title_var.get())
        color = '#4D7C5D' if count <= 80 else '#D97757'  # Sage Green / Warm Clay
        self.char_count_label.configure(text=f"{count}/80", foreground=color)
        
    def update_item_count(self):
        """Update the item count display"""
        ready = sum(1 for i in self.items if i['status'] == 'ready')
        posted = len(list(self.posted_path.glob('*'))) if self.posted_path.exists() else 0
        self.item_count_label.configure(text=f"Items: {ready} Ready | {posted} Posted Today")
        
    def copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        self.root.clipboard_clear()
        self.root.clipboard_append(text.strip())
        self.status_label.configure(text="📋 Copied!", foreground='#4D7C5D')
        
    def copy_all(self):
        """Copy all listing data as JSON for bookmarklet"""
        # Gather all data
        data = {
            'title': self.title_var.get(),
            'price': self.price_var.get(),
            'description': self.desc_text.get('1.0', tk.END).strip(),
            'category': self.category_var.get(),
            'item_specifics': {}
        }
        
        # Add item specifics
        for name, var in self.specific_widgets.items():
            value = var.get()
            if value:
                data['item_specifics'][name] = value
        
        # Copy as JSON
        json_str = json.dumps(data, indent=2)
        self.copy_to_clipboard(json_str)
        
        messagebox.showinfo("Copied!", 
                           "All listing data copied to clipboard!\n\n"
                           "Paste into eBay or use the bookmarklet.")
        
    def open_ebay_listing(self):
        """Open eBay listing page with title pre-filled"""
        title = self.title_var.get()
        url = f"https://www.ebay.com/sl/prelist/suggest?keywords={title.replace(' ', '+')}"
        webbrowser.open(url)
        
    def mark_posted(self):
        """Mark current item as posted"""
        if not self.items or self.current_item_index >= len(self.items):
            return
            
        item = self.items[self.current_item_index]
        
        # Move folder to posted
        src = Path(item['path'])
        dst = self.posted_path / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{item['name']}"
        
        try:
            src.rename(dst)
            
            # Remove from list
            self.items.pop(self.current_item_index)
            self.items_listbox.delete(self.current_item_index)
            
            self.update_item_count()
            self.status_label.configure(text="✅ Marked as posted", foreground='#4D7C5D')
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not move folder: {e}")
    
    # =========================================================================
    # Queue Management Methods
    # =========================================================================
    
    def start_queue(self):
        """Start queue processing"""
        if not self.queue_manager.get_pending_jobs():
            # Scan inbox first if queue is empty
            self.scan_inbox()
            if not self.queue_manager.get_pending_jobs():
                messagebox.showinfo("Empty Queue", "No items to process. Add folders to inbox first.")
                return
        
        self.logger.queue_start(len(self.queue_manager.get_pending_jobs()))
        
        # Update action bar
        if hasattr(self, 'action_bar'):
            self.action_bar.set_processing(True)
        
        self.status_label.configure(text="🚀 Processing queue...", fg=Theme.MUTED_GOLD)
        self.queue_manager.start_processing()
    
    def pause_queue(self):
        """Pause or resume queue processing"""
        if self.queue_manager.is_paused():
            self.queue_manager.resume()
            if hasattr(self, 'action_bar'):
                self.action_bar.set_processing(True)
            self.status_label.configure(text="▶️ Resumed", fg=Theme.SAGE_GREEN)
            self.logger.queue_resume()
        else:
            self.queue_manager.pause()
            if hasattr(self, 'action_bar'):
                self.action_bar.set_processing(False)
            self.status_label.configure(text="⏸️ Paused", fg=Theme.MUTED_GOLD)
            self.logger.queue_pause()
    
    def retry_failed(self):
        """Retry all failed jobs"""
        failed = self.queue_manager.get_failed_jobs()
        if not failed:
            messagebox.showinfo("No Failed", "No failed jobs to retry.")
            return
        
        self.queue_manager.retry_failed()
        self._refresh_queue_display()
        self.status_label.configure(text=f"🔄 {len(failed)} jobs reset for retry", foreground='#4D7C5D')
    
    def clear_completed(self):
        """Clear completed jobs from queue"""
        self.queue_manager.clear_completed()
        self._refresh_queue_display()
        self.status_label.configure(text="🗑️ Cleared completed", foreground='#4D7C5D')
    
    def export_report(self):
        """Export batch report to CSV"""
        if not self.queue_manager.jobs:
            messagebox.showinfo("No Data", "No jobs to report.")
            return
        
        report_path = generate_batch_report(self.queue_manager.jobs)
        
        # Also show summary
        summary = generate_summary_text(self.queue_manager.jobs)
        
        messagebox.showinfo("Report Saved", 
                           f"Report saved to:\n{report_path}\n\n{summary[:500]}")
        
        # Open the report
        os.startfile(report_path)
    
    def _refresh_queue_display(self):
        """Refresh the queue with visual QueueCards"""
        # Clear existing cards
        for card in self.queue_cards:
            card.destroy()
        self.queue_cards = []
        self.items = []
        
        # Also update hidden listbox for legacy compatibility
        self.items_listbox.delete(0, tk.END)
        
        for job in self.queue_manager.jobs:
            # Map job status to card status
            status_map = {
                JobStatus.PENDING: 'pending',
                JobStatus.PROCESSING: 'processing',
                JobStatus.COMPLETED: 'completed',
                JobStatus.FAILED: 'failed',
                JobStatus.PAUSED: 'pending',
                JobStatus.SKIPPED: 'completed',
            }
            status = status_map.get(job.status, 'pending')
            
            # Create QueueCard
            card = QueueCard(
                self.queue_container,
                name=job.folder_name,
                folder_path=job.folder_path,
                status=status,
                on_click=lambda c, j=job: self._on_queue_card_click(c, j),
                thumbnail_size=60
            )
            card.pack(fill=tk.X, pady=2)
            self.queue_cards.append(card)
            
            # Legacy listbox (hidden)
            self.items_listbox.insert(tk.END, job.folder_name)
            
            # Track items for legacy compatibility
            self.items.append({
                'name': job.folder_name,
                'path': job.folder_path,
                'status': job.status.value,
                'data': {'listing_id': job.listing_id, 'offer_id': job.offer_id}
            })
        
        self._update_queue_stats()
    
    def _on_queue_card_click(self, card: QueueCard, job: QueueJob):
        """Handle queue card selection"""
        # Deselect all cards
        for c in self.queue_cards:
            c.set_selected(False)
        
        # Select clicked card
        card.set_selected(True)
        
        # Set current item
        self.current_item = {
            'name': job.folder_name,
            'path': job.folder_path,
            'status': job.status.value,
            'data': {'listing_id': job.listing_id, 'offer_id': job.offer_id}
        }
        
        # Load hero image
        self.hero_image.load_images(job.folder_path)
        
        # Update status
        self.status_label.configure(text=f"Selected: {job.folder_name}",
                                   fg=Theme.CHARCOAL)
    
    def _update_queue_stats(self):
        """Update queue statistics in action bar"""
        stats = self.queue_manager.get_stats()
        
        # Update action bar if exists
        if hasattr(self, 'action_bar'):
            self.action_bar.update_status(
                stats['pending'], 
                stats['completed'], 
                stats['failed']
            )
    
    def _on_job_start(self, job: QueueJob):
        """Callback when a job starts processing"""
        self.logger.job_start(job.id, job.folder_name)
        self.root.after(0, lambda: self._refresh_queue_display())
        self.root.after(0, lambda: self.status_label.configure(
            text=f"⚙️ Processing: {job.folder_name}", foreground='#C9A227'))
    
    def _on_job_complete(self, job: QueueJob):
        """Callback when a job completes successfully"""
        elapsed = job.timing.get('total', 0) if job.timing else 0
        self.logger.job_complete(job.id, job.folder_name, job.listing_id, elapsed)
        
        # Move folder to posted
        try:
            src = Path(job.folder_path)
            if src.exists():
                dst = self.posted_path / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{job.folder_name}"
                self.posted_path.mkdir(exist_ok=True)
                shutil.move(str(src), str(dst))
        except Exception as e:
            print(f"Could not move to posted: {e}")
        
        self.root.after(0, lambda: self._refresh_queue_display())
    
    def _on_job_error(self, job: QueueJob):
        """Callback when a job fails"""
        self.logger.job_error(job.id, job.folder_name, job.error_type, job.error_message)
        self.root.after(0, lambda: self._refresh_queue_display())
    
    def _on_queue_complete(self):
        """Callback when queue processing completes"""
        stats = self.queue_manager.get_stats()
        self.logger.queue_complete(stats['completed'], stats['failed'], stats['total'])
        
        # Update action bar
        self.root.after(0, lambda: (
            self.action_bar.set_processing(False) if hasattr(self, 'action_bar') else None
        ))
        self.root.after(0, lambda: self.status_label.configure(
            text=f"✅ Complete: {stats['completed']} done, {stats['failed']} failed", 
            fg=Theme.SAGE_GREEN))
        self.root.after(0, lambda: self.progress_var.set(100))
    
    def _on_progress(self, current: int, total: int):
        """Callback for progress updates"""
        if total > 0:
            pct = (current / total) * 100
            self.root.after(0, lambda: self.progress_var.set(pct))
            self.root.after(0, lambda: self.progress_label.configure(text=f"{current}/{total}"))


def main():
    # Use TkinterDnD instead of standard Tk
    root = TkinterDnD.Tk()
    app = DraftCommanderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

