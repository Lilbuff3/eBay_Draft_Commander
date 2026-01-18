"""
eBay Draft Commander Pro
Main GUI Application
"""
import os
import sys
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime
import threading
import webbrowser

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from ebay_api import eBayAPIClient
from ai_analyzer import AIAnalyzer


class DraftCommanderApp:
    """Main application window"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("eBay Draft Commander Pro")
        self.root.geometry("1200x800")
        self.root.configure(bg='#1a1a2e')
        
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
        
        # Setup UI
        self.setup_styles()
        self.create_widgets()
        
        # Initialize APIs in background
        self.root.after(100, self.initialize_apis)
    
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
        
        # Control buttons
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(control_frame, text="📁 Scan Inbox", 
                   command=self.scan_inbox).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="🤖 Generate All", 
                   command=self.generate_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="🌐 Open eBay", 
                   command=lambda: webbrowser.open('https://www.ebay.com/sl/sell')).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="📂 Open Inbox Folder", 
                   command=lambda: os.startfile(self.inbox_path)).pack(side=tk.LEFT, padx=5)
        
        # Item count
        self.item_count_label = ttk.Label(control_frame, text="Items: 0 Ready | 0 Posted")
        self.item_count_label.pack(side=tk.RIGHT, padx=10)
        
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
        """Scan inbox folder for new items"""
        self.status_label.configure(text="🔍 Scanning inbox...", foreground='#ffd700')
        
        folders = [f for f in self.inbox_path.iterdir() if f.is_dir()]
        
        self.items_listbox.delete(0, tk.END)
        self.items = []
        
        for folder in folders:
            # Check if folder has images
            images = list(folder.glob('*.jpg')) + list(folder.glob('*.jpeg')) + \
                     list(folder.glob('*.png')) + list(folder.glob('*.JPG'))
            
            if images:
                item = {
                    'name': folder.name,
                    'path': str(folder),
                    'image_count': len(images),
                    'status': 'pending',
                    'data': None
                }
                self.items.append(item)
                self.items_listbox.insert(tk.END, f"⏳ {folder.name} ({len(images)} imgs)")
        
        self.update_item_count()
        self.status_label.configure(text=f"✅ Found {len(self.items)} items", foreground='#00ff00')
        
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
                        text=f"🤖 Analyzing {idx+1}/{len(self.items)}...", foreground='#ffd700'))
                    
                    # Analyze with AI
                    data = self.ai_analyzer.analyze_folder(item['path'])
                    
                    if 'error' not in data:
                        item['data'] = data
                        item['status'] = 'ready'
                        
                        # Update listbox
                        self.root.after(0, lambda idx=i, name=item['name']: 
                                        self.items_listbox.delete(idx))
                        self.root.after(0, lambda idx=i, name=item['name']: 
                                        self.items_listbox.insert(idx, f"✅ {name}"))
                    else:
                        item['status'] = 'error'
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


def main():
    root = tk.Tk()
    app = DraftCommanderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
