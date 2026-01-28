"""
Custom UI Widgets for eBay Draft Commander Pro
Bento Layout Components with Natural Theme
"""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from pathlib import Path
from typing import Callable, Optional, List, Dict
from enum import Enum


# =============================================================================
# Theme Colors (Natural Palette)
# =============================================================================

class Theme:
    """Natural theme color constants"""
    ALABASTER = '#FAFAF9'      # Background
    WHITE = '#FFFFFF'           # Surface/Cards
    SAGE_GREEN = '#4D7C5D'     # Primary actions
    SAGE_DARK = '#3D6349'      # Primary hover
    WARM_CLAY = '#D97757'      # Alerts/warnings
    CHARCOAL = '#374151'       # Text
    SAND = '#E5E7EB'           # Borders/dividers
    BEIGE = '#F5F5F0'          # Sidebar
    MUTED_GOLD = '#C9A227'     # Processing/warning
    LIGHT_GRAY = '#9CA3AF'     # Secondary text
    
    # Status colors
    STATUS_READY = SAGE_GREEN
    STATUS_PROCESSING = MUTED_GOLD
    STATUS_ERROR = WARM_CLAY
    STATUS_PENDING = LIGHT_GRAY


# =============================================================================
# Stage Indicator Widget
# =============================================================================

class WorkflowStage(Enum):
    """Listing workflow stages"""
    IMPORT = 0
    ANALYZE = 1
    EDIT = 2
    PRICE = 3
    POST = 4


class StageIndicator(ttk.Frame):
    """
    Visual pipeline showing workflow stages:
    ●━━━○━━━○━━━○━━━○
    Import → Analyze → Edit → Price → Post
    """
    
    STAGE_LABELS = ['Import', 'Analyze', 'Edit', 'Price', 'Post']
    STAGE_ICONS = ['📥', '🤖', '✏️', '💰', '📤']
    
    def __init__(self, parent, on_stage_click: Callable = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(style='TFrame')
        
        self.current_stage = WorkflowStage.IMPORT
        self.on_stage_click = on_stage_click
        self.stage_buttons = []
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create the stage indicator UI"""
        container = ttk.Frame(self)
        container.pack(pady=10)
        
        for i, (label, icon) in enumerate(zip(self.STAGE_LABELS, self.STAGE_ICONS)):
            # Stage dot/button
            stage_frame = ttk.Frame(container)
            stage_frame.pack(side=tk.LEFT, padx=5)
            
            # Create a canvas for the circle indicator
            canvas = tk.Canvas(stage_frame, width=40, height=40, 
                             bg=Theme.ALABASTER, highlightthickness=0)
            canvas.pack()
            
            # Draw circle
            is_current = (i == self.current_stage.value)
            fill_color = Theme.SAGE_GREEN if is_current else Theme.SAND
            
            circle_id = canvas.create_oval(5, 5, 35, 35, fill=fill_color, 
                                          outline=Theme.SAGE_GREEN, width=2)
            
            # Draw icon text
            text_id = canvas.create_text(20, 20, text=icon, font=('Segoe UI', 12))
            
            # Store references
            canvas.circle_id = circle_id
            canvas.text_id = text_id
            canvas.stage_index = i
            
            # Bind click
            canvas.bind('<Button-1>', lambda e, idx=i: self._on_click(idx))
            canvas.bind('<Enter>', lambda e, c=canvas: self._on_hover(c, True))
            canvas.bind('<Leave>', lambda e, c=canvas: self._on_hover(c, False))
            
            self.stage_buttons.append(canvas)
            
            # Label below
            lbl = ttk.Label(stage_frame, text=label, font=('Segoe UI', 9),
                          foreground=Theme.CHARCOAL if is_current else Theme.LIGHT_GRAY)
            lbl.pack()
            
            # Connector line (except last)
            if i < len(self.STAGE_LABELS) - 1:
                connector = tk.Canvas(container, width=30, height=2,
                                     bg=Theme.ALABASTER, highlightthickness=0)
                connector.create_line(0, 1, 30, 1, fill=Theme.SAND, width=2)
                connector.pack(side=tk.LEFT, pady=15)
    
    def _on_click(self, stage_index: int):
        """Handle stage click"""
        if self.on_stage_click:
            self.on_stage_click(WorkflowStage(stage_index))
    
    def _on_hover(self, canvas, entering: bool):
        """Handle hover effect"""
        if entering:
            canvas.configure(cursor='hand2')
        else:
            canvas.configure(cursor='')
    
    def set_stage(self, stage: WorkflowStage):
        """Update the current stage indicator"""
        self.current_stage = stage
        
        for i, canvas in enumerate(self.stage_buttons):
            is_current = (i == stage.value)
            is_completed = (i < stage.value)
            
            if is_current:
                fill = Theme.SAGE_GREEN
            elif is_completed:
                fill = Theme.SAGE_GREEN
            else:
                fill = Theme.SAND
            
            canvas.itemconfig(canvas.circle_id, fill=fill)


# =============================================================================
# Queue Card Widget
# =============================================================================

class QueueCard(ttk.Frame):
    """
    Visual card for queue items with thumbnail
    ┌──────────┐
    │  [img]   │
    │ Title    │
    │   ✅     │
    └──────────┘
    """
    
    STATUS_ICONS = {
        'pending': ('⏳', Theme.STATUS_PENDING),
        'processing': ('⚙️', Theme.STATUS_PROCESSING),
        'completed': ('✅', Theme.STATUS_READY),
        'failed': ('❌', Theme.STATUS_ERROR),
        'ready': ('✅', Theme.STATUS_READY),
    }
    
    def __init__(self, parent, name: str, folder_path: str, status: str = 'pending',
                 on_click: Callable = None, thumbnail_size: int = 80, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.name = name
        self.folder_path = folder_path
        self.status = status
        self.on_click = on_click
        self.thumbnail_size = thumbnail_size
        self.is_selected = False
        self.photo_image = None  # Keep reference
        
        self._create_widgets()
        self._load_thumbnail()
    
    def _create_widgets(self):
        """Create the card UI"""
        # Card container with border
        self.card = tk.Frame(self, bg=Theme.WHITE, 
                            highlightthickness=1,
                            highlightbackground=Theme.SAND,
                            highlightcolor=Theme.SAGE_GREEN)
        self.card.pack(fill=tk.X, padx=5, pady=3)
        
        # Content frame
        content = tk.Frame(self.card, bg=Theme.WHITE)
        content.pack(fill=tk.X, padx=8, pady=8)
        
        # Thumbnail canvas
        self.thumb_canvas = tk.Canvas(content, width=self.thumbnail_size, 
                                      height=self.thumbnail_size,
                                      bg=Theme.SAND, highlightthickness=0)
        self.thumb_canvas.pack(side=tk.LEFT, padx=(0, 10))
        
        # Text info
        info_frame = tk.Frame(content, bg=Theme.WHITE)
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Name label (truncated)
        display_name = self.name[:20] + '...' if len(self.name) > 20 else self.name
        self.name_label = tk.Label(info_frame, text=display_name,
                                  font=('Segoe UI', 10, 'bold'),
                                  bg=Theme.WHITE, fg=Theme.CHARCOAL,
                                  anchor='w')
        self.name_label.pack(fill=tk.X)
        
        # Status with icon
        icon, color = self.STATUS_ICONS.get(self.status, ('❓', Theme.LIGHT_GRAY))
        self.status_label = tk.Label(info_frame, text=f"{icon} {self.status.title()}",
                                    font=('Segoe UI', 9),
                                    bg=Theme.WHITE, fg=color,
                                    anchor='w')
        self.status_label.pack(fill=tk.X, pady=(2, 0))
        
        # Bind click events to all widgets
        for widget in [self.card, content, self.thumb_canvas, 
                      info_frame, self.name_label, self.status_label]:
            widget.bind('<Button-1>', self._on_click)
            widget.bind('<Enter>', lambda e: self._on_hover(True))
            widget.bind('<Leave>', lambda e: self._on_hover(False))
    
    def _load_thumbnail(self):
        """Load first image from folder as thumbnail"""
        try:
            folder = Path(self.folder_path)
            if folder.exists():
                # Find first image
                for ext in ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG']:
                    images = list(folder.glob(ext))
                    if images:
                        img = Image.open(images[0])
                        # Crop to square and resize
                        size = min(img.size)
                        left = (img.width - size) // 2
                        top = (img.height - size) // 2
                        img = img.crop((left, top, left + size, top + size))
                        img = img.resize((self.thumbnail_size, self.thumbnail_size), 
                                        Image.Resampling.LANCZOS)
                        
                        self.photo_image = ImageTk.PhotoImage(img)
                        self.thumb_canvas.create_image(
                            self.thumbnail_size // 2, 
                            self.thumbnail_size // 2,
                            image=self.photo_image
                        )
                        return
            
            # No image found - show placeholder
            self.thumb_canvas.create_text(
                self.thumbnail_size // 2,
                self.thumbnail_size // 2,
                text='📷',
                font=('Segoe UI', 24)
            )
        except Exception as e:
            print(f"Thumbnail error: {e}")
    
    def _on_click(self, event):
        """Handle card click"""
        if self.on_click:
            self.on_click(self)
    
    def _on_hover(self, entering: bool):
        """Handle hover effect"""
        if entering and not self.is_selected:
            self.card.configure(highlightbackground=Theme.SAGE_GREEN)
        elif not self.is_selected:
            self.card.configure(highlightbackground=Theme.SAND)
    
    def set_selected(self, selected: bool):
        """Update selection state"""
        self.is_selected = selected
        if selected:
            self.card.configure(highlightbackground=Theme.SAGE_GREEN,
                              highlightthickness=2)
        else:
            self.card.configure(highlightbackground=Theme.SAND,
                              highlightthickness=1)
    
    def update_status(self, status: str):
        """Update the status display"""
        self.status = status
        icon, color = self.STATUS_ICONS.get(status, ('❓', Theme.LIGHT_GRAY))
        self.status_label.configure(text=f"{icon} {status.title()}", fg=color)


# =============================================================================
# Tool Card Widget
# =============================================================================

class ToolCard(ttk.Frame):
    """
    Clickable tool card with icon and description
    ┌───────────────┐
    │      📷      │
    │  Photo Editor │
    │  Edit, crop,  │
    │  enhance      │
    └───────────────┘
    """
    
    def __init__(self, parent, icon: str, title: str, description: str,
                 on_click: Callable = None, width: int = 120, **kwargs):
        super().__init__(parent, **kwargs)
        
        self.icon = icon
        self.title = title
        self.description = description
        self.on_click = on_click
        self.card_width = width
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create the tool card UI"""
        # Card container
        self.card = tk.Frame(self, bg=Theme.WHITE,
                            highlightthickness=1,
                            highlightbackground=Theme.SAND,
                            highlightcolor=Theme.SAGE_GREEN,
                            width=self.card_width)
        self.card.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.card.pack_propagate(False)
        
        # Content
        content = tk.Frame(self.card, bg=Theme.WHITE)
        content.pack(expand=True, pady=15)
        
        # Icon (large)
        icon_label = tk.Label(content, text=self.icon,
                             font=('Segoe UI', 28),
                             bg=Theme.WHITE)
        icon_label.pack()
        
        # Title
        title_label = tk.Label(content, text=self.title,
                              font=('Segoe UI', 11, 'bold'),
                              bg=Theme.WHITE, fg=Theme.CHARCOAL)
        title_label.pack(pady=(8, 4))
        
        # Description
        desc_label = tk.Label(content, text=self.description,
                             font=('Segoe UI', 9),
                             bg=Theme.WHITE, fg=Theme.LIGHT_GRAY,
                             wraplength=self.card_width - 20,
                             justify='center')
        desc_label.pack()
        
        # Bind click events
        for widget in [self.card, content, icon_label, title_label, desc_label]:
            widget.bind('<Button-1>', self._on_click)
            widget.bind('<Enter>', lambda e: self._on_hover(True))
            widget.bind('<Leave>', lambda e: self._on_hover(False))
    
    def _on_click(self, event):
        """Handle card click"""
        if self.on_click:
            self.on_click()
    
    def _on_hover(self, entering: bool):
        """Handle hover effect"""
        if entering:
            self.card.configure(highlightbackground=Theme.SAGE_GREEN,
                              highlightthickness=2)
            for widget in self.card.winfo_children():
                widget.configure(cursor='hand2')
        else:
            self.card.configure(highlightbackground=Theme.SAND,
                              highlightthickness=1)
            for widget in self.card.winfo_children():
                widget.configure(cursor='')


# =============================================================================
# Action Bar Widget
# =============================================================================

class ActionBar(ttk.Frame):
    """
    Sticky footer with primary actions and status
    ┌─────────────────────────────────────────────────────────┐
    │  [ 🚀 Start Queue ]    📊 3 pending    [ 📤 Post ]      │
    └─────────────────────────────────────────────────────────┘
    """
    
    def __init__(self, parent, on_start: Callable = None, on_post: Callable = None,
                 **kwargs):
        super().__init__(parent, **kwargs)
        
        self.on_start = on_start
        self.on_post = on_post
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create the action bar UI"""
        # Container with border on top
        container = tk.Frame(self, bg=Theme.WHITE,
                            highlightthickness=1,
                            highlightbackground=Theme.SAND)
        container.pack(fill=tk.X, pady=(10, 0))
        
        inner = tk.Frame(container, bg=Theme.WHITE)
        inner.pack(fill=tk.X, padx=20, pady=15)
        
        # Start Queue button (primary)
        self.start_btn = tk.Button(inner, text='🚀 Start Queue',
                                   font=('Segoe UI', 12, 'bold'),
                                   bg=Theme.SAGE_GREEN, fg=Theme.WHITE,
                                   activebackground=Theme.SAGE_DARK,
                                   activeforeground=Theme.WHITE,
                                   relief='flat', padx=20, pady=8,
                                   cursor='hand2',
                                   command=self.on_start)
        self.start_btn.pack(side=tk.LEFT)
        
        # Status display (center)
        self.status_frame = tk.Frame(inner, bg=Theme.WHITE)
        self.status_frame.pack(side=tk.LEFT, expand=True)
        
        self.status_label = tk.Label(self.status_frame, 
                                    text='📊 Ready to process',
                                    font=('Segoe UI', 11),
                                    bg=Theme.WHITE, fg=Theme.CHARCOAL)
        self.status_label.pack()
        
        # Post button (secondary)
        self.post_btn = tk.Button(inner, text='📤 Post to eBay',
                                  font=('Segoe UI', 11),
                                  bg=Theme.WHITE, fg=Theme.SAGE_GREEN,
                                  activebackground=Theme.SAND,
                                  relief='solid', borderwidth=1,
                                  padx=15, pady=6,
                                  cursor='hand2',
                                  command=self.on_post)
        self.post_btn.pack(side=tk.RIGHT)
    
    def update_status(self, pending: int, completed: int, failed: int):
        """Update status display"""
        text = f'📊 {pending} pending | {completed} done'
        if failed > 0:
            text += f' | {failed} failed'
        self.status_label.configure(text=text)
    
    def set_processing(self, is_processing: bool):
        """Update button states for processing"""
        if is_processing:
            self.start_btn.configure(text='⏸️ Pause', bg=Theme.MUTED_GOLD)
        else:
            self.start_btn.configure(text='🚀 Start Queue', bg=Theme.SAGE_GREEN)


# =============================================================================
# Hero Image Widget
# =============================================================================

class HeroImage(tk.Frame):
    """
    Large image preview with click to edit
    """
    
    def __init__(self, parent, size: int = 300, on_click: Callable = None, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=Theme.ALABASTER)
        
        self.size = size
        self.on_click = on_click
        self.photo_image = None
        self.image_paths = []
        self.current_index = 0
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create hero image UI"""
        # Main image canvas
        self.canvas = tk.Canvas(self, width=self.size, height=self.size,
                               bg=Theme.SAND, highlightthickness=1,
                               highlightbackground=Theme.SAND)
        self.canvas.pack()
        
        # Placeholder
        self.canvas.create_text(self.size // 2, self.size // 2,
                               text='📷\nDrop items or\nselect from queue',
                               font=('Segoe UI', 14),
                               fill=Theme.LIGHT_GRAY,
                               justify='center',
                               tags='placeholder')
        
        # Click hint
        self.hint = tk.Label(self, text='Click to edit photos',
                            font=('Segoe UI', 9),
                            bg=Theme.ALABASTER, fg=Theme.LIGHT_GRAY)
        self.hint.pack(pady=5)
        self.hint.pack_forget()  # Hide initially
        
        # Thumbnail strip (for multiple images)
        self.thumb_frame = tk.Frame(self, bg=Theme.ALABASTER)
        self.thumb_frame.pack(pady=5)
        
        # Bind click
        self.canvas.bind('<Button-1>', self._on_click)
        self.canvas.bind('<Enter>', lambda e: self.canvas.configure(cursor='hand2'))
        self.canvas.bind('<Leave>', lambda e: self.canvas.configure(cursor=''))
    
    def load_images(self, folder_path: str):
        """Load images from folder"""
        self.image_paths = []
        self.current_index = 0
        
        try:
            folder = Path(folder_path)
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG']:
                self.image_paths.extend(folder.glob(ext))
            
            if self.image_paths:
                self._show_image(0)
                self._create_thumbnails()
                self.hint.pack(pady=5)
            else:
                self._show_placeholder()
        except Exception as e:
            print(f"Hero image error: {e}")
            self._show_placeholder()
    
    def _show_image(self, index: int):
        """Display image at index"""
        if 0 <= index < len(self.image_paths):
            img = Image.open(self.image_paths[index])
            
            # Fit to canvas
            ratio = min(self.size / img.width, self.size / img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            self.photo_image = ImageTk.PhotoImage(img)
            
            self.canvas.delete('all')
            self.canvas.create_image(self.size // 2, self.size // 2,
                                    image=self.photo_image)
            self.current_index = index
    
    def _show_placeholder(self):
        """Show placeholder when no images"""
        self.canvas.delete('all')
        self.canvas.create_text(self.size // 2, self.size // 2,
                               text='📷\nNo images',
                               font=('Segoe UI', 14),
                               fill=Theme.LIGHT_GRAY,
                               justify='center')
        self.hint.pack_forget()
    
    def _create_thumbnails(self):
        """Create thumbnail strip for multiple images"""
        # Clear existing
        for widget in self.thumb_frame.winfo_children():
            widget.destroy()
        
        if len(self.image_paths) <= 1:
            return
        
        for i, path in enumerate(self.image_paths[:6]):  # Max 6 thumbnails
            try:
                img = Image.open(path)
                img.thumbnail((50, 50))
                photo = ImageTk.PhotoImage(img)
                
                lbl = tk.Label(self.thumb_frame, image=photo, 
                              bg=Theme.SAND if i == self.current_index else Theme.ALABASTER,
                              cursor='hand2')
                lbl.image = photo
                lbl.pack(side=tk.LEFT, padx=2)
                lbl.bind('<Button-1>', lambda e, idx=i: self._show_image(idx))
            except:
                pass
    
    def _on_click(self, event):
        """Handle click to open editor"""
        if self.on_click and self.image_paths:
            self.on_click([str(p) for p in self.image_paths])
    
    def clear(self):
        """Clear the display"""
        self.image_paths = []
        self._show_placeholder()


# =============================================================================
# Test
# =============================================================================

if __name__ == '__main__':
    root = tk.Tk()
    root.title("Widget Test")
    root.geometry("900x700")
    root.configure(bg=Theme.ALABASTER)
    
    # Stage Indicator
    stage = StageIndicator(root, on_stage_click=lambda s: print(f"Clicked: {s}"))
    stage.pack(pady=20)
    
    # Queue Cards
    queue_frame = tk.Frame(root, bg=Theme.BEIGE, width=200)
    queue_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10)
    
    for i in range(3):
        card = QueueCard(queue_frame, f"Test Item {i+1}",
                        str(Path(__file__).parent / "inbox"),
                        status=['pending', 'processing', 'completed'][i],
                        on_click=lambda c: print(f"Clicked: {c.name}"))
        card.pack(fill=tk.X)
    
    # Tool Cards
    tools_frame = tk.Frame(root, bg=Theme.ALABASTER)
    tools_frame.pack(side=tk.TOP, fill=tk.X, pady=20)
    
    tools = [
        ('📷', 'Photo Editor', 'Edit, crop, enhance'),
        ('💰', 'Price Research', 'Check sold prices'),
        ('👁️', 'Preview', 'See listing preview'),
        ('📋', 'Templates', 'Apply templates'),
    ]
    
    for icon, title, desc in tools:
        card = ToolCard(tools_frame, icon, title, desc,
                       on_click=lambda t=title: print(f"Tool: {t}"),
                       width=140)
        card.pack(side=tk.LEFT, padx=5)
    
    # Action Bar
    action = ActionBar(root, 
                      on_start=lambda: print("Start!"),
                      on_post=lambda: print("Post!"))
    action.pack(side=tk.BOTTOM, fill=tk.X)
    action.update_status(5, 2, 1)
    
    root.mainloop()
