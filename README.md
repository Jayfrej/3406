# MT5 Multi-Account Webhook Trading Bot

A sophisticated web application designed to receive webhook signals from platforms like TradingView and execute trades across multiple MetaTrader 5 accounts simultaneously. This tool features a comprehensive user interface for managing accounts, monitoring instance status, and reviewing a detailed history log of all submitted orders. It also includes an integrated email notification system for alerts and a rate-limiting mechanism to prevent spam and ensure stable performance.


## Quick install

- [Installation](#installation)
- [Configuration](#configuration)
- [External Access](#external-access-cloudflare-tunnel)
- [Usage](#usage)
- [Webhook Integration](#webhook-integration)



## Quick Start

### Installation Steps
1. Install Python 3.8+ (check "Add Python to PATH")
2. Run setup: `python setup.py`
3. Configure MT5 profile (save as "Default")
4. Start bot: `python server.py`

### Enable External Access
1. Install cloudflared
2. Create tunnel
3. Configure DNS
4. Run tunnel

## System Architecture

### Complete System Overview (v3.0 - Multi-User SaaS)

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                     MT5 MULTI-USER SAAS TRADING PLATFORM                                           │
│                              (Webhook + Copy Trading + Google OAuth + Data Isolation)                              │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────┐     ┌──────────────────────┐                          ┌──────────────────────────────────┐
│   SIGNAL SOURCES     │     │   AUTHENTICATION     │                          │     SERVER COMPONENTS            │
│                      │     │                      │                          │  (project-root/)                 │
│  • TradingView       │     │  ┌────────────────┐  │                          │                                  │
│  • Pine Script       │     │  │ Google OAuth   │  │  POST /webhook/{TOKEN}   │  server.py                       │
│  • Custom Bots       │     │  │ 2.0 Login      │──┼────────────────────────> │  ├─ app/                         │
│  • Manual Trading    │     │  └────────────────┘  │                          │  │  ├─ services/                  │
└──────────────────────┘     │         │            │                          │  │  │  ├─ user_service.py         │
                             │         ▼            │                          │  │  │  ├─ token_service.py        │
                             │  ┌────────────────┐  │                          │  │  │  └─ google_oauth_service.py │
                             │  │ Per-User       │  │                          │  │  ├─ middleware/                │
                             │  │ Webhook Token  │  │                          │  │  │  └─ auth.py                 │
                             │  └────────────────┘  │                          │  │  ├─ session_manager.py         │
                             └──────────────────────┘                          │  │  ├─ email_handler.py           │
                                                                               │  │  └─ copy_trading/              │
                        ┌─────────────────────────────────────────────┐       │  ├─ static/                       │
                        │         FLASK SERVER (localhost:5000)       │       │  │  ├─ index.html                 │
                        │  ┌───────────────────────────────────────┐  │       │  │  ├─ login.html                 │
                        │  │  1. Authentication (v3.0)              │  │       │  │  └─ app.js                     │
                        │  │     • Google OAuth 2.0 (Primary)       │  │       │  ├─ data/                         │
                        │  │     • Per-User Webhook Tokens          │  │       │  │  ├─ accounts.db (SQLite)       │
                        │  │     • Session-based Security           │  │       │  │  │  ├─ users table             │
                        │  │     • Legacy Basic Auth (Fallback)     │  │       │  │  │  ├─ user_tokens table       │
                        │  │  2. Data Isolation (CRITICAL)          │  │       │  │  │  └─ accounts table          │
                        │  │     • All queries filter by user_id    │  │       │  │  ├─ copy_pairs.json            │
                        │  │     • Users see ONLY their own data    │  │       │  │  └─ api_keys.json              │
                        │  │  3. Rate Limiting                      │  │       │  ├─ logs/                          │
                        │  │     • 10 req/min (Webhook)             │  │       │  └─ .env                           │
                        │  │  4. Symbol Mapping                     │  │       └──────────────────────────────────┘
                        │  │     • Auto-mapping between brokers     │  │
                        │  └───────────────────────────────────────┘  │
                        └──────────────┬──────────────────────────────┘
                                       │
                                       │
                ┌──────────────────────┼──────────────────────┐
                │                      │                      │
                ▼                      ▼                      ▼
    ┌───────────────────┐  ┌────────────────────┐  ┌──────────────────┐
    │ WEBHOOK HANDLER   │  │  COPY TRADING      │  │  EMAIL HANDLER   │
    │ (TradingView)     │  │  (Master/Slave)    │  │  (Notifications) │
    │                   │  │                    │  │                  │
    │ Process:          │  │ Process:           │  │ Send Alerts:     │       ┌──────────────────────────────────┐
    │ • Parse JSON      │  │ • Validate API key │  │ • Startup        │       │   MT5 INSTANCE STRUCTURE         │
    │ • Validate fields │  │ • Find pairs       │  │ • Online/Offline │       │  (<InstanceRootPath>\<Account>\) │
    │ • Check account   │  │ • Map symbol       │  │ • Errors         │       │                                  │
    └─────────┬─────────┘  └──────────┬─────────┘  └──────────────────┘       │  <AccountNumber>\                │
              │                       │                                        │  ├─ terminal64.exe                │
              │                       │                                        │  ├─ MQL5\                         │
              ▼                       ▼                                        │  │  ├─ Experts\                    │
    webhook_command_*.json    slave_command_*.json                            │  │  │  └─ (All-in-One).mq5        │
              │                       │                                        │  │  └─ Files\                      │
              │                       │                                        │  │      ├─ webhook_command_*.json │
              └───────────────────────┼────────────────────────────────>      │  │      ├─ slave_command_*.json   │
                                      │                                        │  │      └─ instance_<Account>\    │
                                      ▼                                        │  └─ Data\ (Don't write here!)     │
              <InstanceRootPath>\<Account>\MQL5\Files\                         └──────────────────────────────────┘
                                      │
                                      │
                                      ▼
              ┌───────────────────────────────────────────────────┐
              │         MT5 INSTANCE (All-in-One EA v2.2)         │           ┌──────────────────────────────────┐
              │  ┌─────────────────────────────────────────────┐  │           │      EA MODES & ACTIONS          │
              │  │  MODE 1: WEBHOOK                            │  │           │                                  │
              │  │  • Poll: webhook_command_*.json (1-3 sec)   │  │           │  WEBHOOK MODE:                   │
              │  │  • Actions: BUY/SELL/CLOSE/CLOSE_ALL        │  │           │  ✓ Read JSON from Files\         │
              │  │  • Execute: Market/Limit/Stop orders        │  │           │  ✓ Parse action & parameters     │
              │  │  • Delete: File after processing            │  │           │  ✓ Execute trades                │
              │  └─────────────────────────────────────────────┘  │           │  ✓ Delete processed files        │
              │                                                   │           │                                  │
              │  ┌─────────────────────────────────────────────┐  │           │  MASTER MODE:                    │
              │  │  MODE 2: MASTER                             │  │           │  ✓ Monitor account positions     │
              │  │  • Send: POST /api/copy/trade               │  │           │  ✓ Detect: Open/Close/Modify     │
              │  │  • Events: OnOpen/OnClose/OnModify          │  │           │  ✓ Generate unique order_id      │
              │  │  • Auth: API Key from copy pair             │  │           │  ✓ POST to server with API key   │
              │  │  • Data: Symbol, Volume, TP, SL, order_id   │  │           │                                  │
              │  └─────────────────────────────────────────────┘  │           │  SLAVE MODE:                     │
              │                                                   │           │  ✓ Read JSON from Files\         │
              │  ┌─────────────────────────────────────────────┐  │           │  ✓ Execute copy trades           │
              │  │  MODE 3: SLAVE                              │  │           │  ✓ Apply volume calculations     │
              │  │  • Poll: slave_command_*.json (1-3 sec)     │  │           │  ✓ Set comment: COPY_order_xxx   │
              │  │  • Actions: BUY/SELL/CLOSE                  │  │           │  ✓ Delete processed files        │
              │  │  • Volume: Fixed/Multiply/Percent mode      │  │           └──────────────────────────────────┘
              │  │  • Comment: COPY_order_12345                │  │
              │  │  • Delete: File after processing            │  │
              │  └─────────────────────────────────────────────┘  │
              │                                                   │
              │      All modes can run simultaneously             │
              └───────────────────────────────────────────────────┘


┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                           DATA FLOW EXAMPLES                                                       │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐    ┌──────────────────────────────────────────────────┐
│  FLOW 1: WEBHOOK TRADING (TradingView → MT5)            │    │  FLOW 2: COPY TRADING (Master → Slave)           │
│                                                          │    │                                                   │
│  [1] TradingView Alert Triggered                        │    │  [1] Master Account Opens Position               │
│      └─> POST /webhook/abc123xyz                        │    │      └─> BUY EURUSD 1.0 lot                      │
│          {"action":"BUY","symbol":"XAUUSD",             │    │                                                   │
│           "volume":0.01,"tp":2450,"sl":2400}            │    │  [2] Master EA Detects Position                  │
│                                                          │    │      └─> POST /api/copy/trade                    │
│  [2] Flask Server Processes                             │    │          {"api_key":"xxx","event":"deal_add",    │
│      ✓ Token valid                                      │    │           "symbol":"EURUSD","volume":1.0,        │
│      ✓ Rate limit OK                                    │    │           "order_id":"order_12345"}              │
│      ✓ JSON parsed                                      │    │                                                   │
│                                                          │    │  [3] Copy Handler Processes                      │
│  [3] Symbol Mapper Converts                             │    │      ✓ API key valid                             │
│      └─> XAUUSD found in Market Watch                   │    │      ✓ Found 2 active pairs                      │
│                                                          │    │      ✓ Symbol: EURUSD → EURUSD (no change)      │
│  [4] Session Manager Checks                             │    │                                                   │
│      ✓ Account 12345 exists                             │    │  [4] Volume Calculator                           │
│      ✓ MT5 instance online                              │    │      • Slave 1 (Fixed): 1.0 → 0.01 lot          │
│                                                          │    │      • Slave 2 (Multiply): 1.0 × 0.5 = 0.5 lot  │
│  [5] File Writer Creates                                │    │                                                   │
│      └─> C:\MT5_Instances\12345\MQL5\Files\             │    │  [5] File Writer Creates (per slave)             │
│          webhook_command_1234567890.json                │    │      └─> C:\MT5_Instances\67890\MQL5\Files\      │
│                                                          │    │          slave_command_1234567890.json           │
│  [6] MT5 EA (Webhook Mode)                              │    │                                                   │
│      • Detects new file                                 │    │  [6] Slave EA (Slave Mode)                       │
│      • Reads JSON                                       │    │      • Detects new file                          │
│      • Executes: BUY XAUUSD 0.01 lot                    │    │      • Reads JSON                                │
│      • Deletes file                                     │    │      • Executes: BUY EURUSD 0.01 lot             │
│                                                          │    │      • Comment: COPY_order_12345                 │
│  [7] Email Alert Sent                                   │    │      • Deletes file                              │
│      └─> "✓ Position opened: BUY XAUUSD 0.01"          │    │                                                   │
│                                                          │    │  [7] Copy History Updated                        │
│  [8] Response to TradingView                            │    │      └─> SSE broadcast to Web UI                 │
│      └─> 200 OK                                         │    │          Status: Success                         │
└─────────────────────────────────────────────────────────┘    └──────────────────────────────────────────────────┘


┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                     VOLUME CALCULATION MODES (Copy Trading)                                        │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  MODE 1: FIXED                                                                                                     │
│  Formula: Slave volume = Fixed value (ignore master volume)                                                       │
│  Example: Master 1.0 lot → Slave always 0.01 lot                                                                  │
│           Master 2.0 lot → Slave always 0.01 lot                                                                  │
│                                                                                                                    │
│  MODE 2: MULTIPLY                                                                                                  │
│  Formula: Slave volume = Master volume × Multiplier                                                               │
│  Example: Master 1.0 lot × 0.5 = Slave 0.5 lot                                                                    │
│           Master 2.0 lot × 0.5 = Slave 1.0 lot                                                                    │
│                                                                                                                    │
│  MODE 3: PERCENT (Balance-Based)                                                                                  │
│  Formula: Slave volume = (Slave Balance / Master Balance) × Master Volume × Multiplier                           │
│  Example: Master $10,000 balance, 1.0 lot                                                                         │
│           Slave $5,000 balance                                                                                    │
│           Result: (5000/10000) × 1.0 × 2.0 = 1.0 lot                                                              │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### File Patterns Reference

**Webhook Commands** (TradingView → MT5)
```
webhook_command_1234567890.json
webhook_command_1234567891.json
webhook_command_*.json  ← EA polls this pattern
```

**Slave Commands** (Master → Slave via Copy Trading)
```
slave_command_1234567890.json
slave_command_1234567891.json
slave_command_*.json  ← EA polls this pattern
```

**Important Notes:**
-  Files are written to: `<InstanceRootPath>\<Account>\MQL5\Files\`
-  DO NOT write to: `<InstanceRootPath>\<Account>\Data\`
-  Polling interval: 1-3 seconds (configurable in EA)
-  Files are auto-deleted after processing

### JSON Command Structure

```json
{
  "timestamp": "2025-09-29T10:30:00",
  "account": "1123456",
  "action": "BUY",
  "symbol": "XAUUSD",
  "original_symbol": "XAUUSDM",
  "volume": 0.01,
  "take_profit": 2450.0,
  "stop_loss": 2400.0
}
```


## Key Features

### Core Functionality
- **Webhook Integration** - Receive trading commands via `POST /webhook/<token>`
  - Supports actions: `BUY/SELL/LONG/SHORT`, `CLOSE`, `CLOSE_ALL`, `CLOSE_SYMBOL`
- **Multi-Account Management** - Create/Open/Stop/Restart/Delete accounts through UI
- **Real-time History Log** - Command history with Server-Sent Events (SSE) + Clear button
- **Health Monitoring** - System health checks via `GET /health` and `GET /webhook/health`

### Security & Protection
- **Basic Authentication** - Password-protected UI interface
- **Rate Limiting** - Configurable webhook rate limits
- **Token-based Access** - Secure webhook endpoint authentication

### Monitoring & Alerts
- **Email Notifications** - Alert system for critical events:
  - System startup
  - Instance online/offline status
  - Payload validation errors
  - Trading execution alerts
  
  **Note**: System does NOT send emails for Basic Auth failures from `127.0.0.1` or internal health checks to reduce false alarms

### Trading Features
- **Portable MT5 Instances** - Each account runs in isolated instance
- **Symbol Auto-Mapping** - Intelligent symbol mapping with fuzzy matching
- **Market & Pending Orders** - Execute instant BUY/SELL, LIMIT, and STOP orders
- **Position Management** - Close specific positions, symbol positions, or all positions


## Requirements

### System Requirements
- **OS**: Windows 10/11 (64-bit) - [Download Windows 11](https://www.microsoft.com/software-download/windows11)
- **Python**: 3.8+ - [Download Python](https://www.python.org/downloads/)
- **RAM**: 4GB minimum (8GB+ for multiple instances)
- **Disk Space**: 500MB per MT5 instance
- **MetaTrader 5**: Installed and configured - [Download MT5](https://www.metatrader5.com/en/download)

### Python Dependencies
```
Flask==2.3.3
Flask-Limiter==2.8.1
python-dotenv==1.0.0
psutil==5.9.6
requests==2.31.0
werkzeug==2.3.7
```

---

## Installation

### Step 1: Install Python
Download Python 3.8+ from [python.org](https://www.python.org/downloads/)
- Check "Add Python to PATH" during installation

### Step 2: Run Setup Wizard
```bash
python setup.py
```

**The wizard will:**
- Check system requirements
- Install dependencies automatically
- Create directory structure
- Configure profile source
- Generate security credentials
- Setup email notifications (optional)

### Step 3: Prepare MT5 Profile
1. Open your main MT5 installation
2. Login and configure your profile as desired
3. Navigate to: `File → Open Data Folder`
4. Copy the full path
5. Paste path into setup wizard when prompted
6. Save profile as "Default"

### Step 4: Install Expert Advisor
1. Copy `ea/(All-in-One).mq5` to `MT5/MQL5/Experts/`
2. Open MetaEditor
3. Compile the EA
4. Restart MT5

---

## Configuration

### Environment Variables (.env)

```env
# Server Configuration
SECRET_KEY=your-secret-key-here
BASIC_USER=admin
BASIC_PASS=your-secure-password

# Webhook Configuration
WEBHOOK_TOKEN=your-webhook-token-here
EXTERNAL_BASE_URL=http://localhost:5000

# Email Notifications (Optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USER=your-email@gmail.com
EMAIL_PASS=your-app-password
ALERT_EMAIL=alerts@example.com

# Rate Limiting
WEBHOOK_RATE_LIMIT=10 per minute
API_RATE_LIMIT=20 per minute

# Instance Configuration
INSTANCE_ROOT_PATH=C:\MT5_Instances
MT5_PROFILE_SOURCE=C:\Users\YourName\AppData\Roaming\MetaQuotes\Terminal\XXXXXXXX\profiles\Default
```

### Rate Limiting Configuration

Rate limits can be configured in `.env`:
- `WEBHOOK_RATE_LIMIT`: Requests per minute for webhook endpoint (default: 10)
- `API_RATE_LIMIT`: Requests per minute for API endpoints (default: 20)

Changes require server restart to take effect.

---

## External Access (Cloudflare Tunnel)

### Install Cloudflared

**Download:**
- Windows: [https://github.com/cloudflare/cloudflared/releases](https://github.com/cloudflare/cloudflared/releases)

**Install:**
```powershell
# Move to Program Files
move cloudflared.exe "C:\Program Files\cloudflared\"

# Add to PATH
$env:Path += ";C:\Program Files\cloudflared"
```

### Setup Tunnel

**Login:**
```powershell
cloudflared tunnel login
```

**Create Tunnel:**
```powershell
cloudflared tunnel create mt5-bot
```

**Configure (config.yml):**
```yaml
tunnel: YOUR_TUNNEL_ID
credentials-file: C:\Users\<Username>\.cloudflared\YOUR_TUNNEL_ID.json

ingress:
  - hostname: webhook.yourdomain.com
    service: http://127.0.0.1:5000
    
  - hostname: yourdomain.com
    service: http://127.0.0.1:5000
    
  - service: http_status:404
```

### Setup DNS & Run

**Configure DNS (choose one):**

**Option A - Command Line:**
```powershell
cloudflared tunnel route dns mt5-bot webhook.yourdomain.com
cloudflared tunnel route dns mt5-bot yourdomain.com
```

**Option B - Cloudflare Dashboard:**
1. Go to DNS settings
2. Add CNAME record:
   - Name: `webhook` or `@`
   - Target: `YOUR_TUNNEL_ID.cfargotunnel.com`
   - Proxy: Enable (orange cloud)

**Run Tunnel:**
```powershell
cloudflared tunnel run mt5-bot
```

**Update .env:**
```env
EXTERNAL_BASE_URL=https://webhook.yourdomain.com
```

### Security Configuration (Recommended)

#### Cloudflare Firewall Rules

**Allow correct webhook endpoint:**
```
(http.request.uri.path eq "/webhook/YOUR_TOKEN" and http.request.method eq "POST")
```

**Block incorrect webhook attempts:**
```
(http.request.uri.path matches "^/webhook/.*" and http.request.uri.path ne "/webhook/YOUR_TOKEN")
```

#### Rate Limiting
- Set 10 requests/minute for `/webhook/*`
- Enable Bot Fight Mode: ON

---

## Usage

### Start the Bot

```bash
python server.py
```

**Access:**
- Local: `http://localhost:5000`
- External: `https://trading.yourdomain.com`

### Add MT5 Account

1. Open web interface
2. Click "Add MT5 Account"
3. Enter account number and nickname
4. Click "Add Account"
5. MT5 terminal opens automatically - login with your credentials

### Manage Accounts

- **Restart**: Stop and restart instance
- **Stop**: Terminate MT5 process
- **Open**: Start offline instance
- **Delete**: Remove instance and files

### View Command History

- Real-time command log displayed in UI
- Updates via Server-Sent Events (SSE)
- Clear history with "Clear" button

### Check System Health

**Endpoints:**
- `GET /health` - Overall system health
- `GET /webhook/health` - Webhook endpoint health

---

## Webhook Integration

### TradingView Setup

1. Create Alert in TradingView
2. Enable "Webhook URL"
3. Paste: `https://trading.yourdomain.com/webhook/YOUR_TOKEN`
4. Configure alert message (JSON format)

### JSON Payload Examples

**Open BUY Position:**
```json
{
  "action": "BUY",
  "symbol": "XAUUSD",
  "volume": 0.01,
  "take_profit": 2450.0,
  "stop_loss": 2400.0
}
```

**Close All Positions:**
```json
{
  "action": "CLOSE_ALL"
}
```

**Close Symbol Positions:**
```json
{
  "action": "CLOSE_SYMBOL",
  "symbol": "XAUUSD"
}
```

### Test Webhook

**Test via Local:**

```powershell
$body = @{
    action = "BUY"
    symbol = "XAUUSD"
    volume = 0.01
    take_profit = 2450.0
    stop_loss = 2400.0
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:5000/webhook/YOUR_TOKEN" `
    -Method POST -ContentType "application/json" -Body $body
```

### Test via Cloudflare

```powershell
Invoke-WebRequest -Uri "https://trading.yourdomain.com/webhook/YOUR_TOKEN" `
    -Method POST -ContentType "application/json" -Body $body
```

### Test Health Endpoints

```powershell
# System health
Invoke-WebRequest -Uri "http://localhost:5000/health"

# Webhook health
Invoke-WebRequest -Uri "http://localhost:5000/webhook/health"
```


## Best Practices

### Security

- Use strong passwords for Basic Auth
- Rotate webhook tokens every 3-6 months
- Enable email alerts for critical events
- Always use HTTPS (Cloudflare Tunnel)
- Keep software updated
- Review logs regularly

### Trading

- Start with 0.01 lot size
- Test on demo accounts first
- Always use stop loss
- Monitor execution daily
- Have manual backup plan
- Review command history regularly

### Maintenance

| Frequency | Tasks |
|-----------|-------|
| **Daily** | Check command history, verify instance status |
| **Weekly** | Review logs, check system health endpoints |
| **Monthly** | Clean logs, update packages, backup configs |
| **Quarterly** | Full system update, security audit, token rotation |


## Important Warnings

**Risk Warning**  
Trading involves significant loss risk. This bot executes YOUR strategy - it does NOT make trading decisions.

**System Requirements**  
Stable internet, powered-on Windows system, sufficient resources required 24/7.

**Security**  
Never share webhook token, use strong passwords, enable 2FA, review logs regularly.

**Testing**  
ALWAYS test on demo accounts first with minimum lot sizes.

**Email Alerts**  
Email system filters out Basic Auth failures from localhost/health-checks to prevent spam. Configure alerts appropriately.


## Backup

### Critical Files

```
.env
data/accounts.db
data/custom_mappings.json
data/copy_pairs.json
config.yml (if using Cloudflare)
.cloudflared/ (if using Cloudflare)
logs/trading_bot.log
```

### Backup Command

```bash
xcopy .env backup\ /Y
xcopy data backup\data\ /Y /E
xcopy config.yml backup\ /Y
xcopy logs backup\logs\ /Y /E
```

### Automated Backup Script

Create `backup.bat`:
```batch
@echo off
set BACKUP_DIR=backup\%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%
mkdir %BACKUP_DIR%
xcopy .env %BACKUP_DIR%\ /Y
xcopy data %BACKUP_DIR%\data\ /Y /E
xcopy config.yml %BACKUP_DIR%\ /Y
echo Backup completed: %BACKUP_DIR%
```


## Support

**For issues:**
1. Check logs: `logs/trading_bot.log`
2. Check system health: `GET /health`
3. Review command history in UI
4. Verify `.env` configuration
5. Test Cloudflare Tunnel connectivity
6. Check email notifications settings

---

**Version**: 1.0.0  
**Compatible**: MT5 Build 3801+, Python 3.8+, Windows 10/11

**Remember**: Discipline, risk management, and continuous learning are keys to successful trading. Use this tool wisely.

---
---

#  Update 2.0 - Copy Trading System (October 24, 2025)

### Overview

Version 2.0 introduces **Master-Slave Copy Trading** that automatically replicates trades from Master accounts to multiple Slave accounts in real-time.

---

###  Key Features

#### 1. Master-Slave Architecture

- **Master Account**: Sends trading signals to server via HTTP API with unique API key
- **Slave Account**: Receives and executes commands via JSON file bridge
- **Real-time Tracking**: Order ID system ensures precise position matching

#### 2. Volume Management Modes

**Fixed Mode**: Slave always trades fixed lot size
```
Master 1.0 lot → Slave 0.01 lot (always)
```

**Multiply Mode**: Slave volume = Master volume × Multiplier
```
Master 1.0 lot × 2 = Slave 2.0 lots
```

**Percent Mode**: Balance-based calculation
```
Slave volume = (Slave Balance / Master Balance) × Master Volume × Multiplier
Example: (5000/10000) × 1.0 × 2 = 1.0 lot
```

#### 3. Intelligent Symbol Mapping

- Auto-converts symbols between different brokers (XAUUSD → GOLD)
- Fuzzy matching finds closest symbol when exact match unavailable
- Custom mappings via UI

#### 4. Selective TP/SL Copying

- **Enabled**: Slave copies exact TP/SL from Master
- **Disabled**: Slave uses EA defaults or no TP/SL
- Useful for different risk management per account

#### 5. Position Tracking

Each position tracked via unique Order ID in comment: `COPY_order_12345`

#### 6. Real-Time History

- Live event log via Server-Sent Events
- Filter by Success/Error
- Shows Master/Slave, Action, Symbol, Volume, Timestamp

---

###  Technical Details

#### New API Endpoints
```
POST   /api/copy/trade              # Master EA sends signals
GET    /api/copy/pairs              # List copy pairs
POST   /api/copy/pairs              # Create pair
DELETE /api/copy/pairs/<id>         # Delete pair
POST   /api/copy/pairs/<id>/toggle  # Toggle active/inactive
GET    /api/copy/history            # Get history
DELETE /api/copy/history            # Clear history
GET    /events/copy-trades          # SSE real-time updates
```

#### EA Configuration

**Master Mode:**
```
EnableMaster = true
Master_ServerURL = "http://localhost:5000"
Master_APIKey = "your-api-key-from-pair"
Master_SendOnOpen = true
Master_SendOnClose = true
Master_SendOnModify = true
```

**Slave Mode:**
```
EnableSlave = true
Slave_AutoLinkInstance = true
Slave_InstanceRootPath = "C:\\MT5_Instances"
Slave_FilePattern = "slave_command_*.json"
Slave_PollingSeconds = 1
```

---

###  Quick Setup

#### Step 1: Add Master Account
1. Go to **Copy Trading** page
2. Click **"Add Master Account"**
3. Enter account number and nickname
4. Ensure status is **Online**

#### Step 2: Add Slave Account
1. Click **"Add Slave Account"** or **"Add from server"**
2. Enter/select account
3. Verify status is **Online**

#### Step 3: Create Copy Pair
1. Click **"Create New Pair"**
2. Select Master and Slave accounts
3. Configure:
   - Auto Map Symbol
   - Auto Map Volume
   - Copy TP/SL
   - Volume Mode (Fixed/Multiply/Percent)
   - Multiplier
4. Copy the generated **API Key**

#### Step 4: Configure EAs

**Master EA:**
- Paste API key into `Master_APIKey`
- Set `Master_ServerURL`
- Enable send on open/close/modify

**Slave EA:**
- Set `Slave_InstanceRootPath`
- Enable auto link instance

#### Step 5: Test
1. Open position on Master
2. Watch Copy History for events
3. Verify position on Slave with correct volume and symbol

---

###  Usage Examples

**Fixed Volume:**
```
Settings: Fixed, 0.01
Master 2.0 lots → Slave 0.01 lots
```

**Multiply Mode:**
```
Settings: Multiply, 0.5
Master 1.0 lot → Slave 0.5 lots
Master 2.0 lots → Slave 1.0 lot
```

**Percent Mode:**
```
Settings: Percent, 2.0, Master $10k, Slave $5k
Master 1.0 lot → Slave (5000/10000) × 1.0 × 2.0 = 1.0 lot
```

**Symbol Mapping:**
```
Settings: Auto Map Symbol enabled
Master XAUUSD → Slave GOLD (auto-converted)
```

---

###  Troubleshooting

**Slave doesn't execute:**
- Verify pair status is Active
- Check Slave account is Online
- Confirm Slave EA shows `[SLAVE] FileBridge ready`
- Check `Slave_InstanceRootPath` is correct

**Wrong volume:**
- Review Volume Mode and Multiplier
- For Percent mode, verify balances detected
- Check logs for volume calculation

**Symbol not found:**
- Enable Auto Map Symbol
- Verify symbol in Slave's Market Watch
- Add custom mapping if needed

**API Key Invalid:**
- Copy exact key from UI (no spaces)
- Paste into Master EA's `Master_APIKey`
- Restart Master EA

---

###  Advanced Features

#### Multiple Configurations

**One Master → Multiple Slaves:**
```
Master (11111111)
  ├─ Slave (22222222) - Fixed 0.01
  ├─ Slave (33333333) - Multiply 0.5x
  └─ Slave (44444444) - Percent 2.0x
```

**Multiple Masters → One Slave:**
```
Slave (22222222)
  ├─ Master (11111111) - API Key A
  └─ Master (55555555) - API Key B
```

**Cascade (Master → Slave → Slave):**
```
Master (11111111)
  └─ Slave (22222222) [EnableMaster=true]
       └─ Slave (33333333)
```

#### Network Options

**Local (Recommended):**
```
Master_ServerURL = "http://192.168.1.100:5000"
```

**External (Cloudflare):**
```
Master_ServerURL = "https://trading.yourdomain.com"
```

---

###  New Data Files

```
data/copy_pairs.json        # Copy pair definitions & API keys
data/copy_history.json      # Last 1000 copy events
```

**Include in backups!**

---

###  Migration from v1.0

1. Update code to v2.0
2. Run `python server.py`
3. Server auto-creates new files
4. All existing data preserved
5. No manual migration needed

---

###  Copy Trading API

#### POST /api/copy/trade

**Request:**
```json
{
  "api_key": "your-api-key",
  "event": "deal_add",
  "order_id": "order_12345",
  "account": "11111111",
  "symbol": "XAUUSD",
  "type": "BUY",
  "volume": 1.0,
  "tp": 2450.0,
  "sl": 2400.0
}
```

**Events:** `deal_add`, `deal_close`, `position_modify`

**Response:**
```json
{
  "success": true,
  "message": "Signal processed",
  "pairs_processed": 1
}
```

---

**Version 2.0.0 - Copy Trading Update**  
**Release Date**: October 24, 2025  
**Compatible**: MT5 Build 3801+, Python 3.8+, Windows 10/11  
**EA Version**: All-in-One Trading EA v2.2

---

---

# 🚀 Update 3.0 - Multi-User SaaS Platform (December 5, 2025)

### Overview

Version 3.0 transforms the MT5 Trading Bot from a single-user system into a **Multi-Tenant SaaS Platform** with Google OAuth authentication, per-user data isolation, and enterprise-grade security.

---

### 🔑 Key Features

#### 1. Google OAuth 2.0 Authentication

- **One-Click Login**: Sign in with Google account - no password management
- **Secure Sessions**: Server-side session management with secure cookies
- **Auto User Creation**: New users automatically provisioned on first login
- **Profile Integration**: User name and picture synced from Google

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTHENTICATION FLOW                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [User] ──► /login ──► [Google OAuth] ──► /auth/callback        │
│                              │                                  │
│                              ▼                                  │
│                    ┌─────────────────┐                         │
│                    │ Create/Update   │                         │
│                    │ User in DB      │                         │
│                    └────────┬────────┘                         │
│                             │                                   │
│                             ▼                                   │
│                    ┌─────────────────┐                         │
│                    │ Generate        │                         │
│                    │ Webhook Token   │                         │
│                    └────────┬────────┘                         │
│                             │                                   │
│                             ▼                                   │
│                    ┌─────────────────┐                         │
│                    │ Set Session     │                         │
│                    │ Redirect to /   │                         │
│                    └─────────────────┘                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 2. Per-User Webhook Tokens

- **Unique Token Per User**: Each user gets their own webhook URL
- **Token Management**: View, copy, and rotate tokens from dashboard
- **Legacy Support**: Old `WEBHOOK_TOKEN` still works for backward compatibility

```
User A: POST /webhook/whk_abc123...  → Only User A's accounts
User B: POST /webhook/whk_xyz789...  → Only User B's accounts
Legacy: POST /webhook/{WEBHOOK_TOKEN} → Admin accounts (fallback)
```

#### 3. Strict Data Isolation

- **Database Level**: All queries filter by `user_id`
- **JSON Files**: Copy pairs tagged with owner `user_id`
- **API Security**: Users can ONLY see/modify their own data

```sql
-- Every query enforces isolation:
SELECT * FROM accounts WHERE user_id = ?
SELECT * FROM copy_pairs WHERE user_id = ?
```

#### 4. Admin Dashboard

- **User Management**: View all users, toggle active status
- **System Overview**: Global statistics across all users
- **Support Access**: Admins can view data for troubleshooting

#### 5. Enhanced Security

- **Session-Based Auth**: No more Basic Auth for UI (optional fallback)
- **CSRF Protection**: State validation in OAuth flow
- **Type-Safe Queries**: Parameterized SQL prevents injection
- **Proper HTTP Codes**: 401 (Unauthorized) vs 403 (Forbidden)

---

### 📊 Database Schema (v3.0)

```sql
-- NEW: Users table
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,        -- 'user_john_abc123'
    email TEXT UNIQUE NOT NULL,      -- Google email
    name TEXT,                       -- Display name
    picture TEXT,                    -- Profile picture URL
    is_active INTEGER DEFAULT 1,     -- Account enabled
    is_admin INTEGER DEFAULT 0,      -- Admin privileges
    created_at TEXT,
    last_login TEXT
);

-- NEW: Per-user webhook tokens
CREATE TABLE user_tokens (
    token_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    webhook_token TEXT UNIQUE NOT NULL,  -- 'whk_xxx...'
    webhook_url TEXT,
    created_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- UPDATED: Accounts now linked to users
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account TEXT UNIQUE,
    nickname TEXT,
    status TEXT DEFAULT 'inactive',
    broker TEXT,
    user_id TEXT,                    -- NEW: Owner
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
```

---

### 🛠️ New API Endpoints

#### Authentication Routes
```
GET  /login              # Login page
GET  /login/google       # Start Google OAuth
GET  /auth/callback      # OAuth callback
POST /logout             # Clear session
GET  /auth/status        # Check auth status
GET  /auth/webhook-token # Get user's webhook token
POST /auth/rotate-token  # Generate new token
```

#### User Management (Admin)
```
GET  /api/admin/users           # List all users
POST /api/admin/users/:id/toggle # Enable/disable user
GET  /api/admin/stats           # System statistics
```

---

### 🚀 Simple Setup Flow

#### Step 1: Configure Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create project → Enable OAuth consent screen
3. Create OAuth 2.0 credentials
4. Add authorized redirect URI: `http://localhost:5000/auth/google/callback`
5. Copy Client ID and Secret

#### Step 2: Update Environment

```env
# Add to .env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
ADMIN_EMAIL=your-admin@gmail.com
SECRET_KEY=your-secure-random-key
```

#### Step 3: Run Setup

```bash
python setup.py
```

The setup wizard will:
- ✅ Detect existing database
- ✅ Create new tables (users, user_tokens)
- ✅ Add user_id column to accounts
- ✅ Migrate existing data to admin user
- ✅ Preserve all existing configurations

#### Step 4: Start Server

```bash
python server.py
```

#### Step 5: Login

1. Open `http://localhost:5000`
2. Click "Sign in with Google"
3. Authorize the application
4. You're in! 🎉

---

### 📋 Migration Guide

#### From v2.0 to v3.0

**Automatic Migration:**
- All existing accounts assigned to admin user
- All existing copy pairs tagged with admin user_id
- Webhook routes support both old and new tokens

**Manual Steps:**
1. Update `.env` with Google OAuth credentials
2. Run `python setup.py` to migrate database
3. Restart server

**Backward Compatibility:**
- Old `WEBHOOK_TOKEN` still works (maps to admin)
- Basic Auth fallback available during transition
- All v2.0 API endpoints unchanged

---

### 🔐 Security Best Practices

#### Production Deployment

```env
# Required for production
GOOGLE_CLIENT_ID=xxx
GOOGLE_CLIENT_SECRET=xxx
SECRET_KEY=<random-64-char-string>
ADMIN_EMAIL=admin@yourdomain.com

# HTTPS required for OAuth
EXTERNAL_BASE_URL=https://trading.yourdomain.com
```

#### OAuth Redirect URIs

For production, add to Google Console:
```
https://trading.yourdomain.com/auth/google/callback
```

---

### 📁 New File Structure

```
app/
├─ services/                 # NEW: Business logic services
│  ├─ user_service.py        # User CRUD operations
│  ├─ token_service.py       # Webhook token management
│  ├─ google_oauth_service.py # OAuth flow handling
│  └─ auth_service.py        # Authentication helpers
├─ middleware/
│  └─ auth.py                # UPDATED: OAuth + session auth
├─ routes/
│  ├─ auth_routes.py         # NEW: OAuth endpoints
│  └─ ... (existing routes updated for multi-user)
└─ core/
   ├─ app_factory.py         # UPDATED: OAuth integration
   └─ database_init.py       # UPDATED: New schema

static/
├─ login.html                # NEW: Google OAuth login page
└─ index.html                # UPDATED: Session-based auth

data/
└─ accounts.db               # UPDATED: users, user_tokens tables
```

---

### 🧪 Testing

**Multi-User Isolation Test:**
```bash
python tests/test_multi_user_isolation.py
```

**Expected Output:**
```
✅ PASS: database_schema
✅ PASS: json_files
✅ PASS: session_manager
✅ PASS: copy_manager

All tests passed!
```

---

### ⚠️ Breaking Changes

1. **Login Required**: Dashboard now requires Google login
2. **User-Scoped Data**: APIs return only current user's data
3. **Webhook URLs**: New per-user token format

**Mitigation:**
- Legacy `WEBHOOK_TOKEN` still supported
- Admin users see all data
- Basic Auth fallback available

---

### 🐛 Bug Fixes in v3.0

- **Fixed**: `datatype mismatch` error in token generation
- **Fixed**: Hardcoded `admin_001` fallback now dynamically finds admin
- **Fixed**: Type hints for authentication functions
- **Fixed**: Schema consistency across all database operations

---

### 📚 Documentation Updates

- System Architecture diagram updated for Multi-User model
- New authentication flow documentation
- API endpoint changes documented
- Migration guide included

---

**Version 3.0.0 - Multi-User SaaS Platform**  
**Release Date**: December 5, 2025  
**Compatible**: MT5 Build 3801+, Python 3.8+, Windows 10/11  
**EA Version**: All-in-One Trading EA v2.2  
**New Requirements**: Google OAuth credentials

---

### 🎯 What's Next (Roadmap)

- **v3.1**: User dashboard with personal statistics
- **v3.2**: Team/organization support
- **v3.3**: API rate limits per user tier
- **v4.0**: Multi-broker support

---

**Thank you for using MT5 Multi-User Trading Platform!**  
Questions? Issues? Create a ticket or contact support.

---

