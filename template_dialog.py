"""
Template Selection Dialog for eBay Draft Commander Pro
UI for saving and selecting listing templates
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from template_manager import TemplateManager, get_template_manager


class TemplateDialog(tk.Toplevel):
    """Dialog for selecting a listing template"""
    
    def __init__(self, parent, template_manager: TemplateManager = None):
        super().__init__(parent)
        
        self.template_manager = template_manager or get_template_manager()
        self.result = None  # Selected template data
        self.selected_name = None
        
        # Window setup
        self.title("📋 Listing Templates")
        self.geometry("450x400")
        self.configure(bg='#1a1a2e')
        self.resizable(True, True)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self.create_widgets()
        self.refresh_list()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
    
    def create_widgets(self):
        """Create dialog widgets"""
        # Title
        title_frame = ttk.Frame(self, style='Settings.TFrame')
        title_frame.pack(fill=tk.X, padx=15, pady=15)
        
        ttk.Label(title_frame, text="📋 Select Template",
                 font=('Segoe UI', 14, 'bold'),
                 foreground='#00d9ff',
                 background='#1a1a2e').pack(side=tk.LEFT)
        
        # Template list
        list_frame = ttk.Frame(self, style='Settings.TFrame')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=15)
        
        # Listbox with scrollbar
        self.listbox = tk.Listbox(list_frame, 
                                  font=('Segoe UI', 11),
                                  bg='#16213e', fg='white',
                                  selectbackground='#00d9ff',
                                  selectforeground='black',
                                  height=10)
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', 
                                  command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox.bind('<<ListboxSelect>>', self.on_select)
        self.listbox.bind('<Double-Button-1>', lambda e: self.on_use())
        
        # Template info
        info_frame = ttk.Frame(self, style='Settings.TFrame')
        info_frame.pack(fill=tk.X, padx=15, pady=10)
        
        self.info_label = ttk.Label(info_frame, text="Select a template",
                                   foreground='#888',
                                   background='#1a1a2e',
                                   font=('Segoe UI', 10))
        self.info_label.pack(anchor='w')
        
        # Buttons
        btn_frame = ttk.Frame(self, style='Settings.TFrame')
        btn_frame.pack(fill=tk.X, padx=15, pady=15)
        
        ttk.Button(btn_frame, text="❌ Delete",
                  command=self.on_delete).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="Cancel",
                  command=self.on_cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="✅ Use Template",
                  command=self.on_use).pack(side=tk.RIGHT, padx=5)
    
    def refresh_list(self):
        """Refresh the template list"""
        self.listbox.delete(0, tk.END)
        
        templates = self.template_manager.get_all()
        
        if not templates:
            self.listbox.insert(tk.END, "(No templates saved)")
            self.listbox.configure(state='disabled')
            return
        
        self.listbox.configure(state='normal')
        
        for template in templates:
            use_text = f" ({template.use_count}x)" if template.use_count > 0 else ""
            self.listbox.insert(tk.END, f"{template.name}{use_text}")
    
    def on_select(self, event):
        """Handle template selection"""
        selection = self.listbox.curselection()
        if not selection:
            return
        
        templates = self.template_manager.get_all()
        if selection[0] >= len(templates):
            return
        
        template = templates[selection[0]]
        self.selected_name = template.name
        
        # Show template info
        info_parts = []
        if template.data.get('condition'):
            info_parts.append(f"Condition: {template.data['condition']}")
        if template.data.get('default_price'):
            info_parts.append(f"Price: ${template.data['default_price']}")
        if template.data.get('item_specifics'):
            count = len(template.data['item_specifics'])
            info_parts.append(f"Specifics: {count}")
        
        self.info_label.configure(text=" | ".join(info_parts) if info_parts else "No details")
    
    def on_use(self):
        """Apply selected template"""
        if not self.selected_name:
            messagebox.showwarning("Select Template", "Please select a template first")
            return
        
        self.result = self.template_manager.use(self.selected_name)
        self.destroy()
    
    def on_delete(self):
        """Delete selected template"""
        if not self.selected_name:
            return
        
        if messagebox.askyesno("Delete Template", 
                              f"Delete template '{self.selected_name}'?"):
            self.template_manager.delete(self.selected_name)
            self.selected_name = None
            self.refresh_list()
    
    def on_cancel(self):
        """Cancel and close"""
        self.result = None
        self.destroy()


class SaveTemplateDialog(tk.Toplevel):
    """Dialog for saving a new template"""
    
    def __init__(self, parent, current_data: dict, template_manager: TemplateManager = None):
        super().__init__(parent)
        
        self.template_manager = template_manager or get_template_manager()
        self.current_data = current_data
        self.result = None
        
        # Window setup
        self.title("💾 Save Template")
        self.geometry("400x200")
        self.configure(bg='#1a1a2e')
        self.resizable(False, False)
        
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
        main = ttk.Frame(self, style='Settings.TFrame', padding=20)
        main.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(main, text="💾 Save as Template",
                 font=('Segoe UI', 14, 'bold'),
                 foreground='#00d9ff',
                 background='#1a1a2e').pack(anchor='w', pady=(0, 15))
        
        # Name entry
        ttk.Label(main, text="Template Name:",
                 foreground='white',
                 background='#1a1a2e').pack(anchor='w')
        
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(main, textvariable=self.name_var,
                                    font=('Segoe UI', 11), width=40)
        self.name_entry.pack(fill=tk.X, pady=5)
        self.name_entry.focus()
        
        # What will be saved
        saved_items = []
        if self.current_data.get('condition'):
            saved_items.append('condition')
        if self.current_data.get('price'):
            saved_items.append('price')
        if self.current_data.get('item_specifics'):
            saved_items.append(f"{len(self.current_data['item_specifics'])} specifics")
        
        ttk.Label(main, text=f"Will save: {', '.join(saved_items) if saved_items else 'current settings'}",
                 foreground='#888',
                 background='#1a1a2e').pack(anchor='w', pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(main, style='Settings.TFrame')
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        
        ttk.Button(btn_frame, text="Cancel",
                  command=self.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="💾 Save",
                  command=self.on_save).pack(side=tk.RIGHT, padx=5)
        
        # Enter key to save
        self.bind('<Return>', lambda e: self.on_save())
    
    def on_save(self):
        """Save the template"""
        name = self.name_var.get().strip()
        
        if not name:
            messagebox.showwarning("Name Required", "Please enter a template name")
            return
        
        # Check for existing
        if self.template_manager.get(name):
            if not messagebox.askyesno("Overwrite?", 
                                       f"Template '{name}' already exists. Overwrite?"):
                return
        
        # Save template
        self.template_manager.save(name, self.current_data)
        self.result = name
        self.destroy()


# Test
if __name__ == "__main__":
    root = tk.Tk()
    root.title("Test")
    root.geometry("600x400")
    root.configure(bg='#1a1a2e')
    
    def open_templates():
        dialog = TemplateDialog(root)
        root.wait_window(dialog)
        if dialog.result:
            print(f"Selected: {dialog.result}")
    
    def save_template():
        data = {'condition': 'USED_GOOD', 'price': '29.99'}
        dialog = SaveTemplateDialog(root, data)
        root.wait_window(dialog)
        if dialog.result:
            print(f"Saved as: {dialog.result}")
    
    ttk.Button(root, text="Open Templates", command=open_templates).pack(pady=20)
    ttk.Button(root, text="Save Template", command=save_template).pack(pady=20)
    
    root.mainloop()
