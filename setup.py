"""
MT5 Trading Bot - Setup Wizard
Simplified configuration tool for generating .env file
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import sys
import os
import threading
import secrets
from pathlib import Path
from datetime import datetime


class SetupWizard:
    """Simplified setup wizard focused on .env generation"""

    def __init__(self, root):
        self.root = root
        self.root.title("MT5 Trading Bot - Setup Wizard")
        self.root.geometry("750x700")
        self.root.resizable(True, True)

        self.base_dir = Path.cwd()

        # Dark theme colors
        self.bg_dark = "#1e1e1e"
        self.bg_secondary = "#2d2d2d"
        self.bg_input = "#3c3c3c"
        self.fg_primary = "#ffffff"
        self.fg_secondary = "#b0b0b0"
        self.accent_blue = "#0078d4"
        self.accent_green = "#107c10"
        self.accent_red = "#d13438"
        self.accent_yellow = "#ffa500"

        # Configuration variables
        self.basic_user = tk.StringVar(value="admin")
        self.basic_password = tk.StringVar()
        self.external_base_url = tk.StringVar(value="http://localhost:5000")
        self.email_enabled = tk.BooleanVar(value=False)
        self.sender_email = tk.StringVar()
        self.sender_password = tk.StringVar()
        self.recipients = tk.StringVar()

        self.setup_dark_theme()
        self.setup_ui()

        # Check if .env already exists
        if (self.base_dir / '.env').exists():
            self.show_existing_env_warning()

    def setup_dark_theme(self):
        """Apply dark theme styling"""
        self.root.configure(bg=self.bg_dark)

        style = ttk.Style()
        style.theme_use('clam')

        # Configure styles
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
        style.configure("TCheckbutton", background=self.bg_dark, foreground=self.fg_primary)

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
                       bordercolor=self.bg_secondary)

    def setup_ui(self):
        """Create the main UI"""
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

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=730)
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
            text="🚀 MT5 Trading Bot - Setup Wizard",
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

        # Step 1: Initialize Project
        self.create_step1_ui(content)

        # Step 2: Install Dependencies
        self.create_step2_ui(content)

        # Step 3: Server Configuration
        self.create_step3_ui(content)

        # Step 4: Email Configuration (Optional)
        self.create_step4_ui(content)

        # Step 5: Generate Configuration
        self.create_step5_gen_ui(content)


        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def create_step1_ui(self, parent):
        """Step 1: Create Directories"""
        frame = ttk.LabelFrame(parent, text=" 📁 Step 1: Initialize Project ", padding="20")
        frame.pack(fill=tk.X, pady=(0, 15))

        tk.Label(frame, text="Create required folder structure",
                font=("Segoe UI", 9),
                bg=self.bg_dark,
                fg=self.fg_secondary).pack(anchor=tk.W, pady=(0,10))

        self.create_dir_btn = ttk.Button(
            frame,
            text="Create Directories",
            command=self.create_directories
        )
        self.create_dir_btn.pack(pady=(0,10))

        self.dir_status = tk.Label(frame, text="",
                                   bg=self.bg_dark, fg=self.fg_secondary,
                                   font=("Segoe UI", 9))
        self.dir_status.pack()

    def create_step2_ui(self, parent):
        """Step 2: Install Dependencies"""
        frame = ttk.LabelFrame(parent, text=" 📦 Step 2: Install Dependencies ", padding="20")
        frame.pack(fill=tk.X, pady=(0, 15))

        tk.Label(frame, text="Install required Python packages",
                font=("Segoe UI", 9),
                bg=self.bg_dark,
                fg=self.fg_secondary).pack(anchor=tk.W, pady=(0,10))

        self.install_btn = ttk.Button(
            frame,
            text="Install Requirements",
            command=self.install_requirements,
            state=tk.DISABLED
        )
        self.install_btn.pack(pady=(0,10))

        self.progress = ttk.Progressbar(frame, mode='indeterminate', length=300)
        self.progress.pack()

    def create_step3_ui(self, parent):
        """Step 3: Server Configuration"""
        frame = ttk.LabelFrame(parent, text=" ⚙️ Step 3: Server Configuration ", padding="20")
        frame.pack(fill=tk.X, pady=(0, 15))

        config_grid = ttk.Frame(frame)
        config_grid.pack(fill=tk.X)

        # Username
        tk.Label(config_grid, text="Username:",
                font=("Segoe UI", 9, "bold"),
                bg=self.bg_dark, fg=self.fg_primary).grid(row=0, column=0, sticky=tk.W, pady=8)
        ttk.Entry(config_grid, textvariable=self.basic_user, width=45).grid(row=0, column=1, pady=8, padx=(15, 0), sticky=tk.EW)

        # Password
        tk.Label(config_grid, text="Password:",
                font=("Segoe UI", 9, "bold"),
                bg=self.bg_dark, fg=self.fg_primary).grid(row=1, column=0, sticky=tk.W, pady=8)
        ttk.Entry(config_grid, textvariable=self.basic_password, show="●", width=45).grid(row=1, column=1, pady=8, padx=(15, 0), sticky=tk.EW)

        # Server URL
        tk.Label(config_grid, text="Server URL:",
                font=("Segoe UI", 9, "bold"),
                bg=self.bg_dark, fg=self.fg_primary).grid(row=2, column=0, sticky=tk.W, pady=8)
        ttk.Entry(config_grid, textvariable=self.external_base_url, width=45).grid(row=2, column=1, pady=8, padx=(15, 0), sticky=tk.EW)

        config_grid.columnconfigure(1, weight=1)

    def create_step4_ui(self, parent):
        """Step 4: Email Configuration (Optional)"""
        frame = ttk.LabelFrame(parent, text=" 📧 Step 4: Email Notifications (Optional) ", padding="20")
        frame.pack(fill=tk.X, pady=(0, 15))

        # Enable checkbox
        ttk.Checkbutton(
            frame,
            text="Enable email notifications",
            variable=self.email_enabled,
            command=self.toggle_email_fields
        ).pack(anchor=tk.W, pady=(0, 10))

        # Email fields container
        self.email_fields_frame = ttk.Frame(frame)
        self.email_fields_frame.pack(fill=tk.X)

        config_grid = ttk.Frame(self.email_fields_frame)
        config_grid.pack(fill=tk.X)

        # Sender Email
        tk.Label(config_grid, text="Sender Email:",
                font=("Segoe UI", 9, "bold"),
                bg=self.bg_dark, fg=self.fg_primary).grid(row=0, column=0, sticky=tk.W, pady=8)
        ttk.Entry(config_grid, textvariable=self.sender_email, width=45, state=tk.DISABLED).grid(row=0, column=1, pady=8, padx=(15, 0), sticky=tk.EW)

        # Sender Password
        tk.Label(config_grid, text="App Password:",
                font=("Segoe UI", 9, "bold"),
                bg=self.bg_dark, fg=self.fg_primary).grid(row=1, column=0, sticky=tk.W, pady=8)
        self.sender_pass_entry = ttk.Entry(config_grid, textvariable=self.sender_password, show="●", width=45, state=tk.DISABLED)
        self.sender_pass_entry.grid(row=1, column=1, pady=8, padx=(15, 0), sticky=tk.EW)

        # Recipients
        tk.Label(config_grid, text="Recipients:",
                font=("Segoe UI", 9, "bold"),
                bg=self.bg_dark, fg=self.fg_primary).grid(row=2, column=0, sticky=tk.W, pady=8)
        ttk.Entry(config_grid, textvariable=self.recipients, width=45, state=tk.DISABLED).grid(row=2, column=1, pady=8, padx=(15, 0), sticky=tk.EW)

        tk.Label(config_grid, text="(Comma-separated emails)",
                font=("Segoe UI", 8),
                bg=self.bg_dark, fg=self.fg_secondary).grid(row=3, column=1, sticky=tk.W, padx=(15, 0))

        config_grid.columnconfigure(1, weight=1)

        # Store entry widgets for enabling/disabling
        self.email_entry_widgets = [
            config_grid.grid_slaves(row=0, column=1)[0],
            config_grid.grid_slaves(row=1, column=1)[0],
            config_grid.grid_slaves(row=2, column=1)[0]
        ]

    def create_step5_gen_ui(self, parent):
        """Step 5: Generate Configuration"""
        frame = ttk.LabelFrame(parent, text=" 🚀 Step 5: Generate Configuration ", padding="20")
        frame.pack(fill=tk.X, pady=(0, 10))

        tk.Label(frame, text="Ready to generate .env configuration file",
                font=("Segoe UI", 9),
                bg=self.bg_dark,
                fg=self.fg_secondary).pack(anchor=tk.W, pady=(0,15))

        self.generate_btn = ttk.Button(
            frame,
            text="Generate .env File",
            command=self.generate_env,
            state=tk.DISABLED
        )
        self.generate_btn.pack()

    def show_existing_env_warning(self):
        """Warn user if .env already exists"""
        result = messagebox.askyesno(
            "⚠️ .env File Exists",
            ".env file already exists.\n\n"
            "Do you want to:\n"
            "• YES: Backup existing and create new\n"
            "• NO: Exit setup wizard\n\n"
            "Note: Existing .env will be saved as .env.backup",
            icon='warning'
        )

        if not result:
            self.root.quit()

    def toggle_email_fields(self):
        """Enable/disable email configuration fields"""
        state = tk.NORMAL if self.email_enabled.get() else tk.DISABLED
        for widget in self.email_entry_widgets:
            widget.config(state=state)


    def create_directories(self):
        """Create required directory structure"""
        try:
            directories = [
                'app',
                'app/core',
                'app/modules',
                'app/services',
                'app/copy_trading',
                'templates',
                'templates/pages',
                'templates/partials',
                'templates/partials/components',
                'static',
                'static/css',
                'static/css/pages',
                'static/js',
                'static/js/core',
                'static/js/modules',
                'static/js/components',
                'logs',
                'data',
                'data/commands'
            ]

            created = []
            for directory in directories:
                dir_path = self.base_dir / directory
                if not dir_path.exists():
                    dir_path.mkdir(parents=True, exist_ok=True)
                    created.append(directory)

                    # Create .gitkeep in data folders
                    if directory in ['data/commands', 'logs']:
                        (dir_path / '.gitkeep').touch()

            if created:
                self.dir_status.config(
                    text=f"✓ Created: {len(created)} directories",
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

    def install_requirements(self):
        """Install Python dependencies"""
        self.install_btn.config(state=tk.DISABLED)
        self.progress.start()
        self.status_label.config(text="● Installing packages...", fg=self.accent_yellow)

        def install():
            try:
                # Check if requirements.txt exists
                if not (self.base_dir / "requirements.txt").exists():
                    raise FileNotFoundError("requirements.txt not found")

                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )

                self.root.after(0, self.installation_complete, result.returncode == 0, result.stderr if result.returncode != 0 else None)

            except FileNotFoundError as e:
                self.root.after(0, self.installation_complete, False, str(e))
            except subprocess.TimeoutExpired:
                self.root.after(0, self.installation_complete, False, "Installation timed out")
            except Exception as e:
                self.root.after(0, self.installation_complete, False, str(e))

        thread = threading.Thread(target=install)
        thread.daemon = True
        thread.start()

    def installation_complete(self, success, error=None):
        """Handle installation completion"""
        self.progress.stop()
        self.install_btn.config(state=tk.NORMAL)

        if success:
            self.status_label.config(
                text="● Step 2 Complete → Configure Settings",
                fg=self.accent_green
            )
            self.generate_btn.config(state=tk.NORMAL)
            messagebox.showinfo(
                "Success",
                "✓ Dependencies installed successfully!\n\n"
                "Please complete the configuration below."
            )
        else:
            self.status_label.config(
                text="● Installation failed",
                fg=self.accent_red
            )
            error_msg = f"Installation failed:\n\n{error if error else 'Unknown error'}\n\n" \
                       "You can try:\n" \
                       "1. Install manually: pip install -r requirements.txt\n" \
                       "2. Check your internet connection\n" \
                       "3. Run as administrator"
            messagebox.showerror("Error", error_msg)

    def validate_inputs(self):
        """Validate user inputs"""
        if not self.basic_user.get():
            messagebox.showwarning("Validation Error", "Please enter a username")
            return False

        if not self.basic_password.get():
            messagebox.showwarning("Validation Error", "Please enter a password")
            return False

        if len(self.basic_password.get()) < 6:
            messagebox.showwarning("Validation Error", "Password must be at least 6 characters")
            return False

        if not self.external_base_url.get():
            messagebox.showwarning("Validation Error", "Please enter server URL")
            return False

        # Validate email if enabled
        if self.email_enabled.get():
            if not self.sender_email.get():
                messagebox.showwarning("Validation Error", "Please enter sender email")
                return False
            if not self.sender_password.get():
                messagebox.showwarning("Validation Error", "Please enter email app password")
                return False
            if not self.recipients.get():
                messagebox.showwarning("Validation Error", "Please enter recipient email(s)")
                return False

        return True

    def generate_env(self):
        """Generate .env configuration file"""
        if not self.validate_inputs():
            return

        try:
            # Backup existing .env if it exists
            env_file = self.base_dir / '.env'
            if env_file.exists():
                backup_file = self.base_dir / f'.env.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}'
                env_file.rename(backup_file)
                messagebox.showinfo("Backup", f"Existing .env backed up to:\n{backup_file.name}")

            # Generate secure keys
            secret_key = secrets.token_urlsafe(32)
            webhook_token = secrets.token_urlsafe(16)

            # Build .env content
            env_content = f"""# MT5 Trading Bot Configuration
# Generated by Setup Wizard on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

# ==========================================
# SERVER CONFIGURATION
# ==========================================

# Basic Authentication
BASIC_USER={self.basic_user.get()}
BASIC_PASS={self.basic_password.get()}

# Security
SECRET_KEY={secret_key}
WEBHOOK_TOKEN={webhook_token}
EXTERNAL_BASE_URL={self.external_base_url.get()}

# Server Settings
PORT=5000
DEBUG=False


# ==========================================
# EMAIL NOTIFICATIONS
# ==========================================

# Enable/Disable Email Alerts
EMAIL_ENABLED={str(self.email_enabled.get()).lower()}

# Sender Configuration
SENDER_EMAIL={self.sender_email.get() if self.email_enabled.get() else ''}
SENDER_PASSWORD={self.sender_password.get() if self.email_enabled.get() else ''}

# Recipients (comma-separated)
RECIPIENTS={self.recipients.get() if self.email_enabled.get() else ''}

# ==========================================
# ADVANCED SETTINGS
# ==========================================

# Symbol Mapping
SYMBOL_FETCH_ENABLED=False
FUZZY_MATCH_THRESHOLD=0.6

# Rate Limiting
RATE_LIMIT_WEBHOOK=10 per minute
RATE_LIMIT_API=100 per hour

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/trading_bot.log
"""

            # Write .env file
            with open(env_file, 'w', encoding='utf-8') as f:
                f.write(env_content)

            # Show success message
            webhook_url = f"{self.external_base_url.get()}/webhook/{webhook_token}"

            success_message = f"""✓ Configuration Generated Successfully!

📁 File Created: .env

🔐 Credentials:
   • Username: {self.basic_user.get()}
   • Password: {'*' * len(self.basic_password.get())}

🌐 Server:
   • URL: {self.external_base_url.get()}
   • Port: 5000

📡 Webhook URL (for TradingView):
   {webhook_url}


📧 Email Alerts: {'Enabled' if self.email_enabled.get() else 'Disabled'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Setup Complete!

To start the server, run:
   python server.py

Or use the start.bat file.
"""

            messagebox.showinfo("Setup Complete", success_message)

            self.status_label.config(
                text="● Setup Complete! ✓",
                fg=self.accent_green
            )

            # Ask if user wants to start server
            start_now = messagebox.askyesno(
                "Start Server",
                "Configuration complete!\n\n"
                "Do you want to start the server now?"
            )

            if start_now:
                self.start_server()
            else:
                self.root.quit()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate configuration:\n\n{str(e)}")
            self.status_label.config(text="● Error occurred", fg=self.accent_red)

    def start_server(self):
        """Start the trading bot server"""
        try:
            if not (self.base_dir / "server.py").exists():
                messagebox.showerror(
                    "Error",
                    "server.py not found!\n\n"
                    "Please ensure all project files are present."
                )
                return

            if sys.platform == "win32":
                # Use start.bat if available
                if (self.base_dir / "start.bat").exists():
                    subprocess.Popen(['start.bat'], shell=True, cwd=str(self.base_dir))
                else:
                    subprocess.Popen('start cmd /k python server.py', shell=True, cwd=str(self.base_dir))
            else:
                subprocess.Popen([sys.executable, "server.py"], cwd=str(self.base_dir))

            messagebox.showinfo(
                "Server Started",
                f"✓ Server is starting!\n\n"
                f"Access at: {self.external_base_url.get()}\n\n"
                f"Check the terminal window for server logs."
            )

            self.root.quit()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start server:\n\n{str(e)}")


def main():
    """Main entry point"""
    root = tk.Tk()
    app = SetupWizard(root)
    root.mainloop()


if __name__ == "__main__":
    main()

