import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import sys
import os
import threading
from pathlib import Path

class SetupWizard:
    def __init__(self, root):
        self.root = root
        self.root.title("TradingView to MT5 - Setup Wizard")
        self.root.geometry("700x600")
        self.root.resizable(True, True)
        
        self.base_dir = Path.cwd()
        
        # Configure dark theme colors
        self.bg_dark = "#1e1e1e"
        self.bg_secondary = "#2d2d2d"
        self.bg_input = "#3c3c3c"
        self.fg_primary = "#ffffff"
        self.fg_secondary = "#b0b0b0"
        self.accent_blue = "#0078d4"
        self.accent_green = "#107c10"
        self.accent_red = "#d13438"
        self.accent_yellow = "#ffa500"
        
        # Apply dark theme
        self.setup_dark_theme()
        
        # Variables
        self.basic_user = tk.StringVar(value="admin")
        self.basic_password = tk.StringVar()
        self.external_base_url = tk.StringVar(value="http://localhost:5000")
        self.mt5_main_path = tk.StringVar()
        self.mt5_instances_dir = tk.StringVar()
        
        # Google OAuth Variables (Multi-User SaaS)
        self.google_client_id = tk.StringVar()
        self.google_client_secret = tk.StringVar()
        self.admin_email = tk.StringVar()

        # Auto-set instances directory
        self.mt5_instances_dir.set(str(self.base_dir / 'mt5_instances'))
        
        self.setup_ui()
        
    def setup_dark_theme(self):
        """Setup dark theme for the application"""
        self.root.configure(bg=self.bg_dark)
        
        # Configure ttk styles
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        style.configure(".", 
                       background=self.bg_dark,
                       foreground=self.fg_primary,
                       fieldbackground=self.bg_input,
                       bordercolor=self.bg_secondary,
                       selectbackground=self.accent_blue,
                       selectforeground=self.fg_primary)
        
        style.configure("TFrame", background=self.bg_dark)
        style.configure("TLabel", background=self.bg_dark, foreground=self.fg_primary)
        style.configure("TLabelframe", background=self.bg_dark, foreground=self.fg_primary)
        style.configure("TLabelframe.Label", background=self.bg_dark, foreground=self.fg_primary)
        
        style.configure("TButton",
                       background=self.accent_blue,
                       foreground=self.fg_primary,
                       borderwidth=0,
                       focuscolor='none',
                       padding=10)
        style.map("TButton",
                 background=[('active', '#106ebe'), ('disabled', self.bg_secondary)],
                 foreground=[('disabled', self.fg_secondary)])
        
        style.configure("TEntry",
                       fieldbackground=self.bg_input,
                       foreground=self.fg_primary,
                       bordercolor=self.bg_secondary,
                       insertcolor=self.fg_primary)
        
        style.configure("TProgressbar",
                       background=self.accent_blue,
                       troughcolor=self.bg_secondary,
                       bordercolor=self.bg_secondary,
                       lightcolor=self.accent_blue,
                       darkcolor=self.accent_blue)
        
    def setup_ui(self):
        # Main container with scrollbar
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(main_container, bg=self.bg_dark, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=680)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Mouse wheel scrolling
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # Content padding
        content = ttk.Frame(scrollable_frame, padding="20")
        content.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = tk.Label(
            content, 
            text="🚀 TradingView to MT5 Setup Wizard",
            font=("Segoe UI", 18, "bold"),
            bg=self.bg_dark,
            fg=self.fg_primary
        )
        title_label.pack(pady=(0, 5))
        
        subtitle = tk.Label(
            content,
            text="Configure your automated trading bridge",
            font=("Segoe UI", 10),
            bg=self.bg_dark,
            fg=self.fg_secondary
        )
        subtitle.pack(pady=(0, 20))
        
        # Status label
        self.status_label = tk.Label(
            content,
            text="● Ready to setup",
            font=("Segoe UI", 10),
            bg=self.bg_dark,
            fg=self.accent_yellow
        )
        self.status_label.pack(pady=(0, 20))
        
        # Step 1: Create Directories
        step1_frame = ttk.LabelFrame(content, text=" 📁 Step 1: Initialize Project ", padding="20")
        step1_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(step1_frame, text="Create required folder structure", 
                font=("Segoe UI", 9),
                bg=self.bg_dark,
                fg=self.fg_secondary).pack(anchor=tk.W, pady=(0,10))
        
        self.create_dir_btn = ttk.Button(
            step1_frame,
            text="Create Directories",
            command=self.create_directories
        )
        self.create_dir_btn.pack(pady=(0,10))
        
        self.dir_status = tk.Label(step1_frame, text="", 
                                   bg=self.bg_dark, fg=self.fg_secondary,
                                   font=("Segoe UI", 9))
        self.dir_status.pack()
        
        # Step 2: Install Requirements
        step2_frame = ttk.LabelFrame(content, text=" 📦 Step 2: Install Dependencies ", padding="20")
        step2_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(step2_frame, text="Install required Python packages", 
                font=("Segoe UI", 9),
                bg=self.bg_dark,
                fg=self.fg_secondary).pack(anchor=tk.W, pady=(0,10))
        
        self.install_btn = ttk.Button(
            step2_frame,
            text="Install Requirements",
            command=self.install_requirements,
            state=tk.DISABLED
        )
        self.install_btn.pack(pady=(0,10))
        
        self.progress = ttk.Progressbar(step2_frame, mode='indeterminate', length=300)
        self.progress.pack()
        
        # Step 3: Configuration
        step3_frame = ttk.LabelFrame(content, text=" ⚙️ Step 3: Server Configuration ", padding="20")
        step3_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Create a grid layout for better organization
        config_grid = ttk.Frame(step3_frame)
        config_grid.pack(fill=tk.X)
        
        # Server URL (Required)
        tk.Label(config_grid, text="Server URL:",
                font=("Segoe UI", 9, "bold"),
                bg=self.bg_dark, fg=self.fg_primary).grid(row=0, column=0, sticky=tk.W, pady=8)
        url_entry = ttk.Entry(config_grid, textvariable=self.external_base_url, width=40)
        url_entry.grid(row=0, column=1, pady=8, padx=(15, 0), sticky=tk.EW)

        # Basic Auth Section (Optional - for legacy/fallback)
        tk.Label(config_grid, text="Basic Auth (Optional - Fallback):",
                font=("Segoe UI", 8),
                bg=self.bg_dark, fg=self.accent_yellow).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(15, 5))

        # Username (Optional)
        tk.Label(config_grid, text="Username:",
                font=("Segoe UI", 9),
                bg=self.bg_dark, fg=self.fg_secondary).grid(row=2, column=0, sticky=tk.W, pady=8)
        user_entry = ttk.Entry(config_grid, textvariable=self.basic_user, width=40)
        user_entry.grid(row=2, column=1, pady=8, padx=(15, 0), sticky=tk.EW)

        # Password (Optional)
        tk.Label(config_grid, text="Password:",
                font=("Segoe UI", 9),
                bg=self.bg_dark, fg=self.fg_secondary).grid(row=3, column=0, sticky=tk.W, pady=8)
        pass_entry = ttk.Entry(config_grid, textvariable=self.basic_password, show="●", width=40)
        pass_entry.grid(row=3, column=1, pady=8, padx=(15, 0), sticky=tk.EW)

        tk.Label(config_grid, text="(Leave blank if using only Google OAuth)",
                font=("Segoe UI", 8),
                bg=self.bg_dark, fg=self.fg_secondary).grid(row=4, column=1, sticky=tk.W, padx=(15, 0))

        config_grid.columnconfigure(1, weight=1)
        
        # Step 4: Google OAuth Configuration (Multi-User SaaS)
        step4_frame = ttk.LabelFrame(content, text=" 🔐 Step 4: Google OAuth (Multi-User) ", padding="20")
        step4_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(step4_frame, text="Configure Google OAuth for multi-user authentication",
                font=("Segoe UI", 9),
                bg=self.bg_dark,
                fg=self.fg_secondary).pack(anchor=tk.W, pady=(0,5))

        tk.Label(step4_frame, text="Get credentials from: https://console.cloud.google.com/",
                font=("Segoe UI", 8),
                bg=self.bg_dark,
                fg=self.accent_blue).pack(anchor=tk.W, pady=(0,10))

        oauth_grid = ttk.Frame(step4_frame)
        oauth_grid.pack(fill=tk.X)

        # Google Client ID (REQUIRED)
        tk.Label(oauth_grid, text="Google Client ID: *",
                font=("Segoe UI", 9, "bold"),
                bg=self.bg_dark, fg=self.accent_red).grid(row=0, column=0, sticky=tk.W, pady=8)
        google_id_entry = ttk.Entry(oauth_grid, textvariable=self.google_client_id, width=50)
        google_id_entry.grid(row=0, column=1, pady=8, padx=(15, 0), sticky=tk.EW)

        # Google Client Secret (REQUIRED)
        tk.Label(oauth_grid, text="Google Client Secret: *",
                font=("Segoe UI", 9, "bold"),
                bg=self.bg_dark, fg=self.accent_red).grid(row=1, column=0, sticky=tk.W, pady=8)
        google_secret_entry = ttk.Entry(oauth_grid, textvariable=self.google_client_secret, show="●", width=50)
        google_secret_entry.grid(row=1, column=1, pady=8, padx=(15, 0), sticky=tk.EW)

        # Google Redirect URI (REQUIRED)
        tk.Label(oauth_grid, text="Google Redirect URI: *",
                font=("Segoe UI", 9, "bold"),
                bg=self.bg_dark, fg=self.accent_red).grid(row=2, column=0, sticky=tk.W, pady=8)
        google_redirect_var = tk.StringVar(value=f"{self.external_base_url.get()}/auth/google/callback")
        google_redirect_entry = ttk.Entry(oauth_grid, textvariable=google_redirect_var, width=50)
        google_redirect_entry.grid(row=2, column=1, pady=8, padx=(15, 0), sticky=tk.EW)
        self.google_redirect_uri = google_redirect_var

        # Admin Email (REQUIRED)
        tk.Label(oauth_grid, text="Admin Email: *",
                font=("Segoe UI", 9, "bold"),
                bg=self.bg_dark, fg=self.accent_red).grid(row=3, column=0, sticky=tk.W, pady=8)
        admin_email_entry = ttk.Entry(oauth_grid, textvariable=self.admin_email, width=50)
        admin_email_entry.grid(row=3, column=1, pady=8, padx=(15, 0), sticky=tk.EW)

        tk.Label(oauth_grid, text="* = Required for Multi-User SaaS authentication",
                font=("Segoe UI", 8),
                bg=self.bg_dark, fg=self.accent_yellow).grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=(0, 0), pady=(10, 0))

        oauth_grid.columnconfigure(1, weight=1)

        # Step 5: MT5 Configuration (OPTIONAL)
        step5_frame = ttk.LabelFrame(content, text=" 📊 Step 5: MT5 Settings (Optional) ", padding="20")
        step5_frame.pack(fill=tk.X, pady=(0, 15))

        tk.Label(step5_frame, text="MT5 configuration is optional - you can skip this step",
                font=("Segoe UI", 9),
                bg=self.bg_dark,
                fg=self.accent_yellow).pack(anchor=tk.W, pady=(0,10))

        # MT5 Executable
        tk.Label(step5_frame, text="MT5 Executable Path (Optional)",
                font=("Segoe UI", 9, "bold"),
                bg=self.bg_dark, fg=self.fg_primary).pack(anchor=tk.W, pady=(0,5))
        
        tk.Label(step5_frame, text="Select terminal64.exe from your MT5 installation (skip if not using local MT5)",
                font=("Segoe UI", 8),
                bg=self.bg_dark, fg=self.fg_secondary).pack(anchor=tk.W, pady=(0,8))
        
        path_frame = ttk.Frame(step5_frame)
        path_frame.pack(fill=tk.X, pady=(0,15))
        
        path1_entry = ttk.Entry(path_frame, textvariable=self.mt5_main_path)
        path1_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        browse1_btn = ttk.Button(path_frame, text="Browse", command=self.browse_main_path, width=12)
        browse1_btn.pack(side=tk.RIGHT)
        
        # Instances Directory (read-only info)
        tk.Label(step5_frame, text="Instances Directory",
                font=("Segoe UI", 9, "bold"),
                bg=self.bg_dark, fg=self.fg_primary).pack(anchor=tk.W, pady=(10,5))
        
        tk.Label(step5_frame, text="Auto-created location for MT5 account instances",
                font=("Segoe UI", 8),
                bg=self.bg_dark, fg=self.fg_secondary).pack(anchor=tk.W, pady=(0,8))
        
        instances_display = tk.Label(
            step5_frame,
            textvariable=self.mt5_instances_dir,
            font=("Segoe UI", 9),
            bg=self.bg_input,
            fg=self.fg_secondary,
            anchor=tk.W,
            padx=10,
            pady=8,
            relief=tk.FLAT
        )
        instances_display.pack(fill=tk.X)
        
        # Step 6: Launch
        step6_frame = ttk.LabelFrame(content, text=" 🚀 Step 6: Start Server ", padding="20")
        step6_frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(step6_frame, text="Ready to launch your trading server",
                font=("Segoe UI", 9),
                bg=self.bg_dark,
                fg=self.fg_secondary).pack(anchor=tk.W, pady=(0,15))
        
        self.start_btn = ttk.Button(
            step6_frame,
            text="🚀 Start Server",
            command=self.start_server,
            state=tk.DISABLED
        )
        self.start_btn.pack()
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
    def create_directories(self):
        """Create required directory structure"""
        try:
            directories = [
                'app',
                'app/copy_trading',
                'static', 
                'logs',
                'data',
                'data/commands',
                'mt5_instances',
                'backup',
                'migrations'
            ]
            
            created = []
            for directory in directories:
                dir_path = self.base_dir / directory
                if not dir_path.exists():
                    dir_path.mkdir(parents=True, exist_ok=True)
                    created.append(directory)
                    
                    # Create .gitkeep in empty folders
                    if directory in ['data/commands', 'logs', 'backup']:
                        gitkeep_file = dir_path / '.gitkeep'
                        gitkeep_file.touch()
            
            if created:
                self.dir_status.config(
                    text=f"✓ Created: {', '.join(created)}",
                    fg=self.accent_green
                )
            else:
                self.dir_status.config(
                    text="✓ All directories exist",
                    fg=self.accent_green
                )
            
            # Enable next step
            self.install_btn.config(state=tk.NORMAL)
            self.create_dir_btn.config(state=tk.DISABLED)
            self.status_label.config(
                text="● Step 1 Complete → Install Requirements",
                fg=self.accent_green
            )
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create directories:\n{str(e)}")
            self.dir_status.config(text=f"✗ Error: {str(e)}", fg=self.accent_red)
    
    def run_database_migrations(self):
        """Run database migrations to set up multi-user tables"""
        migration_results = []

        try:
            # Migration 001: Add users table
            migration_001 = self.base_dir / 'migrations' / '001_add_users_table.py'
            if migration_001.exists():
                result = subprocess.run(
                    [sys.executable, str(migration_001)],
                    capture_output=True,
                    text=True,
                    cwd=str(self.base_dir)
                )
                if result.returncode == 0:
                    migration_results.append("✓ Database schema created")
                else:
                    migration_results.append(f"⚠ Migration 001: {result.stderr[:100]}")

            # Migration 002: Migrate copy pairs JSON
            migration_002 = self.base_dir / 'migrations' / '002_migrate_copy_pairs_json.py'
            if migration_002.exists():
                result = subprocess.run(
                    [sys.executable, str(migration_002)],
                    capture_output=True,
                    text=True,
                    cwd=str(self.base_dir)
                )
                if result.returncode == 0:
                    migration_results.append("✓ Copy pairs migrated")

            # Migration 003: Migrate webhook accounts JSON
            migration_003 = self.base_dir / 'migrations' / '003_migrate_webhook_accounts.py'
            if migration_003.exists():
                result = subprocess.run(
                    [sys.executable, str(migration_003)],
                    capture_output=True,
                    text=True,
                    cwd=str(self.base_dir)
                )
                if result.returncode == 0:
                    migration_results.append("✓ Webhook accounts migrated")

            return True, migration_results

        except Exception as e:
            return False, [f"Migration error: {str(e)}"]

    def browse_main_path(self):
        filename = filedialog.askopenfilename(
            title="Select MT5 Terminal Executable (terminal64.exe)",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")]
        )
        if filename:
            self.mt5_main_path.set(filename)
    
    def install_requirements(self):
        self.install_btn.config(state=tk.DISABLED)
        self.progress.start()
        self.status_label.config(text="● Installing packages...", fg=self.accent_yellow)
        
        def install():
            try:
                requirements = """# Core Flask Dependencies
Flask==2.3.3
Flask-Limiter==2.8.1
Flask-Cors==4.0.0
werkzeug==2.3.7

# Environment & Configuration
python-dotenv==1.0.0

# System Monitoring
psutil==5.9.6

# HTTP Client (Required for Google OAuth)
requests==2.31.0
"""
                with open("requirements.txt", "w") as f:
                    f.write(requirements)
                
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                    capture_output=True,
                    text=True
                )
                
                self.root.after(0, self.installation_complete, result.returncode == 0)
                
            except Exception as e:
                self.root.after(0, self.installation_complete, False, str(e))
        
        thread = threading.Thread(target=install)
        thread.daemon = True
        thread.start()
    
    def installation_complete(self, success, error=None):
        self.progress.stop()
        self.install_btn.config(state=tk.NORMAL)
        
        if success:
            self.status_label.config(
                text="● Step 2 Complete → Configure Settings",
                fg=self.accent_green
            )
            self.start_btn.config(state=tk.NORMAL)
            messagebox.showinfo(
                "Success", 
                "Dependencies installed successfully!\n\nPlease complete the configuration."
            )
        else:
            self.status_label.config(
                text="● Installation failed",
                fg=self.accent_red
            )
            messagebox.showerror("Error", f"Installation failed:\n{error if error else 'Unknown error'}")
    
    def validate_inputs(self):
        # Server URL is always required
        if not self.external_base_url.get():
            messagebox.showwarning("Validation Error", "Please enter server URL")
            return False

        # Google OAuth Credentials are REQUIRED for Multi-User SaaS
        if not self.google_client_id.get().strip():
            messagebox.showerror(
                "Missing Google Credentials",
                "Google Client ID is required for Multi-User SaaS authentication.\n\n"
                "Get this from: https://console.cloud.google.com/apis/credentials"
            )
            return False

        if not self.google_client_secret.get().strip():
            messagebox.showerror(
                "Missing Google Credentials",
                "Google Client Secret is required for Multi-User SaaS authentication.\n\n"
                "Get this from: https://console.cloud.google.com/apis/credentials"
            )
            return False

        if not self.admin_email.get().strip():
            messagebox.showerror(
                "Missing Admin Email",
                "Admin Email is required.\n\n"
                "This email will be granted admin privileges on first login."
            )
            return False

        # Validate email format (basic check)
        if "@" not in self.admin_email.get() or "." not in self.admin_email.get():
            messagebox.showwarning("Validation Error", "Please enter a valid email address for Admin Email")
            return False

        # Basic Auth validation (only if user provides values)
        if self.basic_password.get() and len(self.basic_password.get()) < 6:
            messagebox.showwarning("Validation Error", "If providing a password, it must be at least 6 characters")
            return False

        # MT5 is optional - only validate if path is provided
        if self.mt5_main_path.get():
            if not os.path.exists(self.mt5_main_path.get()):
                messagebox.showerror("Error", "MT5 executable not found at specified path")
                return False

        return True
    
    def start_server(self):
        if not self.validate_inputs():
            return
        
        try:
            import secrets

            # SECRET_KEY is required for Flask session encryption
            # This is a SERVER-LEVEL key, not a user token
            secret_key = secrets.token_urlsafe(32)

            # NOTE: We do NOT generate WEBHOOK_TOKEN here anymore!
            # In Multi-User SaaS mode, each user gets their own webhook token
            # when they log in via Google OAuth. Tokens are stored in the
            # user_tokens database table.

            # Build MT5 config section (only include if path provided)
            mt5_section = f"""# MT5 Configuration
MT5_MAIN_PATH={self.mt5_main_path.get()}
MT5_PROFILE_SOURCE=
MT5_INSTANCES_DIR={self.mt5_instances_dir.get()}
""" if self.mt5_main_path.get() else """# MT5 Configuration (Not configured - using Remote EA mode)
MT5_MAIN_PATH=
MT5_PROFILE_SOURCE=
MT5_INSTANCES_DIR=
"""

            # Build Google OAuth section (REQUIRED)
            google_section = f"""# Google OAuth (Multi-User SaaS) - REQUIRED
GOOGLE_CLIENT_ID={self.google_client_id.get()}
GOOGLE_CLIENT_SECRET={self.google_client_secret.get()}
GOOGLE_REDIRECT_URI={self.google_redirect_uri.get()}
ADMIN_EMAIL={self.admin_email.get()}
"""

            env_content = f"""# Server Configuration
# SECRET_KEY: Required for Flask session encryption (server-level, not user-specific)
SECRET_KEY={secret_key}

# Legacy Basic Auth (Optional - only if not using Google OAuth)
BASIC_USER={self.basic_user.get()}
BASIC_PASS={self.basic_password.get()}
EXTERNAL_BASE_URL={self.external_base_url.get()}

# Webhook Configuration
# NOTE: In Multi-User SaaS mode, each user gets their own webhook token
# when they log in via Google OAuth. No global WEBHOOK_TOKEN needed.
# WEBHOOK_TOKEN is only for legacy/backward compatibility.
WEBHOOK_RATE_LIMIT=60/minute

{mt5_section}
{google_section}
# Session Configuration
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax
SESSION_COOKIE_SECURE=False

# Email Configuration (Optional)
EMAIL_NOTIFICATIONS_ENABLED=false
SMTP_SERVER=
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USER=
SMTP_PASS=
EMAIL_FROM=
EMAIL_TO=

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/trading_bot.log
"""
            
            with open(".env", "w") as f:
                f.write(env_content)
            
            # Run database migrations automatically
            self.status_label.config(text="● Running database migrations...", fg=self.accent_yellow)
            self.root.update()

            migration_success, migration_results = self.run_database_migrations()

            if not migration_success:
                messagebox.showwarning(
                    "Migration Warning",
                    "Database migrations may not have completed successfully.\n\n"
                    + "\n".join(migration_results) +
                    "\n\nYou can run migrations manually later with:\n"
                    "python migrations/001_add_users_table.py"
                )

            if not os.path.exists("server.py"):
                self.create_server_file()
            
            # Build the launch message - Google OAuth is now required and always enabled
            launch_msg = (
                f"✓ Configuration complete!\n\n"
                f"Web Interface: {self.external_base_url.get()}\n\n"
                f"🔐 Multi-User SaaS Mode Enabled\n"
                f"• Users will login via Google OAuth\n"
                f"• Each user gets their own webhook URL after login\n"
                f"• Admin email: {self.admin_email.get()}\n"
                f"• Google OAuth: Configured\n\n"
                f"Database: {'✓ Migrated' if migration_success else '⚠ Check migrations'}\n\n"
                f"Start the server now?"
            )
            success_msg = (
                f"Server is now running!\n\n"
                f"Access: {self.external_base_url.get()}\n\n"
                f"🔐 Multi-User SaaS Mode\n"
                f"Users should login with Google to get their personal webhook URL.\n\n"
                f"Admin: {self.admin_email.get()}\n"
                f"Redirect URI: {self.google_redirect_uri.get()}"
            )

            result = messagebox.askokcancel("Ready to Launch", launch_msg)

            if result:
                self.status_label.config(text="● Server starting...", fg=self.accent_blue)
                
                if sys.platform == "win32":
                    subprocess.Popen('start cmd /k python server.py', shell=True)
                else:
                    subprocess.Popen([sys.executable, "server.py"])
                
                self.status_label.config(text="● Server is running!", fg=self.accent_green)
                
                messagebox.showinfo("Server Started", success_msg)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start server:\n{str(e)}")
            self.status_label.config(text="● Error occurred", fg=self.accent_red)
    
    def create_server_file(self):
        """
        Create a basic server.py file - ONLY if main server.py doesn't exist.

        NOTE: This creates a MINIMAL fallback server.
        The actual server.py in this project is much more sophisticated
        and uses the app factory pattern with multi-user support.
        This method should rarely be called.
        """
        server_content = '''#!/usr/bin/env python3
"""
FALLBACK SERVER - Created by setup.py
This is a minimal server for testing. The real server uses app factory pattern.
"""
from flask import Flask, request, jsonify, send_from_directory, redirect, session
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

@app.route('/')
def home():
    # Redirect to login if not authenticated
    if not session.get('user_id') and not session.get('auth'):
        return redirect('/login')
    return send_from_directory('static', 'index.html')

@app.route('/login')
def login():
    return send_from_directory('static', 'login.html')

@app.route('/login/google')
def google_login():
    return jsonify({
        'error': 'Google OAuth not configured in fallback server',
        'note': 'Please use the main server.py with app factory'
    }), 501

@app.route('/health')
def health():
    return jsonify({'status': 'running', 'message': 'Fallback Server'})

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"WARNING: Running fallback server on port {port}")
    print("For full multi-user support, use the main server.py")
    app.run(host='0.0.0.0', port=port, debug=True)
'''
        with open("server.py", "w") as f:
            f.write(server_content)

def main():
    root = tk.Tk()
    app = SetupWizard(root)
    root.mainloop()

if __name__ == "__main__":
    main()
