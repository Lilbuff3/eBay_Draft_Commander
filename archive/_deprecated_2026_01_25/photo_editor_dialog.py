"""
Photo Editor Dialog for eBay Draft Commander Pro
UI for editing listing photos with preview
"""
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from pathlib import Path
from typing import List, Optional
from photo_editor import PhotoEditor


class PhotoEditorDialog(tk.Toplevel):
    """Photo editor dialog with preview and controls"""
    
    def __init__(self, parent, image_paths: List[str]):
        super().__init__(parent)
        
        self.image_paths = [Path(p) for p in image_paths]
        self.current_index = 0
        self.editors: List[PhotoEditor] = []
        self.result = False  # True if saved
        
        # Window setup
        self.title("🖼️ Photo Editor")
        self.geometry("900x650")
        self.configure(bg='#1a1a2e')
        self.resizable(True, True)
        
        self.transient(parent)
        self.grab_set()
        
        # Load all images
        self.load_images()
        
        # Create UI
        self.create_widgets()
        
        # Show first image
        self.show_current()
        
        # Center
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
    
    def load_images(self):
        """Load all images into editors"""
        for path in self.image_paths:
            try:
                editor = PhotoEditor(str(path))
                self.editors.append(editor)
            except Exception as e:
                print(f"Could not load {path}: {e}")
    
    def create_widgets(self):
        """Create editor UI"""
        # Main layout: toolbar on left, preview in center, thumbnails on right
        main = ttk.Frame(self, style='Settings.TFrame')
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left toolbar
        toolbar = ttk.Frame(main, style='Settings.TFrame', width=120)
        toolbar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        toolbar.pack_propagate(False)
        
        # Toolbar sections
        self.create_toolbar(toolbar)
        
        # Center preview
        preview_frame = ttk.Frame(main, style='Settings.TFrame')
        preview_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Preview label
        self.preview_label = tk.Label(preview_frame, bg='#0f0f23')
        self.preview_label.pack(fill=tk.BOTH, expand=True)
        
        # Info bar
        info_frame = ttk.Frame(preview_frame, style='Settings.TFrame')
        info_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.info_label = ttk.Label(info_frame, text="", 
                                   foreground='#888', background='#1a1a2e')
        self.info_label.pack(side=tk.LEFT)
        
        self.index_label = ttk.Label(info_frame, text="1/1",
                                    foreground='#00d9ff', background='#1a1a2e')
        self.index_label.pack(side=tk.RIGHT)
        
        # Right thumbnails
        thumb_frame = ttk.Frame(main, style='Settings.TFrame', width=120)
        thumb_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        thumb_frame.pack_propagate(False)
        
        ttk.Label(thumb_frame, text="Photos", foreground='#ffd700',
                 background='#1a1a2e', font=('Segoe UI', 10, 'bold')).pack(pady=5)
        
        # Thumbnail canvas with scroll
        self.thumb_canvas = tk.Canvas(thumb_frame, bg='#16213e', 
                                      highlightthickness=0, width=100)
        self.thumb_canvas.pack(fill=tk.BOTH, expand=True)
        
        self.thumb_frame_inner = ttk.Frame(self.thumb_canvas, style='Settings.TFrame')
        self.thumb_canvas.create_window((0, 0), window=self.thumb_frame_inner, anchor='nw')
        
        self.create_thumbnails()
        
        # Bottom buttons
        btn_frame = ttk.Frame(self, style='Settings.TFrame')
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(btn_frame, text="Cancel", command=self.on_cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="💾 Save All", command=self.on_save).pack(side=tk.RIGHT, padx=5)
        
        # Navigation
        ttk.Button(btn_frame, text="◀ Prev", command=self.prev_image).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Next ▶", command=self.next_image).pack(side=tk.LEFT, padx=5)
    
    def create_toolbar(self, parent):
        """Create the editing toolbar"""
        # Title
        ttk.Label(parent, text="Tools", foreground='#ffd700',
                 background='#1a1a2e', font=('Segoe UI', 10, 'bold')).pack(pady=10)
        
        # Rotation section
        section = ttk.LabelFrame(parent, text="Rotate")
        section.pack(fill=tk.X, pady=5, padx=5)
        
        btn_row = ttk.Frame(section)
        btn_row.pack(fill=tk.X, pady=5)
        ttk.Button(btn_row, text="↺", width=3, command=self.rotate_left).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="↻", width=3, command=self.rotate_right).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="⇆", width=3, command=self.flip_h).pack(side=tk.LEFT, padx=2)
        
        # Crop section
        section = ttk.LabelFrame(parent, text="Crop")
        section.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Button(section, text="Square", width=10, command=self.crop_square).pack(pady=2)
        ttk.Button(section, text="Auto Crop", width=10, command=self.auto_crop).pack(pady=2)
        
        # Enhance section
        section = ttk.LabelFrame(parent, text="Enhance")
        section.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Button(section, text="Auto ✨", width=10, command=self.auto_enhance).pack(pady=2)
        ttk.Button(section, text="Sharpen", width=10, command=self.sharpen).pack(pady=2)
        
        # Brightness slider
        ttk.Label(section, text="Brightness").pack(pady=(5, 0))
        self.brightness_var = tk.DoubleVar(value=1.0)
        brightness_scale = ttk.Scale(section, from_=0.5, to=1.5, 
                                     variable=self.brightness_var,
                                     command=self.update_brightness)
        brightness_scale.pack(fill=tk.X, padx=5)
        
        # Contrast slider
        ttk.Label(section, text="Contrast").pack(pady=(5, 0))
        self.contrast_var = tk.DoubleVar(value=1.0)
        contrast_scale = ttk.Scale(section, from_=0.5, to=1.5,
                                   variable=self.contrast_var,
                                   command=self.update_contrast)
        contrast_scale.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        # Undo/Reset
        section = ttk.LabelFrame(parent, text="History")
        section.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Button(section, text="↩ Undo", width=10, command=self.undo).pack(pady=2)
        ttk.Button(section, text="🔄 Reset", width=10, command=self.reset).pack(pady=2)
        
        # eBay optimization
        section = ttk.LabelFrame(parent, text="eBay")
        section.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Button(section, text="Optimize", width=10, command=self.optimize_for_ebay).pack(pady=2)
    
    def create_thumbnails(self):
        """Create thumbnail strip"""
        for widget in self.thumb_frame_inner.winfo_children():
            widget.destroy()
        
        self.thumb_labels = []
        
        for i, editor in enumerate(self.editors):
            try:
                thumb = editor.get_thumbnail((80, 80))
                if thumb:
                    photo = ImageTk.PhotoImage(thumb)
                    
                    label = tk.Label(self.thumb_frame_inner, image=photo,
                                    bg='#16213e', cursor='hand2')
                    label.image = photo
                    label.pack(pady=5)
                    label.bind('<Button-1>', lambda e, idx=i: self.select_image(idx))
                    
                    self.thumb_labels.append(label)
            except:
                pass
    
    def show_current(self):
        """Display current image in preview"""
        if not self.editors:
            return
        
        editor = self.editors[self.current_index]
        img = editor.get_current()
        
        if not img:
            return
        
        # Resize for preview
        preview = img.copy()
        preview.thumbnail((600, 500), Image.Resampling.LANCZOS)
        
        photo = ImageTk.PhotoImage(preview)
        self.preview_label.configure(image=photo)
        self.preview_label.image = photo
        
        # Update info
        width, height = editor.get_size()
        self.info_label.configure(text=f"{width} × {height} px")
        self.index_label.configure(text=f"{self.current_index + 1}/{len(self.editors)}")
        
        # Highlight current thumbnail
        for i, label in enumerate(self.thumb_labels):
            if i == self.current_index:
                label.configure(relief='solid', borderwidth=2)
            else:
                label.configure(relief='flat', borderwidth=0)
    
    def select_image(self, index: int):
        """Select image by index"""
        self.current_index = index
        self.brightness_var.set(1.0)
        self.contrast_var.set(1.0)
        self.show_current()
    
    def prev_image(self):
        """Show previous image"""
        if self.current_index > 0:
            self.select_image(self.current_index - 1)
    
    def next_image(self):
        """Show next image"""
        if self.current_index < len(self.editors) - 1:
            self.select_image(self.current_index + 1)
    
    # Operation handlers
    def rotate_left(self):
        if self.editors:
            self.editors[self.current_index].rotate_left()
            self.show_current()
    
    def rotate_right(self):
        if self.editors:
            self.editors[self.current_index].rotate_right()
            self.show_current()
    
    def flip_h(self):
        if self.editors:
            self.editors[self.current_index].flip_horizontal()
            self.show_current()
    
    def crop_square(self):
        if self.editors:
            self.editors[self.current_index].crop_square()
            self.show_current()
    
    def auto_crop(self):
        if self.editors:
            self.editors[self.current_index].auto_crop(border=10)
            self.show_current()
    
    def auto_enhance(self):
        if self.editors:
            self.editors[self.current_index].auto_enhance()
            self.show_current()
    
    def sharpen(self):
        if self.editors:
            self.editors[self.current_index].sharpen()
            self.show_current()
    
    def update_brightness(self, value):
        if self.editors:
            editor = self.editors[self.current_index]
            # Reset and apply new brightness
            editor.reset()
            editor.brightness(float(value))
            editor.contrast(self.contrast_var.get())
            self.show_current()
    
    def update_contrast(self, value):
        if self.editors:
            editor = self.editors[self.current_index]
            editor.reset()
            editor.brightness(self.brightness_var.get())
            editor.contrast(float(value))
            self.show_current()
    
    def undo(self):
        if self.editors:
            self.editors[self.current_index].undo()
            self.show_current()
    
    def reset(self):
        if self.editors:
            self.editors[self.current_index].reset()
            self.brightness_var.set(1.0)
            self.contrast_var.set(1.0)
            self.show_current()
    
    def optimize_for_ebay(self):
        """Apply eBay optimization to all images"""
        for editor in self.editors:
            editor.resize_for_ebay()
            editor.auto_enhance()
        self.show_current()
        self.create_thumbnails()
        messagebox.showinfo("Optimized", f"Optimized {len(self.editors)} images for eBay")
    
    def on_save(self):
        """Save all edited images"""
        saved = 0
        for editor in self.editors:
            try:
                editor.save()
                saved += 1
            except Exception as e:
                print(f"Error saving: {e}")
        
        self.result = True
        messagebox.showinfo("Saved", f"Saved {saved} images")
        self.destroy()
    
    def on_cancel(self):
        """Cancel without saving"""
        self.result = False
        self.destroy()


# Test
if __name__ == "__main__":
    from PIL import Image
    
    # Create test images
    test_dir = Path(__file__).parent / "test_photos"
    test_dir.mkdir(exist_ok=True)
    
    for i in range(3):
        img = Image.new('RGB', (400, 300), color=['red', 'green', 'blue'][i])
        img.save(test_dir / f"test_{i}.jpg")
    
    root = tk.Tk()
    root.title("Test")
    root.geometry("200x100")
    
    def open_editor():
        paths = list(test_dir.glob("*.jpg"))
        dialog = PhotoEditorDialog(root, [str(p) for p in paths])
        root.wait_window(dialog)
        print(f"Result: {dialog.result}")
        
        # Cleanup
        for p in test_dir.glob("*.jpg"):
            p.unlink()
        test_dir.rmdir()
    
    ttk.Button(root, text="Open Editor", command=open_editor).pack(pady=30)
    root.mainloop()
