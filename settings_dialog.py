"""
Settings Dialog for eBay Draft Commander Pro
Tabbed settings interface matching the dark theme
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import threading
import webbrowser

from settings_manager import SettingsManager


class SettingsDialog(tk.Toplevel):
    """Settings dialog with tabbed interface"""
    
    # Item condition options
    CONDITIONS = [
        'NEW',
        'LIKE_NEW',
        'NEW_OTHER',
        'NEW_WITH_DEFECTS',
        'MANUFACTURER_REFURBISHED',
        'CERTIFIED_REFURBISHED',
        'EXCELLENT_REFURBISHED',
        'VERY_GOOD_REFURBISHED',
        'GOOD_REFURBISHED',
        'SELLER_REFURBISHED',
        'USED_EXCELLENT',
        'USED_VERY_GOOD',
        'USED_GOOD',
        'USED_ACCEPTABLE',
        'FOR_PARTS_OR_NOT_WORKING',
    ]
    
    def __init__(self, parent, settings_manager: SettingsManager):
        super().__init__(parent)
        
        self.settings_manager = settings_manager
        self.result = False  # True if user clicked Save
        self.entry_widgets = {}  # Store references to entry widgets by key
        self.show_sensitive = {}  # Track show/hide state for sensitive fields
        
        # Window setup
        self.title("⚙️ Settings")
        self.geometry("700x550")
        self.configure(bg='#1a1a2e')
        self.resizable(True, True)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        # Setup styles
        self.setup_styles()
        
        # Create widgets
        self.create_widgets()
        
        # Load current settings into form
        self.load_settings()
        
        # Center on parent
        self.center_on_parent(parent)
        
        # Wait for dialog to close
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        
    def setup_styles(self):
        """Configure ttk styles for the dialog"""
        style = ttk.Style()
        
        # Tab styling
        style.configure('Settings.TNotebook', background='#1a1a2e')
        style.configure('Settings.TNotebook.Tab', 
                       background='#16213e', 
                       foreground='white',
                       padding=[15, 5])
        style.map('Settings.TNotebook.Tab',
                 background=[('selected', '#1a1a2e')],
                 foreground=[('selected', '#00d9ff')])
        
        # Frame styling
        style.configure('Settings.TFrame', background='#1a1a2e')
        style.configure('SettingsPanel.TFrame', background='#16213e')
        
        # Label styling
        style.configure('Settings.TLabel', 
                       background='#1a1a2e', 
                       foreground='white',
                       font=('Segoe UI', 10))
        style.configure('SettingsHeader.TLabel',
                       background='#1a1a2e',
                       foreground='#ffd700',
                       font=('Segoe UI', 11, 'bold'))
        style.configure('SettingsDesc.TLabel',
                       background='#1a1a2e',
                       foreground='#888888',
                       font=('Segoe UI', 9))
        
        # Button styling
        style.configure('Settings.TButton', font=('Segoe UI', 10))
        style.configure('SettingsAction.TButton', font=('Segoe UI', 10, 'bold'))
        
    def create_widgets(self):
        """Create all dialog widgets"""
        # Main container
        main_frame = ttk.Frame(self, style='Settings.TFrame', padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_frame = ttk.Frame(main_frame, style='Settings.TFrame')
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(title_frame, text="⚙️ Application Settings",
                 font=('Segoe UI', 14, 'bold'),
                 foreground='#00d9ff',
                 background='#1a1a2e').pack(side=tk.LEFT)
        
        # Notebook (tabs)
        self.notebook = ttk.Notebook(main_frame, style='Settings.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Create tabs
        self.create_general_tab()
        self.create_ebay_api_tab()
        self.create_policies_tab()
        self.create_ai_tab()
        
        # Button frame
        button_frame = ttk.Frame(main_frame, style='Settings.TFrame')
        button_frame.pack(fill=tk.X)
        
        ttk.Button(button_frame, text="Cancel",
                  command=self.on_cancel,
                  style='Settings.TButton').pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(button_frame, text="💾 Save Settings",
                  command=self.on_save,
                  style='SettingsAction.TButton').pack(side=tk.RIGHT, padx=5)
        
        # Validation status
        self.status_label = ttk.Label(button_frame, text="",
                                      style='Settings.TLabel')
        self.status_label.pack(side=tk.LEFT)
        
    def create_scrollable_frame(self, parent):
        """Create a scrollable frame for tab content"""
        canvas = tk.Canvas(parent, bg='#1a1a2e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style='Settings.TFrame')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        return scrollable_frame
        
    def create_general_tab(self):
        """Create the General Settings tab"""
        tab = ttk.Frame(self.notebook, style='Settings.TFrame', padding=15)
        self.notebook.add(tab, text="📋 General")
        
        content = self.create_scrollable_frame(tab)
        
        # Default Condition
        self.create_section_header(content, "Default Listing Settings")
        
        self.create_field(content, 
                         "DEFAULT_CONDITION",
                         "Default Condition",
                         "Item condition for new listings",
                         field_type="combobox",
                         values=self.CONDITIONS)
        
        self.create_field(content,
                         "DEFAULT_PRICE",
                         "Default Price ($)",
                         "Default starting price")
        
        self.create_field(content,
                         "AUTO_MOVE_POSTED",
                         "Auto-move Posted Items",
                         "Move items to 'posted' folder after successful listing",
                         field_type="checkbox")
        
        # Folder Paths
        self.create_section_header(content, "Folder Paths", top_padding=20)
        
        ttk.Label(content, 
                 text="Folder paths are relative to the application directory",
                 style='SettingsDesc.TLabel').pack(anchor='w', pady=(0, 10))
        
    def create_ebay_api_tab(self):
        """Create the eBay API tab"""
        tab = ttk.Frame(self.notebook, style='Settings.TFrame', padding=15)
        self.notebook.add(tab, text="🔑 eBay API")
        
        content = self.create_scrollable_frame(tab)
        
        # Credentials section
        self.create_section_header(content, "API Credentials")
        
        self.create_field(content, "EBAY_APP_ID", "App ID", 
                         "Your eBay application ID")
        self.create_field(content, "EBAY_DEV_ID", "Dev ID",
                         "Developer ID")
        self.create_field(content, "EBAY_CERT_ID", "Cert ID",
                         "Certificate ID (sensitive)")
        self.create_field(content, "EBAY_RU_NAME", "RU Name",
                         "Redirect URL name for OAuth")
        
        self.create_field(content, "EBAY_ENVIRONMENT", "Environment",
                         "Production or Sandbox",
                         field_type="combobox",
                         values=["production", "sandbox"])
        
        # Tokens section
        self.create_section_header(content, "OAuth Tokens", top_padding=20)
        
        self.create_field(content, "EBAY_USER_TOKEN", "User Token",
                         "OAuth access token (sensitive)",
                         multiline=True)
        
        self.create_field(content, "EBAY_REFRESH_TOKEN", "Refresh Token",
                         "OAuth refresh token (sensitive)",
                         multiline=True)
        
        # Action buttons
        action_frame = ttk.Frame(content, style='Settings.TFrame')
        action_frame.pack(fill=tk.X, pady=15)
        
        ttk.Button(action_frame, text="🔗 Authorize eBay",
                  command=self.authorize_ebay,
                  style='Settings.TButton').pack(side=tk.LEFT, padx=5)
        
        ttk.Button(action_frame, text="✅ Test Connection",
                  command=self.test_ebay_connection,
                  style='Settings.TButton').pack(side=tk.LEFT, padx=5)
        
    def create_policies_tab(self):
        """Create the Business Policies tab"""
        tab = ttk.Frame(self.notebook, style='Settings.TFrame', padding=15)
        self.notebook.add(tab, text="📦 Policies")
        
        content = self.create_scrollable_frame(tab)
        
        self.create_section_header(content, "Business Policies")
        
        ttk.Label(content,
                 text="Enter your eBay business policy IDs. Find these in eBay Seller Hub.",
                 style='SettingsDesc.TLabel').pack(anchor='w', pady=(0, 10))
        
        self.create_field(content, "EBAY_FULFILLMENT_POLICY", "Fulfillment Policy ID",
                         "Shipping/fulfillment policy")
        self.create_field(content, "EBAY_PAYMENT_POLICY", "Payment Policy ID",
                         "Payment policy")
        self.create_field(content, "EBAY_RETURN_POLICY", "Return Policy ID",
                         "Return policy")
        
        self.create_section_header(content, "Merchant Location", top_padding=20)
        
        self.create_field(content, "EBAY_MERCHANT_LOCATION", "Location Key",
                         "Your merchant location identifier")
        
        # Action buttons
        action_frame = ttk.Frame(content, style='Settings.TFrame')
        action_frame.pack(fill=tk.X, pady=15)
        
        ttk.Button(action_frame, text="🔄 Fetch Policies from eBay",
                  command=self.fetch_policies,
                  style='Settings.TButton').pack(side=tk.LEFT, padx=5)
        
        ttk.Button(action_frame, text="🌐 Open Seller Hub",
                  command=lambda: webbrowser.open('https://www.ebay.com/sh/landing'),
                  style='Settings.TButton').pack(side=tk.LEFT, padx=5)
        
    def create_ai_tab(self):
        """Create the AI Settings tab"""
        tab = ttk.Frame(self.notebook, style='Settings.TFrame', padding=15)
        self.notebook.add(tab, text="🤖 AI")
        
        content = self.create_scrollable_frame(tab)
        
        self.create_section_header(content, "Google Gemini AI")
        
        ttk.Label(content,
                 text="Get your API key from Google AI Studio: https://aistudio.google.com/apikey",
                 style='SettingsDesc.TLabel').pack(anchor='w', pady=(0, 10))
        
        self.create_field(content, "GOOGLE_API_KEY", "Google API Key",
                         "Gemini API key for image analysis")
        
        # Action buttons
        action_frame = ttk.Frame(content, style='Settings.TFrame')
        action_frame.pack(fill=tk.X, pady=15)
        
        ttk.Button(action_frame, text="✅ Test AI Connection",
                  command=self.test_ai_connection,
                  style='Settings.TButton').pack(side=tk.LEFT, padx=5)
        
        ttk.Button(action_frame, text="🔗 Get API Key",
                  command=lambda: webbrowser.open('https://aistudio.google.com/apikey'),
                  style='Settings.TButton').pack(side=tk.LEFT, padx=5)
        
    def create_section_header(self, parent, text, top_padding=0):
        """Create a section header"""
        frame = ttk.Frame(parent, style='Settings.TFrame')
        frame.pack(fill=tk.X, pady=(top_padding, 10))
        
        ttk.Label(frame, text=text, style='SettingsHeader.TLabel').pack(anchor='w')
        
        # Separator line
        separator = ttk.Frame(frame, height=1)
        separator.pack(fill=tk.X, pady=(5, 0))
        
    def create_field(self, parent, key, label, description="", 
                    field_type="entry", values=None, multiline=False):
        """
        Create a form field
        
        Args:
            parent: Parent widget
            key: Settings key
            label: Field label
            description: Help text
            field_type: "entry", "combobox", or "checkbox"
            values: List of values for combobox
            multiline: If True, use Text widget for long content
        """
        frame = ttk.Frame(parent, style='Settings.TFrame')
        frame.pack(fill=tk.X, pady=5)
        
        # Label row
        label_frame = ttk.Frame(frame, style='Settings.TFrame')
        label_frame.pack(fill=tk.X)
        
        is_sensitive = self.settings_manager.is_sensitive(key)
        label_text = f"{label} {'🔒' if is_sensitive else ''}"
        
        ttk.Label(label_frame, text=label_text, 
                 style='Settings.TLabel').pack(side=tk.LEFT)
        
        if description:
            ttk.Label(label_frame, text=f"  - {description}",
                     style='SettingsDesc.TLabel').pack(side=tk.LEFT)
        
        # Input row
        input_frame = ttk.Frame(frame, style='Settings.TFrame')
        input_frame.pack(fill=tk.X, pady=(2, 0))
        
        if field_type == "checkbox":
            var = tk.BooleanVar()
            widget = ttk.Checkbutton(input_frame, variable=var)
            widget.pack(side=tk.LEFT)
            self.entry_widgets[key] = ('checkbox', var)
            
        elif field_type == "combobox":
            var = tk.StringVar()
            widget = ttk.Combobox(input_frame, textvariable=var, 
                                 values=values or [], state='readonly',
                                 width=40)
            widget.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.entry_widgets[key] = ('combobox', var)
            
        elif multiline:
            # Use Text widget for long content
            text_frame = ttk.Frame(input_frame, style='Settings.TFrame')
            text_frame.pack(fill=tk.X, expand=True)
            
            widget = tk.Text(text_frame, height=3, width=50,
                           bg='#0f0f23', fg='white',
                           insertbackground='white',
                           font=('Consolas', 9))
            widget.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            # Show/hide toggle for sensitive fields
            if is_sensitive:
                self.show_sensitive[key] = tk.BooleanVar(value=False)
                toggle_btn = ttk.Button(input_frame, text="👁️",
                                       command=lambda k=key: self.toggle_sensitive(k),
                                       width=3)
                toggle_btn.pack(side=tk.RIGHT, padx=5)
            
            self.entry_widgets[key] = ('text', widget)
            
        else:
            # Standard entry
            show = tk.StringVar()
            
            if is_sensitive:
                widget = ttk.Entry(input_frame, textvariable=show, 
                                  show='•', width=50)
                self.show_sensitive[key] = tk.BooleanVar(value=False)
                
                toggle_btn = ttk.Button(input_frame, text="👁️",
                                       command=lambda k=key, w=widget: self.toggle_entry_show(k, w),
                                       width=3)
                toggle_btn.pack(side=tk.RIGHT, padx=5)
            else:
                widget = ttk.Entry(input_frame, textvariable=show, width=50)
            
            widget.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.entry_widgets[key] = ('entry', show)
            
    def toggle_entry_show(self, key, widget):
        """Toggle show/hide for entry widget"""
        if self.show_sensitive[key].get():
            widget.configure(show='•')
            self.show_sensitive[key].set(False)
        else:
            widget.configure(show='')
            self.show_sensitive[key].set(True)
            
    def toggle_sensitive(self, key):
        """Toggle show/hide for text widget (placeholder for future)"""
        # For text widgets, could implement masking but it's more complex
        pass
        
    def load_settings(self):
        """Load current settings into form fields"""
        settings = self.settings_manager.get_all()
        
        for key, (widget_type, widget) in self.entry_widgets.items():
            value = settings.get(key, '')
            
            if widget_type == 'checkbox':
                widget.set(value.lower() == 'true')
            elif widget_type == 'combobox':
                widget.set(value)
            elif widget_type == 'text':
                widget.delete('1.0', tk.END)
                widget.insert('1.0', value)
            else:  # entry
                widget.set(value)
                
    def get_form_values(self) -> dict:
        """Get all values from form fields"""
        values = {}
        
        for key, (widget_type, widget) in self.entry_widgets.items():
            if widget_type == 'checkbox':
                values[key] = 'true' if widget.get() else 'false'
            elif widget_type == 'text':
                values[key] = widget.get('1.0', tk.END).strip()
            else:  # entry or combobox
                values[key] = widget.get()
                
        return values
        
    def on_save(self):
        """Save settings and close dialog"""
        values = self.get_form_values()
        
        # Update settings manager
        for key, value in values.items():
            self.settings_manager.set(key, value)
        
        # Validate
        errors = self.settings_manager.validate()
        
        if errors:
            error_msg = "Please fix the following issues:\n\n" + "\n".join(f"• {e}" for e in errors)
            messagebox.showwarning("Validation Errors", error_msg, parent=self)
            return
        
        # Save to file
        try:
            self.settings_manager.save()
            self.result = True
            messagebox.showinfo("Saved", "Settings saved successfully!", parent=self)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Could not save settings:\n{e}", parent=self)
            
    def on_cancel(self):
        """Cancel and close dialog"""
        self.result = False
        self.destroy()
        
    def center_on_parent(self, parent):
        """Center dialog on parent window"""
        self.update_idletasks()
        
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        
        dialog_width = self.winfo_width()
        dialog_height = self.winfo_height()
        
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        
        self.geometry(f"+{x}+{y}")
        
    # ---------------------------------------------------------------------------
    # Action handlers
    # ---------------------------------------------------------------------------
    
    def authorize_ebay(self):
        """Launch eBay authorization flow"""
        try:
            import subprocess
            auth_script = Path(__file__).parent / "ebay_auth.py"
            if auth_script.exists():
                subprocess.Popen(['python', str(auth_script)], 
                               creationflags=subprocess.CREATE_NEW_CONSOLE)
                messagebox.showinfo("Authorization", 
                                   "Authorization script launched in new window.\n"
                                   "Follow the prompts to authorize your eBay account.\n\n"
                                   "After authorization, restart the app to use the new tokens.",
                                   parent=self)
            else:
                messagebox.showerror("Error", f"Auth script not found: {auth_script}", 
                                    parent=self)
        except Exception as e:
            messagebox.showerror("Error", f"Could not launch authorization: {e}",
                               parent=self)
            
    def test_ebay_connection(self):
        """Test eBay API connection"""
        self.status_label.configure(text="Testing eBay connection...", 
                                   foreground='#ffd700')
        self.update()
        
        def test():
            try:
                from ebay_api import eBayAPIClient
                client = eBayAPIClient()
                # Try a simple API call
                result = client.get_category_suggestions("test item")
                
                if result:
                    self.after(0, lambda: self.status_label.configure(
                        text="✅ eBay connection successful!", foreground='#00ff00'))
                    self.after(0, lambda: messagebox.showinfo(
                        "Success", "eBay API connection is working!", parent=self))
                else:
                    self.after(0, lambda: self.status_label.configure(
                        text="⚠️ Connection works but no data returned", foreground='#ffd700'))
            except Exception as e:
                self.after(0, lambda: self.status_label.configure(
                    text=f"❌ Connection failed", foreground='#ff6b6b'))
                self.after(0, lambda: messagebox.showerror(
                    "Connection Failed", f"Could not connect to eBay:\n{e}", parent=self))
        
        threading.Thread(target=test, daemon=True).start()
        
    def fetch_policies(self):
        """Fetch business policies from eBay"""
        self.status_label.configure(text="Fetching policies...", foreground='#ffd700')
        self.update()
        
        def fetch():
            try:
                from get_policies import get_all_policies
                policies = get_all_policies()
                
                if policies:
                    # Show policies in a message
                    msg = "Found policies:\n\n"
                    for ptype, plist in policies.items():
                        msg += f"\n{ptype}:\n"
                        for p in plist[:3]:  # Show first 3 of each type
                            msg += f"  • {p.get('name', 'Unknown')}: {p.get('id', 'N/A')}\n"
                    
                    self.after(0, lambda: messagebox.showinfo("Policies Found", msg, parent=self))
                    self.after(0, lambda: self.status_label.configure(
                        text="✅ Policies fetched", foreground='#00ff00'))
                else:
                    self.after(0, lambda: messagebox.showwarning(
                        "No Policies", "No policies found. Create them in eBay Seller Hub first.",
                        parent=self))
                    
            except ImportError:
                self.after(0, lambda: messagebox.showerror(
                    "Error", "get_policies.py module not found", parent=self))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror(
                    "Error", f"Could not fetch policies:\n{e}", parent=self))
                self.after(0, lambda: self.status_label.configure(
                    text="❌ Fetch failed", foreground='#ff6b6b'))
        
        threading.Thread(target=fetch, daemon=True).start()
        
    def test_ai_connection(self):
        """Test Google Gemini AI connection"""
        self.status_label.configure(text="Testing AI connection...", foreground='#ffd700')
        self.update()
        
        def test():
            try:
                from ai_analyzer import AIAnalyzer
                analyzer = AIAnalyzer()
                
                # The AIAnalyzer initializes the model, so if no exception, it works
                self.after(0, lambda: self.status_label.configure(
                    text="✅ AI connection successful!", foreground='#00ff00'))
                self.after(0, lambda: messagebox.showinfo(
                    "Success", "Google Gemini AI is configured correctly!", parent=self))
                    
            except Exception as e:
                self.after(0, lambda: self.status_label.configure(
                    text="❌ AI connection failed", foreground='#ff6b6b'))
                self.after(0, lambda: messagebox.showerror(
                    "AI Error", f"Could not connect to Google Gemini:\n{e}", parent=self))
        
        threading.Thread(target=test, daemon=True).start()


# Test the dialog standalone
if __name__ == "__main__":
    from tkinter import Tk
    
    root = Tk()
    root.title("Test Window")
    root.geometry("800x600")
    root.configure(bg='#1a1a2e')
    
    settings = SettingsManager()
    
    def open_settings():
        dialog = SettingsDialog(root, settings)
        root.wait_window(dialog)
        if dialog.result:
            print("Settings were saved!")
        else:
            print("Settings dialog cancelled")
    
    ttk.Button(root, text="Open Settings", command=open_settings).pack(pady=50)
    
    root.mainloop()
