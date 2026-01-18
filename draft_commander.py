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

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from ebay_api import eBayAPIClient
from ai_analyzer import AIAnalyzer
from create_from_folder import create_listing_from_folder, create_listing_structured
from queue_manager import QueueManager, QueueJob, JobStatus
from queue_logger import get_logger, new_session
from report_generator import generate_batch_report, generate_summary_text
from settings_manager import SettingsManager, get_settings_manager
from settings_dialog import SettingsDialog
from web_server import WebControlServer
from template_manager import get_template_manager
from template_dialog import TemplateDialog, SaveTemplateDialog
from photo_editor_dialog import PhotoEditorDialog
from price_research import get_price_researcher
from price_chart_widget import PriceChartDialog
from preview_generator import PreviewGenerator
from preview_dialog import PreviewDialog
from inventory_sync import get_inventory_sync
from inventory_dialog import InventorySyncDialog


class DraftCommanderApp:
    """Main application window"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("eBay Draft Commander Pro (AI Powered)")
        self.root.geometry("1300x850")
        self.root.configure(bg='#1a1a2e')
        
        # Configure Drop Target
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.on_drop)
        
        # Initialize components
        self.ebay_api = None
        self.ai_analyzer = None
        self.items = []  # List of analyzed items
        self.current_item_index = 0
        
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
            self.status_label.configure(text=f"📥 Imported {count} items", foreground='#00ff00')

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
        """Configure ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Dark theme colors
        style.configure('TFrame', background='#1a1a2e')
        style.configure('TLabel', background='#1a1a2e', foreground='white', font=('Segoe UI', 10))
        style.configure('Title.TLabel', font=('Segoe UI', 14, 'bold'), foreground='#00d9ff')
        style.configure('Header.TLabel', font=('Segoe UI', 12, 'bold'), foreground='#ffd700')
        style.configure('TButton', font=('Segoe UI', 10))
        style.configure('Action.TButton', font=('Segoe UI', 11, 'bold'))
        style.configure('TEntry', font=('Segoe UI', 10))
    
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
        """Create all UI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(header_frame, text="📦 eBay Draft Commander Pro", 
                  style='Title.TLabel').pack(side=tk.LEFT)
        
        self.status_label = ttk.Label(header_frame, text="Initializing...", 
                                       foreground='#888')
        self.status_label.pack(side=tk.RIGHT)
        
        # Control buttons - Row 1
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(control_frame, text="📁 Scan Inbox", 
                   command=self.scan_inbox).pack(side=tk.LEFT, padx=5)
        self.start_btn = ttk.Button(control_frame, text="🚀 Start Queue", 
                   command=self.start_queue)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.pause_btn = ttk.Button(control_frame, text="⏸️ Pause", 
                   command=self.pause_queue, state='disabled')
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="🌐 Open eBay", 
                   command=lambda: webbrowser.open('https://www.ebay.com/sl/sell')).pack(side=tk.LEFT, padx=5)
        
        # Item count and web URL
        self.item_count_label = ttk.Label(control_frame, text="Queue: 0 pending")
        self.item_count_label.pack(side=tk.RIGHT, padx=10)
        
        # Web control URL
        web_url = self.web_server.get_url()
        self.web_label = ttk.Label(control_frame, text=f"📱 {web_url}", 
                                   foreground='#00d9ff', cursor='hand2')
        self.web_label.pack(side=tk.RIGHT, padx=10)
        self.web_label.bind('<Button-1>', lambda e: webbrowser.open(web_url))
        
        # Control buttons - Row 2 (Queue Management)
        queue_frame = ttk.Frame(main_frame)
        queue_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(queue_frame, text="🔄 Retry Failed", 
                   command=self.retry_failed).pack(side=tk.LEFT, padx=5)
        ttk.Button(queue_frame, text="🗑️ Clear Done", 
                   command=self.clear_completed).pack(side=tk.LEFT, padx=5)
        ttk.Button(queue_frame, text="📊 Export Report", 
                   command=self.export_report).pack(side=tk.LEFT, padx=5)
        ttk.Button(queue_frame, text="📂 Open Inbox", 
                   command=lambda: os.startfile(self.inbox_path)).pack(side=tk.LEFT, padx=5)
        ttk.Button(queue_frame, text="⚙️ Settings",
                   command=self.open_settings).pack(side=tk.LEFT, padx=5)
        
        # Progress Bar
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                             maximum=100, length=400)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.progress_label = ttk.Label(progress_frame, text="0/0", width=10)
        self.progress_label.pack(side=tk.LEFT, padx=5)
        
        # Main content - split into left (items list) and right (details)
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Items list
        left_panel = ttk.Frame(content_frame, width=350)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        ttk.Label(left_panel, text="📋 Items Queue", style='Header.TLabel').pack(pady=5)
        
        # Listbox for items
        self.items_listbox = tk.Listbox(left_panel, font=('Segoe UI', 10),
                                         bg='#16213e', fg='white',
                                         selectbackground='#00d9ff',
                                         selectforeground='black',
                                         height=25)
        self.items_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.items_listbox.bind('<<ListboxSelect>>', self.on_item_select)
        
        # Right panel - Item details
        right_panel = ttk.Frame(content_frame)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Create scrollable frame for details
        self.canvas = tk.Canvas(right_panel, bg='#16213e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(right_panel, orient="vertical", command=self.canvas.yview)
        self.details_frame = ttk.Frame(self.canvas)
        
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.details_frame, anchor='nw')
        
        self.details_frame.bind('<Configure>', 
                                 lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind('<Configure>', 
                         lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))
        
        # Enable mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>", 
                             lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # Create detail widgets
        self.create_detail_widgets()
        
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
        
        self.char_count_label = ttk.Label(title_row, text="0/80", foreground='#888')
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
        
        self.price_note_label = ttk.Label(price_row, text="", foreground='#888')
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
                                  bg='#0f0f23', fg='white', insertbackground='white',
                                  wrap=tk.WORD)
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
            self.status_label.configure(text="⚙️ Settings updated", foreground='#00ff00')
    
    def reload_settings(self):
        """Reload settings and reinitialize API clients"""
        # Reload settings from file
        self.settings_manager.load()
        
        # Reinitialize API clients with new settings
        self.status_label.configure(text="🔄 Reloading APIs...", foreground='#ffd700')
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
            popup.configure(bg='#1a1a2e')
            popup.resizable(False, False)
            
            # Convert PIL image to Tkinter
            photo = ImageTk.PhotoImage(qr_img)
            
            # QR code label
            qr_label = tk.Label(popup, image=photo, bg='white')
            qr_label.image = photo  # Keep reference
            qr_label.pack(padx=20, pady=20)
            
            # URL label
            url_label = ttk.Label(popup, text=url, foreground='#00d9ff',
                                 font=('Segoe UI', 12))
            url_label.pack(pady=(0, 10))
            
            # Instructions
            ttk.Label(popup, text="Scan with your phone camera to open",
                     foreground='#888', font=('Segoe UI', 10)).pack(pady=(0, 15))
            
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
            self.status_label.configure(text=f"📋 Template applied", foreground='#00ff00')
            
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
        folder = self.current_item.get('folder')
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
            self.status_label.configure(text="🖼️ Photos edited", foreground='#00ff00')
    
    def open_price_research(self):
        """Open price research for current item"""
        # Get search query
        if self.current_item and self.current_item.get('title'):
            query = self.current_item['title'][:50]
        else:
            query = simpledialog.askstring("Price Research", 
                                          "Enter search keywords:",
                                          parent=self.root)
        
        if not query:
            return
        
        self.status_label.configure(text="📊 Researching prices...", foreground='#ffd700')
        self.root.update()
        
        try:
            researcher = get_price_researcher()
            results = researcher.research(query)
            
            dialog = PriceChartDialog(self.root, results)
            self.root.wait_window(dialog)
            
            self.status_label.configure(text="Ready", foreground='white')
            
        except Exception as e:
            messagebox.showerror("Research Error", str(e))
            self.status_label.configure(text="Ready", foreground='white')
    
    def open_preview(self):
        """Open listing preview for current item"""
        if not self.current_item:
            messagebox.showwarning("No Item", "Please select an item to preview")
            return
        
        # Build listing data from current item
        listing_data = {
            'title': self.current_item.get('title', 'Untitled'),
            'price': self.current_item.get('price', '29.99'),
            'condition': self.current_item.get('condition', 'USED_GOOD'),
            'description': self.current_item.get('description', 'No description'),
            'item_specifics': self.current_item.get('item_specifics', {}),
            'shipping_info': 'Free shipping, ships within 1 business day',
        }
        
        # Get images
        image_paths = []
        folder = self.current_item.get('folder')
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
                    text="✅ Ready", foreground='#00ff00'))
            except Exception as e:
                self.root.after(0, lambda: self.status_label.configure(
                    text=f"⚠️ {str(e)[:50]}", foreground='#ff6b6b'))
        
        threading.Thread(target=init, daemon=True).start()
        
    def scan_inbox(self):
        """Scan inbox folder for new items and add to queue"""
        self.status_label.configure(text="🔍 Scanning inbox...", foreground='#ffd700')
        
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
            self.status_label.configure(text=f"✅ Added {added_count} new items ({stats['pending']} pending)", foreground='#00ff00')
        else:
            self.status_label.configure(text=f"✅ {stats['pending']} items pending", foreground='#00ff00')
        
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
                        text=f"🤖 Processing {idx+1}/{len(self.items)}...", foreground='#ffd700'))
                    
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
                text="✅ Generation complete", foreground='#00ff00'))
            self.root.after(0, self.update_item_count)
        
        threading.Thread(target=generate, daemon=True).start()
        
    def on_item_select(self, event):
        """Handle item selection in listbox"""
        selection = self.items_listbox.curselection()
        if not selection:
            return
            
        self.current_item_index = selection[0]
        item = self.items[self.current_item_index]
        
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
                      foreground='#ff6b6b').pack(anchor='w', pady=(5, 2))
            
            for aspect in aspects['required']:
                self.create_aspect_widget(aspect, required=True)
        
        # Optional fields
        if aspects['optional']:
            ttk.Label(self.specifics_container, text="Optional Fields", 
                      foreground='#888').pack(anchor='w', pady=(10, 2))
            
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
        color = '#00ff00' if count <= 80 else '#ff6b6b'
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
        self.status_label.configure(text="📋 Copied!", foreground='#00ff00')
        
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
            self.status_label.configure(text="✅ Marked as posted", foreground='#00ff00')
            
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
        self.start_btn.configure(state='disabled')
        self.pause_btn.configure(state='normal', text="⏸️ Pause")
        self.status_label.configure(text="🚀 Processing queue...", foreground='#ffd700')
        self.queue_manager.start_processing()
    
    def pause_queue(self):
        """Pause or resume queue processing"""
        if self.queue_manager.is_paused():
            self.queue_manager.resume()
            self.pause_btn.configure(text="⏸️ Pause")
            self.status_label.configure(text="▶️ Resumed", foreground='#00ff00')
            self.logger.queue_resume()
        else:
            self.queue_manager.pause()
            self.pause_btn.configure(text="▶️ Resume")
            self.status_label.configure(text="⏸️ Paused", foreground='#ffd700')
            self.logger.queue_pause()
    
    def retry_failed(self):
        """Retry all failed jobs"""
        failed = self.queue_manager.get_failed_jobs()
        if not failed:
            messagebox.showinfo("No Failed", "No failed jobs to retry.")
            return
        
        self.queue_manager.retry_failed()
        self._refresh_queue_display()
        self.status_label.configure(text=f"🔄 {len(failed)} jobs reset for retry", foreground='#00ff00')
    
    def clear_completed(self):
        """Clear completed jobs from queue"""
        self.queue_manager.clear_completed()
        self._refresh_queue_display()
        self.status_label.configure(text="🗑️ Cleared completed", foreground='#00ff00')
    
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
        """Refresh the queue listbox display"""
        self.items_listbox.delete(0, tk.END)
        self.items = []
        
        status_icons = {
            JobStatus.PENDING: "⏳",
            JobStatus.PROCESSING: "⚙️",
            JobStatus.COMPLETED: "✅",
            JobStatus.FAILED: "❌",
            JobStatus.PAUSED: "⏸️",
            JobStatus.SKIPPED: "⏭️"
        }
        
        for job in self.queue_manager.jobs:
            icon = status_icons.get(job.status, "❓")
            text = f"{icon} {job.folder_name}"
            if job.listing_id:
                text += f" → {job.listing_id[:8]}..."
            elif job.error_type:
                text += f" ({job.error_type})"
            self.items_listbox.insert(tk.END, text)
            
            # Track for legacy compatibility
            self.items.append({
                'name': job.folder_name,
                'path': job.folder_path,
                'status': job.status.value,
                'data': {'listing_id': job.listing_id, 'offer_id': job.offer_id}
            })
        
        self._update_queue_stats()
    
    def _update_queue_stats(self):
        """Update queue statistics display"""
        stats = self.queue_manager.get_stats()
        text = f"Queue: {stats['pending']} pending | {stats['completed']} done | {stats['failed']} failed"
        self.item_count_label.configure(text=text)
    
    def _on_job_start(self, job: QueueJob):
        """Callback when a job starts processing"""
        self.logger.job_start(job.id, job.folder_name)
        self.root.after(0, lambda: self._refresh_queue_display())
        self.root.after(0, lambda: self.status_label.configure(
            text=f"⚙️ Processing: {job.folder_name}", foreground='#ffd700'))
    
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
        
        self.root.after(0, lambda: self.start_btn.configure(state='normal'))
        self.root.after(0, lambda: self.pause_btn.configure(state='disabled'))
        self.root.after(0, lambda: self.status_label.configure(
            text=f"✅ Complete: {stats['completed']} done, {stats['failed']} failed", 
            foreground='#00ff00'))
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

