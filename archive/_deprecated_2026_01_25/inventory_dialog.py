"""
Inventory Sync Dialog for eBay Draft Commander Pro
UI for syncing and viewing eBay inventory
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from threading import Thread
from typing import Optional
from inventory_sync import InventorySync, get_inventory_sync


class InventorySyncDialog(tk.Toplevel):
    """Dialog for syncing and viewing eBay inventory"""
    
    def __init__(self, parent, sync: InventorySync = None):
        super().__init__(parent)
        
        self.sync = sync or get_inventory_sync()
        self._syncing = False
        
        # Window setup
        self.title("📦 Inventory Sync")
        self.geometry("700x550")
        self.configure(bg='#1a1a2e')
        self.resizable(True, True)
        
        self.transient(parent)
        
        self.create_widgets()
        self.refresh_display()
        
        # Center
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
    
    def create_widgets(self):
        """Create dialog widgets"""
        main = ttk.Frame(self, style='Settings.TFrame', padding=15)
        main.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header = ttk.Frame(main, style='Settings.TFrame')
        header.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(header, text="📦 eBay Inventory",
                 font=('Segoe UI', 14, 'bold'),
                 foreground='#00d9ff',
                 background='#1a1a2e').pack(side=tk.LEFT)
        
        ttk.Button(header, text="🔄 Sync Now",
                  command=self.start_sync).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header, text="📥 Export CSV",
                  command=self.export_csv).pack(side=tk.RIGHT, padx=5)
        
        # Stats bar
        stats_frame = ttk.Frame(main, style='Settings.TFrame')
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.stats_label = ttk.Label(stats_frame, text="Loading...",
                                    foreground='#888',
                                    background='#1a1a2e')
        self.stats_label.pack(side=tk.LEFT)
        
        self.sync_time_label = ttk.Label(stats_frame, text="",
                                        foreground='#888',
                                        background='#1a1a2e')
        self.sync_time_label.pack(side=tk.RIGHT)
        
        # Progress bar (hidden initially)
        self.progress_frame = ttk.Frame(main, style='Settings.TFrame')
        
        self.progress_label = ttk.Label(self.progress_frame, text="Syncing...",
                                       foreground='#ffd700',
                                       background='#1a1a2e')
        self.progress_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.progress_bar = ttk.Progressbar(self.progress_frame, mode='determinate',
                                           length=300)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Search
        search_frame = ttk.Frame(main, style='Settings.TFrame')
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(search_frame, text="🔍", background='#1a1a2e').pack(side=tk.LEFT)
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search)
        
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var,
                                font=('Segoe UI', 10), width=30)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Listings list
        list_frame = ttk.Frame(main, style='Settings.TFrame')
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Treeview for listings
        columns = ('title', 'price', 'qty', 'status')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings',
                                height=15)
        
        self.tree.heading('title', text='Title')
        self.tree.heading('price', text='Price')
        self.tree.heading('qty', text='Qty')
        self.tree.heading('status', text='Status')
        
        self.tree.column('title', width=350)
        self.tree.column('price', width=80, anchor='e')
        self.tree.column('qty', width=50, anchor='center')
        self.tree.column('status', width=80, anchor='center')
        
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical',
                                  command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Double-click to view
        self.tree.bind('<Double-1>', self.on_item_double_click)
        
        # Footer
        footer = ttk.Frame(main, style='Settings.TFrame')
        footer.pack(fill=tk.X, pady=(15, 0))
        
        ttk.Button(footer, text="Close",
                  command=self.destroy).pack(side=tk.RIGHT)
    
    def refresh_display(self):
        """Refresh listings display"""
        # Update stats
        stats = self.sync.get_stats()
        self.stats_label.configure(
            text=f"📊 {stats['count']} listings | 💰 Total Value: ${stats['total_value']:,.2f} | 📈 Avg: ${stats['avg_price']:.2f}"
        )
        
        # Update sync time
        last_sync = stats.get('last_sync')
        if last_sync:
            # Parse and format
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(last_sync)
                formatted = dt.strftime("%b %d, %Y %I:%M %p")
                self.sync_time_label.configure(text=f"Last sync: {formatted}")
            except:
                self.sync_time_label.configure(text=f"Last sync: {last_sync[:16]}")
        else:
            self.sync_time_label.configure(text="Never synced")
        
        # Update tree
        self.update_tree(self.sync.get_listings())
    
    def update_tree(self, listings):
        """Update treeview with listings"""
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add listings
        for listing in listings:
            self.tree.insert('', 'end', values=(
                listing.get('title', 'Unknown')[:50],
                f"${listing.get('price', 0):.2f}",
                listing.get('quantity', 1),
                listing.get('status', 'Unknown'),
            ), tags=(listing.get('listing_id', ''),))
    
    def on_search(self, *args):
        """Handle search"""
        query = self.search_var.get().strip()
        
        if query:
            results = self.sync.search_listings(query)
        else:
            results = self.sync.get_listings()
        
        self.update_tree(results)
    
    def on_item_double_click(self, event):
        """Handle double-click on item"""
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            values = item.get('values', [])
            if values:
                messagebox.showinfo("Listing Details", 
                                   f"Title: {values[0]}\nPrice: {values[1]}\nQuantity: {values[2]}\nStatus: {values[3]}")
    
    def start_sync(self):
        """Start sync in background"""
        if self._syncing:
            return
        
        self._syncing = True
        
        # Show progress
        self.progress_frame.pack(fill=tk.X, pady=(0, 10), after=self.stats_label.master)
        self.progress_bar['value'] = 0
        self.progress_label.configure(text="Syncing...")
        
        # Run in thread
        thread = Thread(target=self._do_sync, daemon=True)
        thread.start()
    
    def _do_sync(self):
        """Perform sync (in background thread)"""
        try:
            def progress(current, total):
                pct = (current / total) * 100 if total > 0 else 0
                self.after(0, lambda: self._update_progress(pct, current, total))
            
            self.sync.fetch_active_listings(limit=100, progress_callback=progress)
            
            self.after(0, self._sync_complete)
            
        except Exception as e:
            self.after(0, lambda: self._sync_error(str(e)))
    
    def _update_progress(self, pct, current, total):
        """Update progress bar"""
        self.progress_bar['value'] = pct
        self.progress_label.configure(text=f"Syncing... {current}/{total}")
    
    def _sync_complete(self):
        """Handle sync completion"""
        self._syncing = False
        self.progress_frame.pack_forget()
        self.refresh_display()
        messagebox.showinfo("Sync Complete", 
                           f"Synced {self.sync.get_listing_count()} listings")
    
    def _sync_error(self, error: str):
        """Handle sync error"""
        self._syncing = False
        self.progress_frame.pack_forget()
        messagebox.showerror("Sync Error", f"Failed to sync: {error}")
    
    def export_csv(self):
        """Export to CSV file"""
        if not self.sync.get_listings():
            messagebox.showwarning("No Data", "No listings to export")
            return
        
        filepath = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV files', '*.csv')],
            initialfilename='ebay_inventory.csv'
        )
        
        if filepath:
            try:
                self.sync.export_csv(filepath)
                messagebox.showinfo("Exported", f"Exported to {filepath}")
            except Exception as e:
                messagebox.showerror("Export Error", str(e))


# Test
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Test")
    root.geometry("300x200")
    root.configure(bg='#1a1a2e')
    
    def show_sync():
        dialog = InventorySyncDialog(root)
        root.wait_window(dialog)
    
    ttk.Button(root, text="Open Inventory Sync", command=show_sync).pack(pady=50)
    root.mainloop()
