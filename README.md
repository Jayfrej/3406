# 🚀 MT5 Trading Bot - Remote EA System

A professional, modular trading bot that connects **TradingView alerts** to **MetaTrader 5** accounts via a remote Expert Advisor (EA) system. Features include webhook-based signal processing, account-to-account copy trading, real-time monitoring, and comprehensive account management.

---

## ✨ Features

### **Core Functionality**
- 🔔 **TradingView Webhook Integration** - Receive and process trading signals from TradingView alerts
- 📊 **MT5 Remote EA System** - 100% remote-based account management (no local MT5 instances)
- 🔄 **Copy Trading** - Replicate trades from master accounts to slave accounts with customizable settings
- 📈 **Real-Time Monitoring** - Live account status tracking with heartbeat detection
- ⚙️ **Symbol Mapping** - Automatic symbol translation between brokers
- 📧 **Email Notifications** - Configurable alerts for important events

### **Account Management**
- Add/remove trading accounts remotely
- Real-time account status (Online/Offline/Pause)
- Account balance tracking
- Multi-broker support
- Pause/resume trading per account

### **Copy Trading**
- Multiple master-to-slave configurations
- Customizable volume multipliers
- Symbol mapping support
- PSL (Profit/Stop Loss) copying
- Trade history tracking

### **System Features**
- Modern, responsive web UI (dark/light themes)
- RESTful API architecture
- Rate limiting and security
- Comprehensive logging
- Session-based authentication

---

## 🏗️ Architecture

### **Technology Stack**
- **Backend**: Python 3.11+ with Flask
- **Frontend**: Vanilla JavaScript (modular architecture)
- **Templates**: Jinja2 with component-based structure
- **Styling**: Custom CSS (modular)
- **Database**: SQLite (accounts, configurations)
- **Communication**: REST API + Server-Sent Events (SSE)

### **Project Structure**
```
MT5-Trading-Bot/
├── server.py                      # Main Flask application
├── setup.py                       # Configuration wizard (GUI)
├── start.bat                      # Windows startup script
├── requirements.txt               # Python dependencies
├── .env.template                  # Environment variables template
│
├── app/                           # Backend modules
│   ├── __init__.py
│   ├── trades.py                  # Trade history tracking
│   │
│   ├── core/                      # Core utilities
│   │   ├── config.py              # Configuration management
│   │   └── email.py               # Email notifications
│   │
│   ├── services/                  # Business logic services
│   │   ├── accounts.py            # Account management (SessionManager)
│   │   ├── broker.py              # Broker data management
│   │   ├── signals.py             # Signal translation
│   │   ├── symbols.py             # Symbol mapping
│   │   └── balance.py             # Balance tracking
│   │
│   ├── modules/                   # Feature modules (Blueprints)
│   │   ├── webhooks/              # TradingView webhook handling
│   │   │   ├── __init__.py
│   │   │   ├── routes.py
│   │   │   └── services.py
│   │   ├── accounts/              # Account management API
│   │   │   ├── __init__.py
│   │   │   └── routes.py
│   │   └── system/                # System settings & logs
│   │       ├── __init__.py
│   │       └── routes.py
│   │
│   └── copy_trading/              # Copy trading module
│       ├── __init__.py
│       ├── copy_manager.py        # Pair management
│       ├── copy_handler.py        # Signal processing
│       ├── copy_executor.py       # Trade execution
│       └── copy_history.py        # History tracking
│
├── templates/                     # HTML templates (Jinja2)
│   ├── base.html                  # Master layout
│   ├── index.html                 # SPA entry point
│   ├── partials/                  # Reusable components
│   │   ├── sidebar.html
│   │   ├── header.html
│   │   └── components/
│   │       ├── loading.html
│   │       ├── toast.html
│   │       └── modals.html
│   └── pages/                     # Page templates
│       ├── accounts.html
│       ├── webhook.html
│       ├── copy_trading.html
│       ├── system.html
│       └── settings.html
│
├── static/                        # Frontend assets
│   ├── css/                       # Modular stylesheets
│   │   ├── base.css
│   │   ├── layout.css
│   │   ├── components.css
│   │   ├── toast.css
│   │   ├── modals.css
│   │   ├── responsive.css
│   │   └── pages/
│   │       ├── accounts.css
│   │       ├── webhook.css
│   │       ├── copy-trading.css
│   │       ├── system.css
│   │       └── settings.css
│   │
│   └── js/                        # Modular JavaScript
│       ├── core/                  # Core utilities
│       │   ├── utils.js
│       │   ├── api.js
│       │   ├── auth.js
│       │   ├── theme.js
│       │   └── router.js
│       ├── components/            # UI components
│       │   ├── toast.js
│       │   ├── modal.js
│       │   └── loading.js
│       ├── modules/               # Feature modules
│       │   ├── webhooks/
│       │   │   ├── webhooks.js
│       │   │   └── webhook-ui.js
│       │   ├── accounts/
│       │   │   ├── accounts.js
│       │   │   └── account-ui.js
│       │   ├── copy-trading/
│       │   │   ├── copy-trading.js
│       │   │   └── copy-trading-ui.js
│       │   ├── system/
│       │   │   ├── system.js
│       │   │   └── system-ui.js
│       │   └── settings/
│       │       ├── settings.js
│       │       └── settings-ui.js
│       ├── compat-bridge.js       # Backward compatibility
│       └── main.js                # Application coordinator
│
├── data/                          # Application data
│   ├── accounts.db                # SQLite database
│   ├── broker_data.json           # Broker configurations
│   ├── webhook_accounts.json      # Webhook allowlist
│   └── commands/                  # Command queue files
│
├── logs/                          # Application logs
│   └── trading_bot.log
│
└── ea/                            # MetaTrader 5 Expert Advisor
    └── All-in-One_EA.mq5          # MT5 EA source code
```

---

## 🚀 Quick Start

### **Prerequisites**
- **Python 3.11+** installed
- **MetaTrader 5** terminal (for running the EA)
- **Windows OS** (recommended)

### **Installation**

**1. Clone the repository:**
```bash
git clone <repository-url>
cd MT5-Trading-Bot
```

**2. Run the setup wizard:**
```bash
python setup.py
```

The setup wizard will guide you through:
1. **Initialize Project** - Create required directories
2. **Install Dependencies** - Install Python packages from requirements.txt
3. **Server Configuration** - Set username, password, and server URL
4. **Email Configuration** (Optional) - Configure email notifications
5. **Generate .env** - Create environment configuration file

**3. Start the server:**
```bash
# Windows
start.bat

# Or manually
python server.py
```

**4. Access the web interface:**
```
http://localhost:5000
```

**Default credentials** (can be changed during setup):
- Username: `admin`
- Password: (set during setup)

---

## 📋 Configuration

### **Environment Variables (.env)**

The `.env` file is automatically generated by `setup.py`. Key variables include:

```env
# Server Configuration
BASIC_USER=admin                          # Dashboard username
BASIC_PASS=your_password                  # Dashboard password
SECRET_KEY=auto_generated_32_bytes        # Flask secret key
WEBHOOK_TOKEN=auto_generated_16_bytes     # Webhook authentication token
EXTERNAL_BASE_URL=http://localhost:5000   # Server external URL
PORT=5000                                 # Server port
DEBUG=False                               # Debug mode (False for production)

# Email Notifications
EMAIL_ENABLED=true                        # Enable/disable email alerts
SENDER_EMAIL=your.email@gmail.com         # Sender email address
SENDER_PASSWORD=your_app_password         # Email app password
RECIPIENTS=alert@gmail.com                # Comma-separated recipients

# Advanced Settings
SYMBOL_FETCH_ENABLED=False                # Symbol fetching from MT5 API
FUZZY_MATCH_THRESHOLD=0.6                 # Symbol matching threshold
RATE_LIMIT_WEBHOOK=10 per minute          # Webhook rate limit
RATE_LIMIT_API=100 per hour               # API rate limit
LOG_LEVEL=INFO                            # Logging level
LOG_FILE=logs/trading_bot.log             # Log file path
```

---

## 🔧 Usage

### **1. Account Management**

**Add a New Account:**
1. Go to **Accounts** page
2. Click **"Add Account"**
3. Enter MT5 account number and nickname
4. Account status will be **"Wait for Activate"**
5. Run the EA on your MT5 terminal
6. Status will change to **"Online"** when EA connects

**Account Actions:**
- **Pause** - Stop processing signals temporarily
- **Resume** - Resume processing signals
- **Delete** - Remove account from system

### **2. Webhook Configuration**

**Get Your Webhook URL:**
1. Go to **Webhook** page
2. Copy the webhook URL displayed
3. Use this URL in TradingView alerts

**Add Webhook Account:**
1. Click **"Add Account"** in Webhook Configuration
2. Select account from dropdown
3. Account will receive signals from TradingView

**TradingView Alert Setup:**
```json
{
  "account_number": "123456",
  "symbol": "EURUSD",
  "action": "BUY",
  "volume": 0.01,
  "take_profit": 2450.0,
  "stop_loss": 2400.0,
  "secret": "XXX"
}
```

### **3. Copy Trading**

**Create a Copy Pair:**
1. Go to **Copy Trading** page
2. Click **"Add New Pair"**
3. Select Master account (source)
4. Select Slave account (destination)
5. Configure settings:
   - **Volume Mode**: Fixed, Multiply, Balance Ratio
   - **Multiplier**: Volume multiplier for slave
   - **Copy PSL**: Copy profit/stop loss levels
   - **Symbol Mapping**: Auto-map symbols between brokers
6. Click **"Create Pair"**

**Manage Copy Pairs:**
- **Enable/Disable** - Toggle pair active status
- **Edit** - Modify pair settings
- **Delete** - Remove copy pair
- **View History** - See copy trade history

### **4. System Monitoring**

**System Information:**
- Server status and uptime
- Account statistics (total, online, offline)
- Last health check timestamp
- Webhook and copy trading endpoints

**System Logs:**
- Real-time log streaming
- Filter by log level (info, success, warning, error)
- Clear logs functionality
- Export logs

---

## 🔌 API Endpoints

### **Authentication**
All endpoints require session-based authentication except webhook endpoints.

**Login:**
```http
POST /login
Content-Type: application/json

{
  "username": "admin",
  "password": "your_password"
}
```

### **Account Management**
```http
GET    /accounts                    # List all accounts
POST   /accounts                    # Add new account
DELETE /accounts/{account}          # Delete account
POST   /accounts/{account}/pause    # Pause account
POST   /accounts/{account}/resume   # Resume account
GET    /accounts/stats              # Get statistics
```

### **Webhook**
```http
POST /webhook/{token}               # Receive TradingView signals
GET  /webhook-accounts              # List webhook accounts
POST /webhook-accounts              # Add webhook account
```

### **Copy Trading**
```http
GET    /api/pairs                   # List copy pairs
POST   /api/pairs                   # Create copy pair
PUT    /api/pairs/{pair_id}         # Update copy pair
DELETE /api/pairs/{pair_id}         # Delete copy pair
POST   /api/copy/trade              # Receive master signals
GET    /api/copy/history            # Get copy history
```

### **System**
```http
GET  /health                        # Health check
GET  /api/settings                  # Get settings
POST /api/settings/rate-limits      # Update rate limits
POST /api/settings/email            # Update email settings
GET  /api/system/logs               # Get system logs
```

---

## 🛡️ Security

### **Authentication**
- Session-based authentication for dashboard
- Token-based authentication for webhooks
- Secure password hashing
- CSRF protection

### **Rate Limiting**
- Webhook endpoints: 10 requests per minute (configurable)
- API endpoints: 100 requests per hour (configurable)
- Protection against brute force attacks

### **Data Protection**
- Secure environment variable storage
- SQLite database with proper permissions
- No sensitive data in logs
- HTTPS support (configure reverse proxy)

---

## 📊 Database Schema

### **accounts.db (SQLite)**

**accounts** table:
```sql
CREATE TABLE accounts (
    account TEXT PRIMARY KEY,
    nickname TEXT,
    status TEXT DEFAULT 'Wait for Activate',
    broker TEXT,
    last_seen TEXT,
    created TEXT,
    symbol_mappings TEXT DEFAULT NULL,
    pid INTEGER DEFAULT NULL
);
```

**global_settings** table:
```sql
CREATE TABLE global_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    secret_key TEXT DEFAULT NULL,
    updated TEXT DEFAULT ''
);
```

---

## 🔄 How It Works

### **Signal Flow**

```
┌─────────────────┐
│  TradingView    │
│     Alert       │
└────────┬────────┘
         │ HTTP POST
         ▼
┌─────────────────┐
│   Webhook       │
│   Endpoint      │◄────── Token Authentication
└────────┬────────┘
         │ Validate & Parse
         ▼
┌─────────────────┐
│ Signal          │
│ Translator      │◄────── Symbol Mapping
└────────┬────────┘
         │ Translate to MT5 Format
         ▼
┌─────────────────┐
│  Command        │
│  Queue          │
└────────┬────────┘
         │ Write JSON Command
         ▼
┌─────────────────┐
│   MT5 EA        │
│ (Polling)       │◄────── Remote Connection
└────────┬────────┘
         │ Execute Trade
         ▼
┌─────────────────┐
│  MT5 Terminal   │
│  (User's PC)    │
└─────────────────┘
```

### **Copy Trading Flow**

```
┌─────────────────┐
│  Master EA      │
│  (Sends Signal) │
└────────┬────────┘
         │ HTTP POST with API Key
         ▼
┌─────────────────┐
│ Copy Handler    │◄────── Validate API Key
└────────┬────────┘
         │ Find Active Pairs
         ▼
┌─────────────────┐
│ Copy Executor   │◄────── Volume Calculation
│                 │◄────── Symbol Mapping
└────────┬────────┘
         │ Generate Slave Commands
         ▼
┌─────────────────┐
│ Command Queue   │◄────── Per-Slave Commands
└────────┬────────┘
         │ Write JSON Commands
         ▼
┌─────────────────┐
│  Slave EAs      │
│  (Multiple)     │◄────── Polling
└────────┬────────┘
         │ Execute Trades
         ▼
┌─────────────────┐
│ Slave Terminals │
│ (Multiple PCs)  │
└─────────────────┘
```

---

## 🧪 Testing

### **Run System Validation:**
```bash
python validate_system.py
```

This checks:
- ✅ All required files exist
- ✅ Directory structure is correct
- ✅ Templates are complete
- ✅ Static assets are present
- ✅ Python modules are available
- ✅ No legacy files remain
- ✅ Environment variables are valid
- ✅ Python syntax is correct

---

## 🐛 Troubleshooting

### **Common Issues**

**1. Port Already in Use**
```bash
# Change port in .env
PORT=5001
```

**2. EA Not Connecting**
- Check EXTERNAL_BASE_URL in .env matches your server address
- Verify firewall allows connections on configured port
- Ensure EA is running on MT5 with correct server URL

**3. Webhook 403 Forbidden**
- Verify WEBHOOK_TOKEN matches between .env and TradingView alert
- Check account is added to webhook allowlist

**4. Email Notifications Not Working**
- Use Gmail App Password (not regular password)
- Enable "Less secure apps" if using older Gmail account
- Check SMTP settings in .env

**5. Copy Trading Not Working**
- Verify both master and slave accounts are Online
- Check copy pair is enabled (status: active)
- Ensure API key is correctly configured in master EA
- Verify symbol mapping if using different brokers

---

## 📦 Dependencies

Key Python packages (see `requirements.txt` for complete list):
- **Flask 2.3.3** - Web framework
- **Flask-Limiter 2.8.1** - Rate limiting
- **Flask-Cors 4.0.0** - CORS support
- **python-dotenv 1.0.0** - Environment variables
- **psutil 5.9.6** - Process monitoring
- **requests 2.31.0** - HTTP client

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:
1. Fork the repository
2. Create a feature branch
3. Follow existing code style
4. Test thoroughly
5. Submit a pull request

---

## 📄 License

This project is proprietary software. All rights reserved.

---

## 🆘 Support

For support, please:
1. Check the troubleshooting section above
2. Review system logs in `logs/trading_bot.log`
3. Run validation script: `python validate_system.py`
4. Check GitHub issues for known problems

---

## 🎯 Roadmap

**Planned Features:**
- [ ] Google OAuth authentication
- [ ] PostgreSQL/Supabase database migration
- [ ] Payment integration (Paddle)
- [ ] Multi-language support
- [ ] Advanced analytics dashboard
- [ ] Mobile app
- [ ] Docker deployment
- [ ] Cloud hosting guides

---

## 📝 Changelog

### **v2.0.0** - Remote-Only Architecture
- ✅ Complete migration to 100% remote EA system
- ✅ Removed all local MT5 instance management
- ✅ Modular frontend (HTML, CSS, JS)
- ✅ Component-based template system
- ✅ Professional dark/light themes
- ✅ Improved error handling
- ✅ Enhanced security features
- ✅ Comprehensive documentation

### **v1.0.0** - Initial Release
- ✅ TradingView webhook integration
- ✅ Basic copy trading functionality
- ✅ Account management
- ✅ Web dashboard

---

## 🌟 Acknowledgments

Built with modern web technologies and best practices for professional trading automation.

**Technologies Used:**
- Python & Flask
- JavaScript (ES6+)
- HTML5 & CSS3
- SQLite
- MetaTrader 5 MQL5

---

**Made with ❤️ for traders worldwide** 🚀

