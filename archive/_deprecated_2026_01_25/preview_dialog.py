"""
Preview Dialog for eBay Draft Commander Pro
Display listing preview in embedded browser
"""
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import tempfile
import webbrowser
from typing import Dict, List, Optional
from preview_generator import PreviewGenerator


class PreviewDialog(tk.Toplevel):
    """Dialog showing listing preview"""
    
    def __init__(self, parent, listing_data: Dict, image_paths: List[str] = None):
        super().__init__(parent)
        
        self.listing_data = listing_data
        self.image_paths = image_paths or []
        self.generator = PreviewGenerator()
        self.preview_file = None
        
        # Window setup
        self.title("👁️ Listing Preview")
        self.geometry("850x700")
        self.configure(bg='#1a1a2e')
        self.resizable(True, True)
        
        self.transient(parent)
        
        self.create_widgets()
        self.generate_preview()
        
        # Center
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def create_widgets(self):
        """Create dialog widgets"""
        # Header
        header = ttk.Frame(self, style='Settings.TFrame')
        header.pack(fill=tk.X, padx=15, pady=15)
        
        ttk.Label(header, text="👁️ Listing Preview",
                 font=('Segoe UI', 14, 'bold'),
                 foreground='#00d9ff',
                 background='#1a1a2e').pack(side=tk.LEFT)
        
        # Open in browser button
        ttk.Button(header, text="🌐 Open in Browser",
                  command=self.open_in_browser).pack(side=tk.RIGHT, padx=5)
        
        # Info bar
        info_frame = ttk.Frame(self, style='Settings.TFrame')
        info_frame.pack(fill=tk.X, padx=15)
        
        self.info_label = ttk.Label(info_frame, text="Generating preview...",
                                   foreground='#888',
                                   background='#1a1a2e')
        self.info_label.pack(side=tk.LEFT)
        
        # Preview area - using text widget since tkinter doesn't have HTML rendering
        # Show a styled preview of key info instead
        preview_frame = ttk.Frame(self, style='Settings.TFrame')
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)
        
        # Create a nice preview display
        self.preview_canvas = tk.Canvas(preview_frame, bg='white', 
                                        highlightthickness=1,
                                        highlightbackground='#ddd')
        scrollbar = ttk.Scrollbar(preview_frame, orient='vertical',
                                  command=self.preview_canvas.yview)
        
        self.preview_canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.preview_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Create inner frame
        self.preview_inner = tk.Frame(self.preview_canvas, bg='white')
        self.canvas_window = self.preview_canvas.create_window(
            (0, 0), window=self.preview_inner, anchor='nw'
        )
        
        self.preview_inner.bind('<Configure>', self._on_frame_configure)
        self.preview_canvas.bind('<Configure>', self._on_canvas_configure)
        
        # Footer buttons
        footer = ttk.Frame(self, style='Settings.TFrame')
        footer.pack(fill=tk.X, padx=15, pady=15)
        
        ttk.Button(footer, text="Close",
                  command=self.on_close).pack(side=tk.RIGHT, padx=5)
    
    def _on_frame_configure(self, event):
        """Update scroll region"""
        self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox('all'))
    
    def _on_canvas_configure(self, event):
        """Resize inner frame to canvas width"""
        self.preview_canvas.itemconfig(self.canvas_window, width=event.width)
    
    def generate_preview(self):
        """Generate and display preview"""
        # Create visual preview in canvas
        self._build_preview_display()
        
        # Also generate HTML file for browser viewing
        try:
            temp_dir = Path(tempfile.gettempdir())
            self.preview_file = temp_dir / "ebay_preview.html"
            self.generator.save_preview(
                self.listing_data, 
                str(self.preview_file),
                self.image_paths
            )
            self.info_label.configure(text="Preview ready - Click 'Open in Browser' for full view")
        except Exception as e:
            self.info_label.configure(text=f"Preview error: {e}")
    
    def _build_preview_display(self):
        """Build preview display in canvas"""
        # Clear existing
        for widget in self.preview_inner.winfo_children():
            widget.destroy()
        
        # eBay-like styling
        pad = 20
        
        # Header banner
        banner = tk.Frame(self.preview_inner, bg='#3665f3', height=40)
        banner.pack(fill=tk.X)
        tk.Label(banner, text="eBay Listing Preview", 
                bg='#3665f3', fg='white',
                font=('Segoe UI', 11, 'bold')).pack(pady=10)
        
        # Content area
        content = tk.Frame(self.preview_inner, bg='white', padx=pad, pady=pad)
        content.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title = self.listing_data.get('title', 'Untitled')
        tk.Label(content, text=title,
                bg='white', fg='#191919',
                font=('Segoe UI', 16, 'bold'),
                wraplength=700, justify='left').pack(anchor='w', pady=(0, 10))
        
        # Condition badge
        condition = self.listing_data.get('condition', 'Used').replace('_', ' ').title()
        cond_frame = tk.Frame(content, bg='#f0f0f0', padx=10, pady=4)
        cond_frame.pack(anchor='w', pady=(0, 10))
        tk.Label(cond_frame, text=condition, bg='#f0f0f0',
                font=('Segoe UI', 10)).pack()
        
        # Price
        price = self.listing_data.get('price', '0.00')
        tk.Label(content, text=f"${price}",
                bg='white', fg='#191919',
                font=('Segoe UI', 24, 'bold')).pack(anchor='w', pady=(0, 20))
        
        # Buy buttons
        btn_frame = tk.Frame(content, bg='white')
        btn_frame.pack(fill=tk.X, pady=(0, 20))
        
        buy_btn = tk.Button(btn_frame, text="Buy It Now",
                           bg='#3665f3', fg='white',
                           font=('Segoe UI', 12, 'bold'),
                           relief='flat', padx=40, pady=10)
        buy_btn.pack(fill=tk.X, pady=2)
        
        cart_btn = tk.Button(btn_frame, text="Add to cart",
                            bg='white', fg='#3665f3',
                            font=('Segoe UI', 12),
                            relief='solid', padx=40, pady=10)
        cart_btn.pack(fill=tk.X, pady=2)
        
        # Shipping info
        shipping = tk.Frame(content, bg='#f8f8f8', padx=15, pady=15)
        shipping.pack(fill=tk.X, pady=(0, 20))
        tk.Label(shipping, text="📦 Shipping",
                bg='#f8f8f8', font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        shipping_text = self.listing_data.get('shipping_info', 'Standard shipping')
        tk.Label(shipping, text=shipping_text,
                bg='#f8f8f8', font=('Segoe UI', 10),
                fg='#555').pack(anchor='w')
        
        # Separator
        ttk.Separator(content, orient='horizontal').pack(fill=tk.X, pady=15)
        
        # Item specifics
        tk.Label(content, text="Item specifics",
                bg='white', font=('Segoe UI', 14, 'bold')).pack(anchor='w', pady=(0, 10))
        
        specifics = self.listing_data.get('item_specifics', {})
        if specifics:
            spec_frame = tk.Frame(content, bg='white')
            spec_frame.pack(fill=tk.X, pady=(0, 15))
            
            for key, value in specifics.items():
                row = tk.Frame(spec_frame, bg='white')
                row.pack(fill=tk.X, pady=2)
                tk.Label(row, text=key, bg='white', fg='#767676',
                        width=20, anchor='w',
                        font=('Segoe UI', 10)).pack(side=tk.LEFT)
                tk.Label(row, text=str(value), bg='white',
                        font=('Segoe UI', 10, 'bold'),
                        anchor='w').pack(side=tk.LEFT, fill=tk.X)
        else:
            tk.Label(content, text="No item specifics set",
                    bg='white', fg='#888').pack(anchor='w')
        
        # Separator
        ttk.Separator(content, orient='horizontal').pack(fill=tk.X, pady=15)
        
        # Description
        tk.Label(content, text="Item description",
                bg='white', font=('Segoe UI', 14, 'bold')).pack(anchor='w', pady=(0, 10))
        
        desc = self.listing_data.get('description', 'No description provided.')
        # Strip HTML for display
        import re
        desc_text = re.sub(r'<[^>]+>', ' ', desc)
        desc_text = ' '.join(desc_text.split())[:500]  # Limit length
        
        tk.Label(content, text=desc_text + "..." if len(desc_text) >= 500 else desc_text,
                bg='white', fg='#333',
                font=('Segoe UI', 10),
                wraplength=700, justify='left').pack(anchor='w')
        
        # Image count
        if self.image_paths:
            tk.Label(content, text=f"\n📷 {len(self.image_paths)} photos attached",
                    bg='white', fg='#888',
                    font=('Segoe UI', 10)).pack(anchor='w', pady=(15, 0))
    
    def open_in_browser(self):
        """Open full preview in browser"""
        if self.preview_file and self.preview_file.exists():
            webbrowser.open(f'file://{self.preview_file}')
    
    def on_close(self):
        """Clean up and close"""
        # Optionally delete temp file
        # if self.preview_file and self.preview_file.exists():
        #     self.preview_file.unlink()
        self.destroy()


# Test
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Test")
    root.geometry("300x200")
    root.configure(bg='#1a1a2e')
    
    def show_preview():
        listing = {
            'title': 'Xerox Sensor Part ABC123 - Excellent Working Condition',
            'price': '45.99',
            'condition': 'USED_EXCELLENT',
            'shipping_info': 'Free shipping, ships within 1 business day',
            'item_specifics': {
                'Brand': 'Xerox',
                'Model': 'ABC123',
                'Type': 'Sensor',
                'Condition': 'Used - Excellent',
            },
            'description': '''
                <h2>Product Overview</h2>
                <p>This is a genuine Xerox sensor in excellent used condition. 
                Perfect for replacing worn or damaged sensors in compatible Xerox printers.</p>
                
                <h2>Features</h2>
                <ul>
                    <li>Original Xerox part</li>
                    <li>Tested and working</li>
                    <li>Clean and ready to install</li>
                </ul>
            '''
        }
        
        dialog = PreviewDialog(root, listing)
        root.wait_window(dialog)
    
    ttk.Button(root, text="Show Preview", command=show_preview).pack(pady=50)
    root.mainloop()
