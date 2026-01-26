"""
Price Chart Widget for eBay Draft Commander Pro
Display price research data with visual chart
"""
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional


class PriceChartDialog(tk.Toplevel):
    """Dialog showing price research results with chart"""
    
    def __init__(self, parent, research_data: Dict):
        super().__init__(parent)
        
        self.data = research_data
        
        # Window setup
        self.title("📊 Price Research")
        self.geometry("600x500")
        self.configure(bg='#1a1a2e')
        self.resizable(True, True)
        
        self.transient(parent)
        self.grab_set()
        
        self.create_widgets()
        
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
        
        ttk.Label(header, text="📊 Price Research Results",
                 font=('Segoe UI', 14, 'bold'),
                 foreground='#00d9ff',
                 background='#1a1a2e').pack(side=tk.LEFT)
        
        ttk.Label(header, text=f"Query: {self.data.get('query', 'N/A')}",
                 foreground='#888',
                 background='#1a1a2e').pack(side=tk.RIGHT)
        
        # Stats cards
        stats_frame = ttk.Frame(main, style='Settings.TFrame')
        stats_frame.pack(fill=tk.X, pady=10)
        
        stats = [
            ("📈 Average", f"${self.data.get('average', 0):.2f}", '#00d9ff'),
            ("📊 Median", f"${self.data.get('median', 0):.2f}", '#ffd700'),
            ("📉 Min", f"${self.data.get('min', 0):.2f}", '#888'),
            ("📈 Max", f"${self.data.get('max', 0):.2f}", '#888'),
            ("💰 Suggested", f"${self.data.get('suggested', 0):.2f}", '#00ff00'),
        ]
        
        for label, value, color in stats:
            card = tk.Frame(stats_frame, bg='#16213e', padx=15, pady=10)
            card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=3)
            
            tk.Label(card, text=label, bg='#16213e', fg='#888',
                    font=('Segoe UI', 9)).pack()
            tk.Label(card, text=value, bg='#16213e', fg=color,
                    font=('Segoe UI', 14, 'bold')).pack()
        
        # Chart (simple bar chart using Canvas)
        chart_frame = ttk.LabelFrame(main, text="Price Distribution")
        chart_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.chart_canvas = tk.Canvas(chart_frame, bg='#0f0f23', 
                                      highlightthickness=0, height=150)
        self.chart_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Draw chart after canvas is sized
        self.after(100, self.draw_chart)
        
        # Sample items
        items_frame = ttk.LabelFrame(main, text="Similar Items")
        items_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Items list
        items_list = tk.Listbox(items_frame, bg='#16213e', fg='white',
                               font=('Segoe UI', 10), height=5,
                               selectbackground='#00d9ff')
        items_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        items = self.data.get('items', [])
        for item in items[:8]:
            price = item.get('price', 0)
            title = item.get('title', 'Unknown')[:50]
            items_list.insert(tk.END, f"${price:.2f} - {title}")
        
        if not items:
            items_list.insert(tk.END, "(No similar items found)")
        
        # Close button
        ttk.Button(main, text="Close", command=self.destroy).pack(pady=10)
    
    def draw_chart(self):
        """Draw the price distribution chart"""
        self.chart_canvas.delete('all')
        
        price_range = self.data.get('price_range', [])
        if not price_range:
            self.chart_canvas.create_text(
                self.chart_canvas.winfo_width() // 2,
                self.chart_canvas.winfo_height() // 2,
                text="No price data available",
                fill='#888', font=('Segoe UI', 12)
            )
            return
        
        canvas_width = self.chart_canvas.winfo_width()
        canvas_height = self.chart_canvas.winfo_height()
        
        if canvas_width < 50 or canvas_height < 50:
            return
        
        # Chart area
        margin = 40
        chart_left = margin
        chart_right = canvas_width - margin
        chart_top = 20
        chart_bottom = canvas_height - 30
        chart_width = chart_right - chart_left
        chart_height = chart_bottom - chart_top
        
        # Get max count for scaling
        max_count = max(item['count'] for item in price_range)
        if max_count == 0:
            max_count = 1
        
        # Bar width
        num_bars = len(price_range)
        bar_width = (chart_width / num_bars) * 0.8
        bar_gap = (chart_width / num_bars) * 0.2
        
        # Draw bars
        for i, item in enumerate(price_range):
            bar_height = (item['count'] / max_count) * chart_height
            
            x1 = chart_left + i * (bar_width + bar_gap)
            y1 = chart_bottom - bar_height
            x2 = x1 + bar_width
            y2 = chart_bottom
            
            # Gradient effect using color
            color = self._get_gradient_color(i, num_bars)
            
            self.chart_canvas.create_rectangle(
                x1, y1, x2, y2,
                fill=color, outline='#16213e'
            )
            
            # Price label
            if i % max(1, num_bars // 5) == 0:  # Show every nth label
                self.chart_canvas.create_text(
                    (x1 + x2) / 2, chart_bottom + 15,
                    text=f"${item['price']:.0f}",
                    fill='#888', font=('Segoe UI', 8)
                )
    
    def _get_gradient_color(self, index: int, total: int) -> str:
        """Generate gradient color from cyan to gold"""
        # Interpolate between #00d9ff and #ffd700
        ratio = index / max(1, total - 1)
        
        r1, g1, b1 = 0x00, 0xd9, 0xff  # Cyan
        r2, g2, b2 = 0xff, 0xd7, 0x00  # Gold
        
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        
        return f'#{r:02x}{g:02x}{b:02x}'


class QuickPriceWidget(ttk.Frame):
    """Compact price suggestion widget for embedding"""
    
    def __init__(self, parent, on_research_click=None):
        super().__init__(parent, style='Settings.TFrame')
        
        self.on_research_click = on_research_click
        
        # Price display
        self.price_label = ttk.Label(self, text="Suggested: --",
                                    foreground='#00ff00',
                                    background='#1a1a2e',
                                    font=('Segoe UI', 10))
        self.price_label.pack(side=tk.LEFT, padx=5)
        
        # Research button
        ttk.Button(self, text="📊 Research",
                  command=self._on_click).pack(side=tk.LEFT, padx=5)
    
    def set_price(self, price: float):
        """Update displayed price"""
        self.price_label.configure(text=f"Suggested: ${price:.2f}")
    
    def _on_click(self):
        if self.on_research_click:
            self.on_research_click()


# Test
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Test")
    root.geometry("300x200")
    root.configure(bg='#1a1a2e')
    
    # Mock research data
    mock_data = {
        'query': 'xerox sensor',
        'count': 25,
        'average': 45.50,
        'median': 42.00,
        'min': 15.00,
        'max': 89.99,
        'suggested': 39.99,
        'price_range': [
            {'price': 15, 'count': 2},
            {'price': 25, 'count': 5},
            {'price': 35, 'count': 8},
            {'price': 45, 'count': 6},
            {'price': 55, 'count': 3},
            {'price': 65, 'count': 1},
        ],
        'items': [
            {'price': 45.00, 'title': 'Xerox Sensor Part ABC123'},
            {'price': 39.99, 'title': 'Xerox Transfer Sensor XYZ'},
            {'price': 52.00, 'title': 'Sensor Assembly Xerox 7800'},
        ]
    }
    
    def show_chart():
        dialog = PriceChartDialog(root, mock_data)
        root.wait_window(dialog)
    
    ttk.Button(root, text="Show Price Chart", command=show_chart).pack(pady=50)
    
    root.mainloop()
