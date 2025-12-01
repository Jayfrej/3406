//+------------------------------------------------------------------+
//|                                        AllInOneTradingEA.mq5     |
//|                    Multi-Mode: Webhook + Master + Slave          |
//|  v3.11 - API-ONLY MODE! Centralized API, Atomic Lock Fix            |
//+------------------------------------------------------------------+
#property copyright "MT5 Trading Bot"
#property link      "https://github.com/Jayferj"
#property version   "3.11"
#property strict

//==================== Enums ====================
enum ENUM_LOG_LEVEL
{
   LOG_DEBUG,        // Debug (All messages)
   LOG_INFO,         // Info (Important events)
   LOG_WARNING,      // Warning (Potential issues)
   LOG_ERROR         // Error (Critical issues only)
};

//==================== Input Parameters ====================
input group "=== Mode Selection (Multi-Select) ==="
input bool EnableWebhook = false;                          // ? Enable Webhook Mode
input bool EnableMaster = false;                           // ? Enable Master Mode
input bool EnableSlave = false;                            // ? Enable Slave Mode

input group "=== API Settings (Centralized) ==="
input string API_ServerURL = "http://localhost:5000";      // Server URL (used by all modes)
input int    API_PollSeconds = 1;                          // API poll interval (seconds) - faster = lower latency
input int    API_Timeout = 1000;                           // API request timeout (ms) - reduced for faster transmission

input group "=== Webhook Settings ==="
input bool WebhookCloseOppositeBeforeOpen = false;    // Close opposite positions before opening (Webhook only - Slave uses 100% copy)
input bool WebhookAutoCloseBySymbol = true;          // Auto close by symbol if no ticket/comment/index (Webhook)

input group "=== Master Settings ==="
input string Master_APIKey = "";                           // API Key (from Copy Pair)
input bool   Master_SendOnOpen = true;                     // Send signal on position open
input bool   Master_SendOnClose = true;                    // Send signal on position close
input bool   Master_SendOnModify = true;                   // Send signal on TP/SL modify

input group "=== Trade Settings ==="
input double DefaultVolume = 0.10;                         // Default volume
input int    Slippage = 10;                                // Slippage (points)
input string TradeComment = "AllInOneEA";                  // Trade comment
input long   MagicNumberInput = 0;                         // Magic number (0 = auto)

input group "=== Logging ==="
input bool EnableLogging = true;                           // Enable logging
input ENUM_LOG_LEVEL LogLevel = LOG_INFO;                  // Log level

// ===== 🔥 BEGIN ATOMIC LOCK GLOBALS (NEW) =====
bool g_is_processing_master = false;          // ป้องกัน race condition ใน CheckMasterPositions
datetime g_last_master_process_time = 0;      // เวลาที่ประมวลผลครั้งล่าสุด
// ===== END ATOMIC LOCK GLOBALS =====
// === BEGIN ORDER MAPPING GLOBALS (added) ===
// 🔥 Map เพื่อติดตาม Master Comment → Slave Ticket
struct OrderMapping {
   string master_comment;
   ulong  slave_ticket;
   string symbol;
   double volume;
   datetime created_time;
};

OrderMapping g_order_map[];
int g_map_count = 0;
// === END ORDER MAPPING GLOBALS (added) ===

// === BEGIN ORDER MAPPING HELPERS (added) ===
// เพิ่ม mapping ใหม่
void AddOrderMapping(string comment, ulong ticket, string symbol, double volume) {
   ArrayResize(g_order_map, g_map_count + 1);
   g_order_map[g_map_count].master_comment = comment;
   g_order_map[g_map_count].slave_ticket = ticket;
   g_order_map[g_map_count].symbol = symbol;
   g_order_map[g_map_count].volume = volume;
   g_order_map[g_map_count].created_time = TimeCurrent();
   g_map_count++;

   LogMessage(LOG_INFO, "[MAP] Added: " + comment + " → " + IntegerToString((int)ticket));
}

// หา ticket จาก comment
ulong FindTicketByComment(string comment) {
   for(int i = 0; i < g_map_count; i++) {
      if(g_order_map[i].master_comment == comment) {
         LogMessage(LOG_DEBUG, "[MAP] Found: " + comment + " → " + IntegerToString((int)g_order_map[i].slave_ticket));
         return g_order_map[i].slave_ticket;
      }
   }
   LogMessage(LOG_WARNING, "[MAP] Not found: " + comment);
   return 0;
}

// อัพเดท ticket หลัง partial close
void UpdateTicketMapping(string comment, ulong new_ticket, double new_volume) {
   for(int i = 0; i < g_map_count; i++) {
      if(g_order_map[i].master_comment == comment) {
         ulong old_ticket = g_order_map[i].slave_ticket;
         g_order_map[i].slave_ticket = new_ticket;
         g_order_map[i].volume = new_volume;
         LogMessage(LOG_INFO, "[MAP] Updated: " + comment + " ticket " + IntegerToString((int)old_ticket) + " → " + IntegerToString((int)new_ticket));
         return;
      }
   }
}

// ลบ mapping เมื่อ position ปิดหมด
void RemoveOrderMapping(string comment) {
   for(int i = 0; i < g_map_count; i++) {
      if(g_order_map[i].master_comment == comment) {
         LogMessage(LOG_INFO, "[MAP] Removed: " + comment);
         // Shift array elements
         for(int j = i; j < g_map_count - 1; j++) {
            g_order_map[j] = g_order_map[j + 1];
         }
         g_map_count--;
         ArrayResize(g_order_map, g_map_count);
         return;
      }
   }
}
// === END ORDER MAPPING HELPERS (added) ===

// 🔥 ฟังก์ชันปัดเศษ volume ให้ถูกต้องตาม broker requirements
double RoundVolumeToValidStep(string symbol, double volume) {
   double volume_step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   double volume_min = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double volume_max = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   
   LogMessage(LOG_DEBUG, "[VOLUME_CHECK] Symbol: " + symbol + 
              " | Input: " + DoubleToString(volume, 3) +
              " | Step: " + DoubleToString(volume_step, 3) +
              " | Min: " + DoubleToString(volume_min, 3) +
              " | Max: " + DoubleToString(volume_max, 3));
   
   if(volume <= 0.0) return 0.0;
   
   // ปัดเศษให้ตรงกับ volume_step
   double rounded = MathRound(volume / volume_step) * volume_step;
   
   // ตรวจสอบขอบเขต
   if(rounded < volume_min) rounded = volume_min;
   if(rounded > volume_max) rounded = volume_max;
   
   // ถ้าปัดแล้วได้ 0 ให้ใช้ volume_min
   if(rounded <= 0.0) rounded = volume_min;
   
   LogMessage(LOG_INFO, "[VOLUME_FIX] " + symbol + ": " + 
              DoubleToString(volume, 3) + " → " + DoubleToString(rounded, 3));
   
   return rounded;
}



// === BEGIN TrackAndUpdateMapping (added/replaced) ===
void TrackAndUpdateMapping(string symbol, string comment, double expected_volume) {
   LogMessage(LOG_INFO, "[SLAVE] 🔎 Tracking new position after partial close: " + symbol + " volume=" + DoubleToString(expected_volume, 2));

   Sleep(500); // รอให้ MT5 สร้าง position ใหม่

   // หา position ใหม่ที่มี volume ตรงกับที่คาดหวัง
   for(int i = 0; i < PositionsTotal(); i++) {
      ulong new_ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(new_ticket)) continue;

      string pos_symbol = PositionGetString(POSITION_SYMBOL);
      double pos_volume = PositionGetDouble(POSITION_VOLUME);

      // เช็คว่าเป็น position ที่เหลือจาก partial close หรือไม่
      if(pos_symbol == symbol && MathAbs(pos_volume - expected_volume) < 0.001) {

         // เช็คว่า ticket นี้ไม่อยู่ใน map แล้ว
         bool ticket_exists = false;
         for(int j = 0; j < g_map_count; j++) {
            if(g_order_map[j].slave_ticket == new_ticket) {
               ticket_exists = true;
               break;
            }
         }

         if(!ticket_exists) {
            LogMessage(LOG_INFO, "[SLAVE] 🎯 Found remaining position: ticket=" + IntegerToString((int)new_ticket));

            // อัพเดท Map ด้วย ticket ใหม่
            UpdateTicketMapping(comment, new_ticket, expected_volume);
            return;
         }
      }
   }

   LogMessage(LOG_WARNING, "[SLAVE] Could not find remaining position after partial close");
}
// === END TrackAndUpdateMapping (added/replaced) ===







//==================== Global Variables ====================
string AccountNumber;
long   g_magic = 0;
bool   Initialized = false;


// Master tracking arrays
ulong MasterTickets[];
string MasterSymbols[];
int MasterTypes[];
double MasterVolumes[];
double MasterTPs[];
double MasterSLs[];

// 🔥 Pending Orders tracking array
ulong MasterPendingTickets[];

// 🔥 Master Position Tracking - Batch Processing Support

// Thread-safe counter and locks
int g_processing_counter = 0;

// ⭐ Broker Data Scanner
bool g_broker_data_sent = false;  // ส่งข้อมูลโบรกเกอร์แล้วหรือยัง

// ⭐ Hard-coded Constants (ไม่มี User Settings)
const double FUZZY_MATCH_THRESHOLD = 0.75;  // Hard-coded: 0.75
const bool ENABLE_FUZZY_MATCH = true;       // Hard-coded: เปิดเสมอ
const bool SCANNER_ENABLED = true;          // Hard-coded: เปิดเสมอ
const bool SCANNER_FORCE_RESEND = false;    // Hard-coded: ส่งทุกรอบ (ไม่เช็ค flag)
const int HEARTBEAT_INTERVAL = 30;          // Hard-coded: 30 วินาที

// ⭐ Balance Tracker
datetime g_last_balance_send = 0;  // เวลาที่ส่ง balance ครั้งล่าสุด
int g_balance_send_interval = 300;  // Heartbeat: ส่งอย่างน้อยทุก 5 นาที
double g_last_balance = 0;  // Balance ครั้งล่าสุดที่ส่ง
double g_last_equity = 0;  // Equity ครั้งล่าสุดที่ส่ง
double g_balance_change_threshold = 0.5;  // ส่งเมื่อเปลี่ยน > 0.5%

// ⭐ Remote Mode Heartbeat
datetime g_last_heartbeat_time = 0;  // เวลาที่ส่ง heartbeat ครั้งล่าสุด

// ⭐ Balance Update Check Cache
bool g_balance_update_needed = false;  // ต้องส่ง balance หรือไม่
datetime g_last_balance_check = 0;  // เวลาที่เช็คครั้งล่าสุด
int g_balance_check_interval = 60;  // เช็คทุก 60 วินาที


//==================== Imports ====================
#import "shell32.dll"
int ShellExecuteW(int hwnd, string lpOperation, string lpFile, string lpParameters, string lpDirectory, int nShowCmd);
#import

//==================== Utility Functions ====================
string ToLower(string s) { StringToLower(s); return s; }
long ComputeAutoMagic() { 
   long lg = (long)AccountInfoInteger(ACCOUNT_LOGIN);
   if(lg <= 0) return 999999;
   return lg % 1000000;
}
string DataFolder() { return TerminalInfoString(TERMINAL_DATA_PATH); }
string FilesRoot() { return DataFolder() + "\\MQL5\\Files"; }

string NormalizePath(string p) {
   string q = p;
   StringToLower(q);
   StringReplace(q, "/", "\\");
   while(StringLen(q) > 0 && StringGetCharacter(q, (int)StringLen(q)-1) == '\\')
      q = StringSubstr(q, 0, (int)StringLen(q)-1);
   return q;
}

bool FolderExistsUnderFiles(const string sub) {
   string found = "";
   long h = FileFindFirst(sub + "\\*.*", found, 0);
   if(h == INVALID_HANDLE) return false;
   FileFindClose(h);
   return true;
}

bool CreateJunction(const string dst_abs, const string src_abs) {
   string cmd = "C:\\Windows\\System32\\cmd.exe";
   string args = "/c mklink /J \"" + dst_abs + "\" \"" + src_abs + "\"";
   int r = ShellExecuteW(0, "runas", cmd, args, "", 1);
   if(r > 32) LogMessage(LOG_INFO, "Junction created: " + dst_abs);
   else LogMessage(LOG_ERROR, "Failed to create junction");
   return (r > 32);
}

//==================== Robust JSON Parser ====================
int NextNonSpace(const string s, int i) {
   int n = (int)StringLen(s);
   while(i < n) {
      int ch = StringGetCharacter(s, i);
      if(ch != ' ' && ch != '\t' && ch != '\r' && ch != '\n') break;
      i++;
   }
   return i;
}

string GetVal(const string json, const string key) {
   string jlow = json, klow = key;
   StringToLower(jlow);
   StringToLower(klow);
   
   int p = StringFind(jlow, "\"" + klow + "\"");
   int token = (p != -1) ? (int)StringLen(key) + 2 : 0;
   if(p == -1) {
      p = StringFind(jlow, "'" + klow + "'");
      if(p == -1) return "";
      token = (int)StringLen(key) + 2;
   }
   
   int colon = StringFind(json, ":", p + token);
   if(colon == -1) return "";
   int i = NextNonSpace(json, colon + 1);
   int ch = StringGetCharacter(json, i);
   
   if(ch == '\"' || ch == '\'') {
      int quote = ch;
      i++;
      int q = i, n = (int)StringLen(json);
      while(q < n && StringGetCharacter(json, q) != quote) q++;
      if(q >= n) return "";
      return StringSubstr(json, i, q - i);
   }
   
   int q = i, n = (int)StringLen(json);
   while(q < n) {
      ch = StringGetCharacter(json, q);
      if(ch == ',' || ch == '}' || ch == ']' || ch == '\r' || ch == '\n') break;
      q++;
   }
   string v = StringSubstr(json, i, q - i);
   StringTrimLeft(v);
   StringTrimRight(v);
   return v;
}

//==================== Symbol Resolution ====================
string AlnumUpper(const string s) {
   string out = "";
   for(int i = 0; i < (int)StringLen(s); ++i) {
      int ch = StringGetCharacter(s, i);
      if((ch >= '0' && ch <= '9') || (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z')) {
         if(ch >= 'a' && ch <= 'z') ch = ch - 'a' + 'A';
         uchar uc8 = (uchar)ch;
         out += CharToString(uc8);
      }
   }
   return out;
}

string ResolveSymbol(const string want) {
   if(want == "") return "";
   string base = want;
   
   if(SymbolSelect(base, true)) return base;
   
   string want_up = base;
   StringToUpper(want_up);
   for(int i = 0; i < SymbolsTotal(false); ++i) {
      string s = SymbolName(i, false);
      string su = s;
      StringToUpper(su);
      if(su == want_up) {
         SymbolSelect(s, true);
         return s;
      }
   }
   
   string want_norm = AlnumUpper(base);
   int bestScore = -100000;
   string best = "";
   for(int i = 0; i < SymbolsTotal(false); ++i) {
      string s = SymbolName(i, false);
      string sn = AlnumUpper(s);
      int score = -1000;
      if(sn == want_norm) score = 100;
      else {
         int pos = StringFind(sn, want_norm);
         if(pos == 0) score = 90 - (int)(StringLen(sn) - StringLen(want_norm));
         else if(StringFind(want_norm, sn) == 0) score = 80 - (int)(StringLen(want_norm) - StringLen(sn));
         else if(pos >= 0) score = 70 - (int)(StringLen(sn) - StringLen(want_norm));
      }
      if(score > bestScore) {
         bestScore = score;
         best = s;
      }
   }
   if(best != "") {
      SymbolSelect(best, true);
      return best;
   }
   
   return "";
}

//==================== ⭐ NEW: Enhanced Fuzzy Symbol Matching ====================

// คำนวณ Similarity Score ระหว่าง 2 string (0.0 - 1.0)
double CalculateSimilarity(const string str1, const string str2) {
   if(str1 == "" || str2 == "") return 0.0;
   string s1 = str1, s2 = str2;
   StringToLower(s1);
   StringToLower(s2);
   // Exact match
   if(s1 == s2) return 1.0;
   // Contains match
   if(StringFind(s1, s2) >= 0 || StringFind(s2, s1) >= 0) return 0.9;
   // Levenshtein-like simple scoring
   int len1 = (int)StringLen(s1);
   int len2 = (int)StringLen(s2);
   int maxLen = MathMax(len1, len2);
   if(maxLen == 0) return 0.0;
   int matches = 0;
   int minLen = MathMin(len1, len2);
   for(int i = 0; i < minLen; i++) {
      if(StringGetCharacter(s1, i) == StringGetCharacter(s2, i)) {
         matches++;
      }
   }
   return (double)matches / (double)maxLen;
}

// Normalize Symbol (ลบ suffix/prefix ที่ไม่จำเป็น)
string NormalizeSymbol(const string symbol) {
   if(symbol == "") return "";
   string normalized = symbol;
   StringToLower(normalized);
   // ลบ suffix ที่พบบ่อย
   string suffixes[] = {".m", "m", "dm", "sm", ".mini", ".micro", ".cash", ".spot", ".pro", ".ecn", ".raw", "_m", "_mini", "_micro"};
   for(int i = 0; i < ArraySize(suffixes); i++) {
      int pos = StringFind(normalized, suffixes[i]);
      if(pos >= 0 && pos == (int)StringLen(normalized) - (int)StringLen(suffixes[i])) {
         normalized = StringSubstr(normalized, 0, pos);
         break;
      }
   }
   // ลบ prefix ที่พบบ่อย
   string prefixes[] = {"m_", "mini_", "micro_", "fx_", "forex_", "cfd_"};
   for(int i = 0; i < ArraySize(prefixes); i++) {
      if(StringFind(normalized, prefixes[i]) == 0) {
         normalized = StringSubstr(normalized, (int)StringLen(prefixes[i]));
         break;
      }
   }
   // ลบตัวเลขท้ายสุด
   int len = (int)StringLen(normalized);
   while(len > 0) {
      int ch = StringGetCharacter(normalized, len - 1);
      if(ch >= '0' && ch <= '9') {
         len--;
      } else {
         break;
      }
   }
   if(len < (int)StringLen(normalized)) {
      normalized = StringSubstr(normalized, 0, len);
   }
   return normalized;
}

// ⭐ Fuzzy Symbol Resolver (Hard-coded: Always Enabled)
string ResolveSymbolFuzzy(const string want) {
   if(want == "") return "";
   // ✅ Hard-coded: Fuzzy Match เปิดเสมอ
   // ใช้ threshold แบบ hard-coded
   double threshold = FUZZY_MATCH_THRESHOLD;  // ✅ Hard-coded: 0.75
   string wantLower = want;
   StringToLower(wantLower);
   // Step 1: Exact match (case-insensitive)
   for(int i = 0; i < SymbolsTotal(false); i++) {
      string sym = SymbolName(i, false);
      string symLower = sym;
      StringToLower(symLower);
      if(symLower == wantLower) {
         SymbolSelect(sym, true);
         LogMessage(LOG_INFO, "[FUZZY_MATCH] ✅ Exact match: " + want + " → " + sym);
         return sym;
      }
   }
   // Step 2: Normalized exact match
   string wantNorm = NormalizeSymbol(want);
   for(int i = 0; i < SymbolsTotal(false); i++) {
      string sym = SymbolName(i, false);
      string symNorm = NormalizeSymbol(sym);
      if(symNorm == wantNorm) {
         SymbolSelect(sym, true);
         LogMessage(LOG_INFO, "[FUZZY_MATCH] ✅ Normalized match: " + want + " → " + sym);
         return sym;
      }
   }
   // Step 3: Fuzzy matching with score
   string bestMatch = "";
   double bestScore = threshold;
   for(int i = 0; i < SymbolsTotal(false); i++) {
      string sym = SymbolName(i, false);
      // Score 1: Direct similarity
      double score1 = CalculateSimilarity(wantLower, sym);
      // Score 2: Normalized similarity
      double score2 = CalculateSimilarity(wantNorm, NormalizeSymbol(sym));
      // Use best score
      double score = MathMax(score1, score2);
      if(score > bestScore) {
         bestScore = score;
         bestMatch = sym;
      }
   }
   if(bestMatch != "") {
      SymbolSelect(bestMatch, true);
      LogMessage(LOG_INFO, "[FUZZY_MATCH] ✅ Fuzzy match: " + want + " → " + bestMatch + " (score: " + DoubleToString(bestScore, 2) + ")");
      return bestMatch;
   }
   // Step 4: Contains match (fallback)
   for(int i = 0; i < SymbolsTotal(false); i++) {
      string sym = SymbolName(i, false);
      string symLower = sym;
      StringToLower(symLower);
      if(StringFind(symLower, wantLower) >= 0 || StringFind(wantLower, symLower) >= 0) {
         SymbolSelect(sym, true);
         LogMessage(LOG_INFO, "[FUZZY_MATCH] ✅ Contains match: " + want + " → " + sym);
         return sym;
      }
   }
   LogMessage(LOG_WARNING, "[FUZZY_MATCH] ❌ No match found for: " + want);
   return "";
}


//==================== Trading Functions ====================
double NormalizeLots(const string sym, double vol) {
   double step = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
   if(step > 0 && vmin > 0) {
      vol = MathMax(vmin, MathFloor(vol / step) * step);
      vol = MathMin(vol, vmax);
   }
   return vol;
}

bool SendOrderAdvanced(string action, string order_type, string sym,
                      double volume, double price, double sl, double tp,
                      string comment, string exp_iso, string source = "")
{
   // Thread-safe counter increment
   g_processing_counter++;
   int process_id = g_processing_counter;
   
   LogMessage(LOG_DEBUG, "[" + IntegerToString(process_id) + "] Processing " + source + " order: " + action + " " + sym);
   
   string realSym = ResolveSymbolFuzzy(sym);
   if(realSym == "") {
      LogMessage(LOG_ERROR, "[" + IntegerToString(process_id) + "] Cannot resolve symbol: " + sym);
      return false;
   }
   
   MqlTick t;
   if(!SymbolInfoTick(realSym, t)) {
      LogMessage(LOG_ERROR, "[" + IntegerToString(process_id) + "] No tick for " + realSym);
      return false;
   }
   
   double useLots = NormalizeLots(realSym, (volume > 0 ? volume : DefaultVolume));
   if(useLots <= 0) {
      LogMessage(LOG_ERROR, "[" + IntegerToString(process_id) + "] Volume is zero after normalization");
      return false;
   }
   
   int digits = (int)SymbolInfoInteger(realSym, SYMBOL_DIGITS);
   double pnorm = (price > 0 ? NormalizeDouble(price, digits) : 0.0);
   double sln = (sl > 0 ? NormalizeDouble(sl, digits) : 0.0);
   double tpn = (tp > 0 ? NormalizeDouble(tp, digits) : 0.0);
   
   string act = ToLower(action), ot = ToLower(order_type);
   if(act == "long") act = "buy";
   if(act == "short") act = "sell";
   if(act == "call") act = "buy";
   if(act == "put") act = "sell";

   // ✅ Safety: if order_type looks like action (buy/sell/call/put), force market order
   if(ot == "buy" || ot == "sell" || ot == "long" || ot == "short" || ot == "call" || ot == "put" || ot == "open") {
      ot = "market";
      LogMessage(LOG_WARNING, "[" + IntegerToString(process_id) + "] order_type looks like action (" + order_type + "), forcing market order");
   }

   // Pre-close opposite positions if enabled (WEBHOOK mode only - NOT Slave/Master)
   // 🔥 Slave mode ต้อง copy Master 100% ไม่ใช้ reversal logic เพราะ Master จะส่งคำสั่งมาให้แล้ว
   // ✅ ตรวจสอบ EnableWebhook แทนการเช็ค source เพราะ Webhook และ Slave ใช้ source="API" เหมือนกัน

   // 🔍 Debug: แสดงสถานะ flags ทั้งหมด
   LogMessage(LOG_DEBUG, "[REVERSAL_CHECK] EnableWebhook=" + (EnableWebhook ? "YES" : "NO") +
                         " EnableSlave=" + (EnableSlave ? "YES" : "NO") +
                         " Setting=" + (WebhookCloseOppositeBeforeOpen ? "ON" : "OFF") +
                         " Action=" + act);

   if(EnableWebhook && WebhookCloseOppositeBeforeOpen && (act == "buy" || act == "sell")) {
      LogMessage(LOG_INFO, "[REVERSAL] ✅ WebhookCloseOppositeBeforeOpen ACTIVE - checking for opposite positions");
      CloseOppositePositionsBySymbol(realSym, act, source);
   }
   else if(WebhookCloseOppositeBeforeOpen && (act == "buy" || act == "sell")) {
      // แสดงเหตุผลว่าทำไมไม่ trigger
      if(!EnableWebhook) {
         LogMessage(LOG_WARNING, "[REVERSAL] ⚠️ WebhookCloseOppositeBeforeOpen NOT triggered: EnableWebhook=FALSE (need to enable Webhook mode)");
      }
      else if(EnableSlave) {
         LogMessage(LOG_WARNING, "[REVERSAL] ⚠️ WebhookCloseOppositeBeforeOpen NOT triggered: EnableSlave=TRUE (Slave mode doesn't use reversal)");
      }
   }

   MqlTradeRequest req;
   ZeroMemory(req);
   MqlTradeResult res;
   ZeroMemory(res);
   
   req.symbol = realSym;
   req.volume = useLots;
   req.magic = (MagicNumberInput > 0 ? MagicNumberInput : ComputeAutoMagic());
   req.comment = (comment != "" ? comment : TradeComment + "_" + source);
   req.deviation = Slippage;
   // ✅ TP/SL Support: set from parameters (0 = no TP/SL)
   req.sl = sln;  // Stop Loss price
   req.tp = tpn;  // Take Profit price
   
   // ✅ MARKET ORDER: execute immediately at current price
   if(ot == "" || ot == "market") {
      req.action = TRADE_ACTION_DEAL;
      req.type_filling = ORDER_FILLING_FOK;
      if(act == "buy") {
         req.type = ORDER_TYPE_BUY;
         req.price = t.ask;
      } else {
         req.type = ORDER_TYPE_SELL;
         req.price = t.bid;
      }
   }
   // ✅ PENDING ORDERS: require price parameter
   // Supported types: buy_limit, sell_limit, buy_stop, sell_stop
   else {
      if(pnorm <= 0) {
         LogMessage(LOG_ERROR, "[" + IntegerToString(process_id) + "] Pending order (" + ot + ") requires price > 0");
         return false;
      }

      // Auto-prefix with buy_/sell_ if only "limit" or "stop" is provided
      if(ot == "limit" || ot == "stop")
         ot = (act == "buy" ? "buy_" + ot : "sell_" + ot);

      if(ot == "buy_limit") req.type = ORDER_TYPE_BUY_LIMIT;
      else if(ot == "sell_limit") req.type = ORDER_TYPE_SELL_LIMIT;
      else if(ot == "buy_stop") req.type = ORDER_TYPE_BUY_STOP;
      else if(ot == "sell_stop") req.type = ORDER_TYPE_SELL_STOP;
      else {
         LogMessage(LOG_ERROR, "[" + IntegerToString(process_id) + "] Unknown order_type: " + order_type + " (supported: market, buy_limit, sell_limit, buy_stop, sell_stop)");
         return false;
      }

      req.action = TRADE_ACTION_PENDING;
      req.price = pnorm;
      req.type_time = ORDER_TIME_GTC;
   }
   
   ResetLastError();
   bool ok = OrderSend(req, res);

// === BEGIN MAP WRITE (updated) ===
if(ok && res.order > 0) {
   if(comment != "") {
      // รอให้ position ถูกสร้างจริงๆ
      Sleep(100);
      
      // หา position ที่เพิ่งเปิด
      ulong actual_ticket = 0;
      for(int i = 0; i < PositionsTotal(); i++) {
         ulong check_ticket = PositionGetTicket(i);
         if(PositionSelectByTicket(check_ticket)) {
            if(PositionGetString(POSITION_SYMBOL) == sym && 
               PositionGetString(POSITION_COMMENT) == comment) {
               actual_ticket = check_ticket;
               break;
            }
         }
      }
      
      if(actual_ticket > 0) {
         AddOrderMapping(comment, actual_ticket, sym, volume);
      } else {
         LogMessage(LOG_WARNING, "[MAP] Could not find position for: " + comment);
      }
   }
}
// === END MAP WRITE (updated) ===

   if(!ok) {
      LogMessage(LOG_ERROR, "[" + IntegerToString(process_id) + "] Order failed: ret=" + IntegerToString(res.retcode) + " err=" + IntegerToString(GetLastError()) + " " + res.comment);
      return false;
   }
   
   LogMessage(LOG_INFO, "[" + IntegerToString(process_id) + "] Order executed: " + act + " " + realSym + " " + DoubleToString(useLots, 2) + " @ " + DoubleToString(res.price, 5));
   return true;
}

bool ClosePositionsByAmount(string sym, double reqVolume, string source = "") {
   g_processing_counter++;
   int process_id = g_processing_counter;
   
   LogMessage(LOG_DEBUG, "[" + IntegerToString(process_id) + "] Processing " + source + " close: " + sym + " volume: " + DoubleToString(reqVolume, 2));
   
   string realSym = ResolveSymbol(sym);
   if(realSym == "") {
      LogMessage(LOG_ERROR, "[" + IntegerToString(process_id) + "] Cannot resolve symbol: " + sym);
      return false;
   }
   
   // หา positions ทั้งหมดของ symbol นี้
   ulong tickets[];
   double volumes[];
   int count = 0;
   
   for(int i = 0; i < PositionsTotal(); i++) {
      ulong t = PositionGetTicket(i);
      if(!PositionSelectByTicket(t)) continue;
      if(PositionGetString(POSITION_SYMBOL) != realSym) continue;
      
      ArrayResize(tickets, count + 1);
      ArrayResize(volumes, count + 1);
      tickets[count] = t;
      volumes[count] = PositionGetDouble(POSITION_VOLUME);
      count++;
   }
   
   if(count == 0) {
      LogMessage(LOG_INFO, "[" + IntegerToString(process_id) + "] No positions to close for " + realSym);
      return false;
   }
   
   double totalVol = 0.0;
   for(int i = 0; i < count; i++) {
      totalVol += volumes[i];
   }
   
   LogMessage(LOG_INFO, "[" + IntegerToString(process_id) + "] Found " + IntegerToString(count) + " positions, total volume: " + DoubleToString(totalVol, 2));
   
   double target = reqVolume;
   if(target <= 0.0 || target >= totalVol - 1e-8) {
      target = totalVol;
      LogMessage(LOG_INFO, "[" + IntegerToString(process_id) + "] Closing all positions");
   } else {
      LogMessage(LOG_INFO, "[" + IntegerToString(process_id) + "] 🔥 Partial closing: " + DoubleToString(target, 2) + " of " + DoubleToString(totalVol, 2));
   }
   
   double remaining = target;
   bool any = false;
   
   // ปิด positions ทีละตัว จนกว่าจะครบ volume ที่ต้องการ
   for(int i = 0; i < count && remaining > 0.001; i++) {
      double lotsToClose = MathMin(volumes[i], remaining);
      
      if(lotsToClose >= volumes[i] - 0.00001) {
         // Close ทั้งหมด
         if(ClosePositionByTicket(tickets[i], source)) {
            any = true;
            remaining -= volumes[i];
            LogMessage(LOG_INFO, "[" + IntegerToString(process_id) + "] Closed full position: " + DoubleToString(volumes[i], 2) + " lots");
         }
      } else {
         // Partial close
         if(ClosePositionByTicketAndVolume(tickets[i], lotsToClose, source)) {
            any = true;
            remaining -= lotsToClose;
            LogMessage(LOG_INFO, "[" + IntegerToString(process_id) + "] 🔥 Partial closed: " + DoubleToString(lotsToClose, 2) + " lots");
         }
      }
   }
   
   LogMessage(LOG_INFO, "[" + IntegerToString(process_id) + "] Close operation completed. Success: " + (any ? "Yes" : "No"));
   return any;
}



bool CloseAllPositionsBySymbol(string sym, string source = "SLAVE") {
   string realSym = ResolveSymbol(sym);
   if(realSym == "") {
      LogMessage(LOG_ERROR, "[CLOSE_ALL] Cannot resolve symbol: " + sym);
      return false;
   }
   double total = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; --i) {
      ulong t = PositionGetTicket(i);
      if(!PositionSelectByTicket(t)) continue;
      if(PositionGetString(POSITION_SYMBOL) != realSym) continue;
      total += PositionGetDouble(POSITION_VOLUME);
   }
   if(total <= 0.0) return false;
   return ClosePositionsByAmount(sym, total, source);
}

// 🔥 NEW FUNCTION - Partial Close by Comment + Volume
// === BEGIN ClosePositionByCommentAndVolume (replaced) ===
bool ClosePositionByCommentAndVolume(string target_comment, double target_volume, string source = "SLAVE") {
   LogMessage(LOG_DEBUG, "[SLAVE] Finding position with comment: " + target_comment + " to close volume: " + DoubleToString(target_volume, 2));

   // 🔥 ใช้ Map หา ticket แทนการ loop หา comment
   ulong ticket = FindTicketByComment(target_comment);
   if(ticket == 0) {
      LogMessage(LOG_WARNING, "[SLAVE] Position not found in map: " + target_comment);
      return false;
   }

   if(!PositionSelectByTicket(ticket)) {
      LogMessage(LOG_WARNING, "[SLAVE] Position ticket not exist: " + IntegerToString((int)ticket));
      RemoveOrderMapping(target_comment); // ลบออกจาก map
      return false;
   }

   string symbol = PositionGetString(POSITION_SYMBOL);
   double current_volume = PositionGetDouble(POSITION_VOLUME);

   if(target_volume >= current_volume - 0.00001) {
      // Close ทั้งหมด
      LogMessage(LOG_INFO, "[SLAVE] Closing full position: " + target_comment);
      bool result = ClosePositionByTicket(ticket, source);
      if(result) {
         RemoveOrderMapping(target_comment); // ลบออกจาก map
      }
      return result;
   } else {
      // Partial close
      LogMessage(LOG_INFO, "[SLAVE] 🔥 Partial closing: " + target_comment + " volume: " + DoubleToString(target_volume, 2));
      bool result = ClosePositionByTicketAndVolume(ticket, target_volume, source);
      if(result) {
         // 🔥 ติดตาม position ใหม่หลัง partial close
         TrackAndUpdateMapping(symbol, target_comment, current_volume - target_volume);
      }
      return result;
   }
}
// === END ClosePositionByCommentAndVolume (replaced) ===



// 🔥 NEW FUNCTION - Partial Close by Ticket + Volume
// 🔥 ฟังก์ชันติดตาม position ใหม่หลัง partial close
void TrackNewPositionAfterPartialClose(string symbol, int original_type, double expected_volume, string original_comment) {
   LogMessage(LOG_INFO, "[SLAVE] 🔎 Tracking new position: " + symbol + " volume=" + DoubleToString(expected_volume, 2) + " comment=" + original_comment);
   
   // รอให้ MT5 สร้าง position ใหม่
   Sleep(500); // รอ 0.5 วินาที
   
   // ค้นหา position ใหม่ที่ไม่มี comment ที่ถูกต้อง
   for(int i = 0; i < PositionsTotal(); i++) {
      ulong new_ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(new_ticket)) continue;
      
      string pos_symbol = PositionGetString(POSITION_SYMBOL);
      int pos_type = (int)PositionGetInteger(POSITION_TYPE);
      double pos_volume = PositionGetDouble(POSITION_VOLUME);
      string pos_comment = PositionGetString(POSITION_COMMENT);
      
      // เช็คว่าเป็น position ที่เหลือจาก partial close หรือไม่
      if(pos_symbol == symbol && 
         pos_type == original_type && 
         MathAbs(pos_volume - expected_volume) < 0.001 &&
         pos_comment != original_comment) {
         
         LogMessage(LOG_INFO, 
            "[SLAVE] 🎯 Found remaining position: ticket=" + IntegerToString((int)new_ticket) + 
            " old_comment=" + pos_comment + " → new_comment=" + original_comment
         );
         
         // แก้ไข comment กลับไปเป็นเดิม
         ModifyPositionComment(new_ticket, original_comment);
         return;
      }
   }
   
   LogMessage(LOG_WARNING, "[SLAVE] Could not find remaining position after partial close");
}

// ฟังก์ชันแก้ไข comment ของ position
void ModifyPositionComment(ulong ticket, string new_comment) {
   if(!PositionSelectByTicket(ticket)) {
      LogMessage(LOG_ERROR, "[SLAVE] Cannot select position for comment modification: " + IntegerToString((int)ticket));
      return;
   }
   
   string symbol = PositionGetString(POSITION_SYMBOL);
   double sl = PositionGetDouble(POSITION_SL);
   double tp = PositionGetDouble(POSITION_TP);
   
   MqlTradeRequest req;
   MqlTradeResult res;
   ZeroMemory(req);
   ZeroMemory(res);
   
   req.action = TRADE_ACTION_SLTP;
   req.position = ticket;
   req.symbol = symbol;
   req.sl = sl;
   req.tp = tp;
   req.comment = new_comment;
   req.magic = (MagicNumberInput > 0 ? MagicNumberInput : ComputeAutoMagic());
   
   ResetLastError();
   bool ok = OrderSend(req, res);
   
   if(ok) {
      LogMessage(LOG_INFO, "[SLAVE] ✅ Comment updated: ticket=" + IntegerToString((int)ticket) + " → " + new_comment);
   } else {
      LogMessage(LOG_ERROR, "[SLAVE] Failed to update comment: ticket=" + IntegerToString((int)ticket) + 
                 " ret=" + IntegerToString((int)res.retcode) + " err=" + IntegerToString(GetLastError()));
   }
}

bool ClosePositionByTicketAndVolume(ulong ticket, double target_volume, string source = "SLAVE") {
   if(!PositionSelectByTicket(ticket)) {
      LogMessage(LOG_WARNING, "[SLAVE] Position not found: " + IntegerToString((int)ticket));
      return false;
   }
   
   string sym = PositionGetString(POSITION_SYMBOL);
   int typ = (int)PositionGetInteger(POSITION_TYPE);
   double current_volume = PositionGetDouble(POSITION_VOLUME);
   string original_comment = PositionGetString(POSITION_COMMENT);
   
   
// 🔥 ปัดเศษ target_volume ให้ถูกต้องตาม broker requirements
double rounded_target = RoundVolumeToValidStep(sym, target_volume);
if(rounded_target != target_volume) {
   LogMessage(LOG_WARNING, "[SLAVE] Volume rounded: " + DoubleToString(target_volume, 3) + " → " + DoubleToString(rounded_target, 3));
   target_volume = rounded_target;
}

// ตรวจสอบ volume
   if(target_volume >= current_volume - 0.00001) {
      // Close ทั้งหมด
      LogMessage(LOG_INFO, "[SLAVE] Target volume >= current volume, closing full position");
      return ClosePositionByTicket(ticket, source);
   }
   
   // Partial close
   double price = (typ == POSITION_TYPE_BUY) ? SymbolInfoDouble(sym, SYMBOL_BID) : SymbolInfoDouble(sym, SYMBOL_ASK);
   
   MqlTradeRequest req; 
   MqlTradeResult res;
   ZeroMemory(req); 
   ZeroMemory(res);
   
   req.action   = TRADE_ACTION_DEAL;
   req.position = ticket;
   req.symbol   = sym;
   req.volume   = target_volume;  // 🔥 ใช้ volume ที่ต้องการปิด
   req.price    = price;
   req.deviation= Slippage;
   req.magic    = (MagicNumberInput > 0 ? MagicNumberInput : ComputeAutoMagic());
   req.type     = (typ == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
   req.type_filling = ORDER_FILLING_FOK;
   
   ResetLastError();
   bool ok = OrderSend(req, res);
   if(ok) {
      double remaining = current_volume - target_volume;
      LogMessage(LOG_INFO, 
         "[SLAVE] 🔥 Partial close success: ticket=" + IntegerToString((int)ticket) + 
         " closed=" + DoubleToString(target_volume, 2) + 
         " remain=" + DoubleToString(remaining, 2)
      );
      
      // 🔥 ติดตาม position ใหม่หลัง partial close
      TrackNewPositionAfterPartialClose(sym, typ, remaining, original_comment);
      
   } else {
      LogMessage(LOG_ERROR, 
         "[SLAVE] Partial close failed: ticket=" + IntegerToString((int)ticket) + 
         " ret=" + IntegerToString((int)res.retcode) + 
         " err=" + IntegerToString(GetLastError())
      );
   }
   
   return ok;
}


bool ClosePositionByTicket(ulong ticket, string source = "SLAVE") {
   if(!PositionSelectByTicket(ticket)) {
      LogMessage(LOG_WARNING, "[CLOSE_TICKET] Position not found: " + IntegerToString((int)ticket));
      return false;
   }
   string sym = PositionGetString(POSITION_SYMBOL);
   int typ = (int)PositionGetInteger(POSITION_TYPE);
   double vol = PositionGetDouble(POSITION_VOLUME);
   double price = (typ == POSITION_TYPE_BUY) ? SymbolInfoDouble(sym, SYMBOL_BID) : SymbolInfoDouble(sym, SYMBOL_ASK);

   MqlTradeRequest req; MqlTradeResult res;
   ZeroMemory(req); ZeroMemory(res);

   req.action   = TRADE_ACTION_DEAL;
   req.position = ticket;
   req.symbol   = sym;
   req.volume   = vol;
   req.price    = price;
   req.deviation= Slippage;
   req.magic    = (MagicNumberInput > 0 ? MagicNumberInput : ComputeAutoMagic());
   req.type     = (typ == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
   req.type_filling = ORDER_FILLING_FOK;

   ResetLastError();
   bool ok = OrderSend(req, res);
   if(ok) {
      LogMessage(LOG_INFO, "[CLOSE_TICKET] Closed ticket " + IntegerToString((int)ticket) + " vol=" + DoubleToString(vol,2));
   } else {
      LogMessage(LOG_ERROR, "[CLOSE_TICKET] Failed ticket " + IntegerToString((int)ticket) + " ret=" + IntegerToString((int)res.retcode) + " err=" + IntegerToString(GetLastError()));
   }
   return ok;
}

bool CloseOppositePositionsBySymbol(string sym, string incoming_action, string source = "WEBHOOK") {
   string realSym = ResolveSymbol(sym);
   if(realSym == "") {
      LogMessage(LOG_ERROR, "[CLOSE_OPP] Cannot resolve symbol: " + sym);
      return false;
   }
   string act = ToLower(incoming_action);
   int targetType = -1;
   if(act == "buy")  targetType = POSITION_TYPE_SELL;
   if(act == "sell") targetType = POSITION_TYPE_BUY;
   if(targetType < 0) return false;

   // 🔥 Log ว่ากำลังจะปิดอะไร
   string targetTypeName = (targetType == POSITION_TYPE_BUY ? "BUY" : "SELL");
   string actUpper = act;
   StringToUpper(actUpper);
   LogMessage(LOG_INFO, "[CLOSE_OPP] Received " + actUpper + " signal → will close all " + targetTypeName + " positions for " + realSym);

   ulong toClose[];
   for(int i = 0; i < PositionsTotal(); ++i) {
      ulong t = PositionGetTicket(i);
      if(!PositionSelectByTicket(t)) continue;
      if(PositionGetString(POSITION_SYMBOL) != realSym) continue;
      int typ = (int)PositionGetInteger(POSITION_TYPE);
      if(typ == targetType) {
         int n = ArraySize(toClose);
         ArrayResize(toClose, n+1);
         toClose[n] = t;
      }
   }

   // 🔥 Log จำนวน positions ที่จะปิด
   int count = ArraySize(toClose);
   if(count == 0) {
      LogMessage(LOG_INFO, "[CLOSE_OPP] No opposite positions to close for " + realSym);
      return true;  // Success - no opposite positions
   }

   LogMessage(LOG_INFO, "[CLOSE_OPP] Closing " + IntegerToString(count) + " opposite position(s) for " + realSym);

   bool any = false;
   int closed = 0;
   for(int i = 0; i < count; ++i) {
      if(ClosePositionByTicket(toClose[i], source)) {
         closed++;
         any = true;
      }
   }

   // 🔥 Log ผลลัพธ์
   LogMessage(LOG_INFO, "[CLOSE_OPP] ✅ Successfully closed " + IntegerToString(closed) + "/" + IntegerToString(count) + " position(s) for " + realSym);

   return any;
}

int CollectSymbolTickets(string sym, ulong &tickets[]) {
   ArrayResize(tickets, 0);
   string realSym = ResolveSymbol(sym);
   if(realSym == "") return 0;
   
   for(int i = 0; i < PositionsTotal(); ++i) {
      ulong t = PositionGetTicket(i);
      if(!PositionSelectByTicket(t)) continue;
      if(PositionGetString(POSITION_SYMBOL) != realSym) continue;
      int n = ArraySize(tickets);
      ArrayResize(tickets, n+1);
      tickets[n] = t;
   }
   
   int n = ArraySize(tickets);
   for(int i = 0; i < n; ++i) {
      for(int j = i+1; j < n; ++j) {
         datetime ti = 0, tj = 0;
         if(PositionSelectByTicket(tickets[i])) ti = (datetime)PositionGetInteger(POSITION_TIME);
         if(PositionSelectByTicket(tickets[j])) tj = (datetime)PositionGetInteger(POSITION_TIME);
         if(tj < ti) {
            ulong tmp = tickets[i];
            tickets[i] = tickets[j];
            tickets[j] = tmp;
         }
      }
   }
   return n;
}

bool ClosePositionByIndex(string sym, int index1based, string source = "SLAVE") {
   ulong tickets[];
   int n = CollectSymbolTickets(sym, tickets);
   if(n <= 0) return false;
   int idx = index1based - 1;
   if(idx < 0 || idx >= n) {
      LogMessage(LOG_WARNING, "[CLOSE_INDEX] Index out of range: " + IntegerToString(index1based) + " of " + IntegerToString(n));
      return false;
   }
   return ClosePositionByTicket(tickets[idx], source);
}

bool ModifyPositionByTicket(ulong ticket, double sl, double tp) {
   if(!PositionSelectByTicket(ticket)) {
      LogMessage(LOG_WARNING, "[MODIFY_TICKET] Position not found: " + IntegerToString((int)ticket));
      return false;
   }
   string sym = PositionGetString(POSITION_SYMBOL);
   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   double sln = (sl > 0 ? NormalizeDouble(sl, digits) : 0.0);
   double tpn = (tp > 0 ? NormalizeDouble(tp, digits) : 0.0);

   MqlTradeRequest req; MqlTradeResult res;
   ZeroMemory(req); ZeroMemory(res);

   req.action   = TRADE_ACTION_SLTP;
   req.position = ticket;
   req.symbol   = sym;
   req.sl       = sln;
   req.tp       = tpn;
   req.magic    = (MagicNumberInput > 0 ? MagicNumberInput : ComputeAutoMagic());

   ResetLastError();
   bool ok = OrderSend(req, res);
   if(ok) {
      LogMessage(LOG_INFO, "[MODIFY_TICKET] Modified ticket " + IntegerToString((int)ticket) + " SL=" + DoubleToString(sln, digits) + " TP=" + DoubleToString(tpn, digits));
   } else {
      LogMessage(LOG_ERROR, "[MODIFY_TICKET] Failed modify ticket " + IntegerToString((int)ticket) + " ret=" + IntegerToString((int)res.retcode) + " err=" + IntegerToString(GetLastError()));
   }
   return ok;
}

bool ModifyPositionsBySymbol(string sym, double sl, double tp) {
   string realSym = ResolveSymbol(sym);
   if(realSym == "") {
      LogMessage(LOG_ERROR, "[MODIFY_ALL] Cannot resolve symbol: " + sym);
      return false;
   }
   bool any = false;
   for(int i = 0; i < PositionsTotal(); ++i) {
      ulong t = PositionGetTicket(i);
      if(!PositionSelectByTicket(t)) continue;
      if(PositionGetString(POSITION_SYMBOL) != realSym) continue;
      any |= ModifyPositionByTicket(t, sl, tp);
   }
   return any;
}

//+------------------------------------------------------------------+
//| Modify Position by Comment or Symbol                             |
//+------------------------------------------------------------------+
bool ModifyPositionBySL_TP(string sym, string target_comment, double tp, double sl) {
   g_processing_counter++;
   int process_id = g_processing_counter;

   LogMessage(LOG_INFO, "[" + IntegerToString(process_id) + "] MODIFY: symbol=" + sym +
              ", comment=" + target_comment + ", TP=" + DoubleToString(tp, 5) +
              ", SL=" + DoubleToString(sl, 5));

   // If comment provided, find by comment first
   if(target_comment != "") {
      for(int i = 0; i < PositionsTotal(); i++) {
         ulong ticket = PositionGetTicket(i);
         if(ticket == 0) continue;

         if(!PositionSelectByTicket(ticket)) continue;

         string pos_comment = PositionGetString(POSITION_COMMENT);
         string pos_symbol = PositionGetString(POSITION_SYMBOL);
         long pos_magic = PositionGetInteger(POSITION_MAGIC);
         long my_magic = (MagicNumberInput > 0 ? MagicNumberInput : ComputeAutoMagic());

         // Match by comment and magic
         if(pos_magic == my_magic && StringFind(pos_comment, target_comment) >= 0) {
            LogMessage(LOG_INFO, "[" + IntegerToString(process_id) + "] Found position #" +
                      IntegerToString(ticket) + " with comment: " + pos_comment);
            return ModifyPositionByTicket(ticket, sl, tp);
         }
      }

      LogMessage(LOG_WARNING, "[" + IntegerToString(process_id) + "] Position not found with comment: " + target_comment);
      return false;
   }

   // Otherwise modify by symbol
   LogMessage(LOG_INFO, "[" + IntegerToString(process_id) + "] Modifying all positions for symbol: " + sym);
   return ModifyPositionsBySymbol(sym, sl, tp);
}

bool ModifyPositionByIndex(string sym, int index1based, double sl, double tp) {
   ulong tickets[];
   int n = CollectSymbolTickets(sym, tickets);
   if(n <= 0) return false;
   int idx = index1based - 1;
   if(idx < 0 || idx >= n) {
      LogMessage(LOG_WARNING, "[MODIFY_INDEX] Index out of range: " + IntegerToString(index1based) + " of " + IntegerToString(n));
      return false;
   }
   return ModifyPositionByTicket(tickets[idx], sl, tp);
}

bool ClosePositionByExactComment(string targetComment, string source = "SLAVE") {
   if(targetComment == "") return false;
   for(int i = PositionsTotal() - 1; i >= 0; --i) {
      ulong t = PositionGetTicket(i);
      if(!PositionSelectByTicket(t)) continue;
      string c = PositionGetString(POSITION_COMMENT);
      if(c == targetComment) {
         return ClosePositionByTicket(t, source);
      }
   }
   LogMessage(LOG_WARNING, "[CLOSE_COMMENT] Not found comment: " + targetComment);
   return false;
}

bool ModifyPositionByExactComment(string targetComment, double sl, double tp) {
   if(targetComment == "") return false;
   for(int i = 0; i < PositionsTotal(); ++i) {
     ulong t = PositionGetTicket(i);
     if(!PositionSelectByTicket(t)) continue;
     string c = PositionGetString(POSITION_COMMENT);
     if(c == targetComment) {
        return ModifyPositionByTicket(t, sl, tp);
     }
   }
   LogMessage(LOG_WARNING, "[MODIFY_COMMENT] Not found comment: " + targetComment);
   return false;
}

//==================== Webhook Mode ====================


//==================== Slave Mode ====================


//==================== Master Mode ====================
void InitMasterPositions() {
   int total = PositionsTotal();
   
   ArrayResize(MasterTickets, total);
   ArrayResize(MasterSymbols, total);
   ArrayResize(MasterTypes, total);
   ArrayResize(MasterVolumes, total);
   ArrayResize(MasterTPs, total);
   ArrayResize(MasterSLs, total);
   
   for(int i = 0; i < total; i++) {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0) {
         MasterTickets[i] = ticket;
         MasterSymbols[i] = PositionGetString(POSITION_SYMBOL);
         MasterTypes[i] = (int)PositionGetInteger(POSITION_TYPE);
         MasterVolumes[i] = PositionGetDouble(POSITION_VOLUME);
         MasterTPs[i] = PositionGetDouble(POSITION_TP);
         MasterSLs[i] = PositionGetDouble(POSITION_SL);
      }
   }
   
   LogMessage(LOG_INFO, "[MASTER] Initialized " + IntegerToString(total) + " existing positions");
}

void SendSignal(string event, string symbol, int type, double volume, double tp, double sl, ulong master_ticket,
                string order_type = "market", double price = 0.0) {
   string url = API_ServerURL + "/api/copy/trade";

   string typeStr = (type == POSITION_TYPE_BUY) ? "BUY" : "SELL";
   string order_id = "order_" + IntegerToString((int)master_ticket);

   // 🔥 สำคัญ: ส่ง volume ที่ปิดจริง ไม่ใช่ volume ทั้งหมดของ position
   // 🔥 เพิ่ม order_type และ price สำหรับ Pending Orders
   string payload = StringFormat(
      "{"
      "\"api_key\":\"%s\","
      "\"event\":\"%s\","
      "\"order_id\":\"%s\","
      "\"account\":\"%s\","
      "\"symbol\":\"%s\","
      "\"type\":\"%s\","
      "\"volume\":%.2f,"
      "\"tp\":%.5f,"
      "\"sl\":%.5f,"
      "\"order_type\":\"%s\","
      "\"price\":%.5f"
      "}",
      Master_APIKey,
      event,
      order_id,
      IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)),
      symbol,
      typeStr,
      volume,
      tp,
      sl,
      order_type,
      price
   );

   LogMessage(LOG_DEBUG, "[MASTER] 📡 Sending: " + event + " " + symbol + " vol=" + DoubleToString(volume, 2));

   // 🚀 ส่งข้อมูลแบบ fast (ใช้ timeout สั้น, ไม่ตรวจสอบ response detail)
   string response = SendHttpRequest(url, payload, API_Timeout);

   // ตรวจสอบแค่ว่ามี response กลับมาหรือไม่
   if(response == "") {
      LogMessage(LOG_WARNING, "[MASTER] ⚠️ No response from server (timeout or network error)");
   }
   else {
      LogMessage(LOG_DEBUG, "[MASTER] ✅ Signal sent successfully");
   }
}



void CheckMasterPositions() {
   int currentTotal = PositionsTotal();
   
   // ตรวจสอบการเปลี่ยนแปลง volume ของ position ที่มีอยู่ (Partial Close)
   if(Master_SendOnClose) {
      for(int i = 0; i < ArraySize(MasterTickets); i++) {
         ulong oldTicket = MasterTickets[i];
         double oldVolume = MasterVolumes[i];
         string oldSymbol = MasterSymbols[i];
         int oldType = MasterTypes[i];
         
         // หา position เดิมใน current positions
         bool found = false;
         for(int j = 0; j < currentTotal; j++) {
            if(PositionGetTicket(j) == oldTicket) {
               found = true;
               double currentVolume = PositionGetDouble(POSITION_VOLUME);
               
               // 🔥 ตรวจจับ Partial Close: volume ลดลง
               if(currentVolume < oldVolume - 0.00001) { // ใช้ epsilon เพื่อป้องกัน floating point error
                  double closedVolume = oldVolume - currentVolume;
                  
                  LogMessage(LOG_INFO, 
                     "[MASTER] 🔥 PARTIAL CLOSE detected: " + 
                     oldSymbol + " ticket=" + IntegerToString((int)oldTicket) + 
                     " closed=" + DoubleToString(closedVolume, 2) + 
                     " remain=" + DoubleToString(currentVolume, 2)
                  );
                  
                  // ส่งสัญญาณ partial close พร้อม volume ที่ปิดจริง
                  SendSignal("deal_close", oldSymbol, oldType, closedVolume, 0, 0, oldTicket);
                  
                  // อัปเดต volume ใหม่
                  MasterVolumes[i] = currentVolume;
                  MasterTickets[i] = PositionGetTicket(j);
               }
               break;
            }
         }
         
         // 🔥 ตรวจจับ Full Close: position หายไปทั้งหมด
         if(!found) {
            LogMessage(LOG_INFO, 
               "[MASTER] 🔥 FULL CLOSE detected: " + 
               oldSymbol + " ticket=" + IntegerToString((int)oldTicket) + 
               " closed=" + DoubleToString(oldVolume, 2)
            );
            
            // ส่งสัญญาณ full close
            SendSignal("deal_close", oldSymbol, oldType, oldVolume, 0, 0, oldTicket);
         }
      }
   }
   
   // 🔥 ตรวจสอบ positions ใหม่ที่เปิด (ปรับปรุงให้รองรับ batch processing)
   // ตรวจสอบทุก position แทนการเปรียบเทียบจำนวน (เพื่อไม่พลาด positions ที่เปิดพร้อมกัน)
   if(Master_SendOnOpen) {
      int newPositionsFound = 0;

      for(int i = 0; i < currentTotal; i++) {
         ulong ticket = PositionGetTicket(i);
         bool isNew = true;

         // เช็คว่า ticket นี้อยู่ใน MasterTickets array หรือยัง
         for(int j = 0; j < ArraySize(MasterTickets); j++) {
            if(MasterTickets[j] == ticket) {
               isNew = false;
               break;
            }
         }

         // ถ้าเป็น position ใหม่ → ส่ง signal
         if(isNew) {
            string symbol = PositionGetString(POSITION_SYMBOL);
            int type = (int)PositionGetInteger(POSITION_TYPE);
            double volume = PositionGetDouble(POSITION_VOLUME);
            double tp = PositionGetDouble(POSITION_TP);
            double sl = PositionGetDouble(POSITION_SL);

            LogMessage(LOG_INFO, "[MASTER] 🆕 NEW POSITION #" + IntegerToString(newPositionsFound + 1) + ": " + symbol + " ticket=" + IntegerToString((int)ticket));
            SendSignal("deal_add", symbol, type, volume, tp, sl, ticket);
            newPositionsFound++;
         }
      }

      if(newPositionsFound > 0) {
         LogMessage(LOG_INFO, "[MASTER] ✅ Sent " + IntegerToString(newPositionsFound) + " new position signal(s)");
      }
   }
   
   // ตรวจสอบการ modify TP/SL (เหมือนเดิม)
   if(Master_SendOnModify) {
      for(int i = 0; i < ArraySize(MasterTickets); i++) {
         ulong ticket = MasterTickets[i];
         
         for(int j = 0; j < currentTotal; j++) {
            if(PositionGetTicket(j) == ticket) {
               double currentTP = PositionGetDouble(POSITION_TP);
               double currentSL = PositionGetDouble(POSITION_SL);
               
               if(MathAbs(currentTP - MasterTPs[i]) > 0.00001 || 
                  MathAbs(currentSL - MasterSLs[i]) > 0.00001) {
                  
                  string symbol = PositionGetString(POSITION_SYMBOL);
                  int type = (int)PositionGetInteger(POSITION_TYPE);
                  double volume = PositionGetDouble(POSITION_VOLUME);
                  
                  LogMessage(LOG_INFO, "[MASTER] 🔄 MODIFY: " + symbol);
                  SendSignal("position_modify", symbol, type, volume, currentTP, currentSL, ticket);
                  
                  MasterTPs[i] = currentTP;
                  MasterSLs[i] = currentSL;
               }
               break;
            }
         }
      }
   }
   
   // 📝 อัปเดต Arrays สำหรับรอบถัดไป
   UpdateMasterArrays();
}

// ⭐ ฟังก์ชันสำหรับอัปเดต Master Arrays
void UpdateMasterArrays() {
   int currentTotal = PositionsTotal();

   ArrayResize(MasterTickets, currentTotal);
   ArrayResize(MasterSymbols, currentTotal);
   ArrayResize(MasterTypes, currentTotal);
   ArrayResize(MasterVolumes, currentTotal);
   ArrayResize(MasterTPs, currentTotal);
   ArrayResize(MasterSLs, currentTotal);

   for(int i = 0; i < currentTotal; i++) {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0) {
         MasterTickets[i] = ticket;
         MasterSymbols[i] = PositionGetString(POSITION_SYMBOL);
         MasterTypes[i] = (int)PositionGetInteger(POSITION_TYPE);
         MasterVolumes[i] = PositionGetDouble(POSITION_VOLUME);  // 🔥 อัปเดต volume ปัจจุบัน
         MasterTPs[i] = PositionGetDouble(POSITION_TP);
         MasterSLs[i] = PositionGetDouble(POSITION_SL);
      }
   }
}

//+------------------------------------------------------------------+
//| Check Master Pending Orders and Send Signals                     |
//+------------------------------------------------------------------+
void CheckMasterPendingOrders() {
   if(!Master_SendOnOpen) return;

   int total_orders = OrdersTotal();

   for(int i = 0; i < total_orders; i++) {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0) continue;

      // เช็คว่าเป็น pending order ใหม่ที่ยังไม่ได้ส่ง
      bool already_sent = false;
      for(int j = 0; j < ArraySize(MasterPendingTickets); j++) {
         if(MasterPendingTickets[j] == ticket) {
            already_sent = true;
            break;
         }
      }

      if(!already_sent) {
         string symbol = OrderGetString(ORDER_SYMBOL);
         ENUM_ORDER_TYPE order_type_enum = (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
         double volume = OrderGetDouble(ORDER_VOLUME_CURRENT);
         double price = OrderGetDouble(ORDER_PRICE_OPEN);
         double tp = OrderGetDouble(ORDER_TP);
         double sl = OrderGetDouble(ORDER_SL);

         // แปลง order type เป็น string
         string order_type_str = "market";
         int type = POSITION_TYPE_BUY;  // default

         if(order_type_enum == ORDER_TYPE_BUY_LIMIT) {
            order_type_str = "limit";
            type = POSITION_TYPE_BUY;
         }
         else if(order_type_enum == ORDER_TYPE_SELL_LIMIT) {
            order_type_str = "limit";
            type = POSITION_TYPE_SELL;
         }
         else if(order_type_enum == ORDER_TYPE_BUY_STOP) {
            order_type_str = "stop";
            type = POSITION_TYPE_BUY;
         }
         else if(order_type_enum == ORDER_TYPE_SELL_STOP) {
            order_type_str = "stop";
            type = POSITION_TYPE_SELL;
         }
         else {
            // Skip market orders (ORDER_TYPE_BUY, ORDER_TYPE_SELL)
            continue;
         }

         LogMessage(LOG_INFO, "[MASTER] 🆕 NEW PENDING ORDER: " + symbol + " " + order_type_str + " @ " + DoubleToString(price, 5));
         SendSignal("order_add", symbol, type, volume, tp, sl, ticket, order_type_str, price);

         // บันทึกว่าส่งแล้ว
         int size = ArraySize(MasterPendingTickets);
         ArrayResize(MasterPendingTickets, size + 1);
         MasterPendingTickets[size] = ticket;
      }
   }

   // ลบ pending tickets ที่ไม่มีอยู่แล้ว (ถูก executed หรือ cancelled)
   int new_size = 0;
   for(int i = 0; i < ArraySize(MasterPendingTickets); i++) {
      bool exists = false;
      for(int j = 0; j < total_orders; j++) {
         if(OrderGetTicket(j) == MasterPendingTickets[i]) {
            exists = true;
            break;
         }
      }
      if(exists) {
         MasterPendingTickets[new_size] = MasterPendingTickets[i];
         new_size++;
      }
   }
   ArrayResize(MasterPendingTickets, new_size);
}



//==================== File Bridge Setup ====================

//==================== Logging ====================
void LogMessage(ENUM_LOG_LEVEL level, string message) {
   if(!EnableLogging) return;
   if(level < LogLevel) return;
   
   string prefix = "";
   switch(level) {
      case LOG_DEBUG:   prefix = "[DEBUG] "; break;
      case LOG_INFO:    prefix = "[INFO] "; break;
      case LOG_WARNING: prefix = "[WARN] "; break;
      case LOG_ERROR:   prefix = "[ERROR] "; break;
   }
   
   string fullMessage = prefix + TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS) + " " + message;
   Print(fullMessage);
   
   string filename = "AllInOneEA_" + AccountNumber + ".log";
   int handle = FileOpen(filename, FILE_WRITE | FILE_READ | FILE_TXT | FILE_ANSI);
   
   if(handle != INVALID_HANDLE) {
      FileSeek(handle, 0, SEEK_END);
      FileWriteString(handle, fullMessage + "\n");
      FileClose(handle);
   }
}

//==================== EA Lifecycle ====================

//==================== ⭐ NEW: Broker Data Scanner ====================

// ⭐ Helper: Send JSON via WebRequest and return response (POST)
string SendHttpRequest(string url, string json, int timeout_ms) {
   char postData[];
   char resultData[];
   string headers = "Content-Type: application/json\r\n";
   StringToCharArray(json, postData, 0, StringLen(json));
   int status = WebRequest("POST", url, headers, timeout_ms, postData, resultData, headers);
   if(status == -1) {
      int err = GetLastError();
      LogMessage(LOG_ERROR, "[HTTP] WebRequest failed: Error " + IntegerToString(err) + " - Add '" + url + "' to allowed URLs");
      return "";
   }
   string resp = CharArrayToString(resultData);
   LogMessage(LOG_DEBUG, "[HTTP] Response: " + resp);
   return resp;
}

// ⭐ Helper: Send GET request and return response
string SendHttpGetRequest(string url, int timeout_ms) {
   char postData[];  // Empty for GET
   char resultData[];
   string headers = "";
   int status = WebRequest("GET", url, headers, timeout_ms, postData, resultData, headers);
   if(status == -1) {
      int err = GetLastError();
      LogMessage(LOG_ERROR, "[HTTP] GET request failed: Error " + IntegerToString(err) + " - Add '" + url + "' to allowed URLs");
      return "";
   }
   string resp = CharArrayToString(resultData);
   LogMessage(LOG_DEBUG, "[HTTP] GET Response: " + resp);
   return resp;
}

// เพิ่ม Global Variables
// bool g_broker_data_sent = false;  // (declared above)

// ⭐ ฟังก์ชันสแกนและส่งข้อมูลโบรกเกอร์ (ครั้งเดียวตอน Init)
\
 //==================== ⭐ NEW: Broker Data Scanner (Once Only) ====================

 // Global Variables

 // ส่งข้อมูลโบรกเกอร์ (ส่งทุกครั้งที่ EA Init)
 void ScanAndSendBrokerData() {
    // ✅ Hard-coded: ส่งทุกครั้งที่เรียกฟังก์ชัน - ไม่มีการเช็ค flag
    LogMessage(LOG_INFO, "[BROKER_SCAN] ═══════════════════════════════════════");
    LogMessage(LOG_INFO, "[BROKER_SCAN] Sending ALL broker symbols (Auto)...");
    LogMessage(LOG_INFO, "[BROKER_SCAN] ═══════════════════════════════════════");

    // สร้าง JSON
    string json = "{";
    json += "\"account\":\"" + AccountNumber + "\",";
    json += "\"broker\":\"" + AccountInfoString(ACCOUNT_COMPANY) + "\",";
    json += "\"server\":\"" + AccountInfoString(ACCOUNT_SERVER) + "\",";
    json += "\"currency\":\"" + AccountInfoString(ACCOUNT_CURRENCY) + "\",";
    json += "\"leverage\":" + IntegerToString(AccountInfoInteger(ACCOUNT_LEVERAGE)) + ",";
    json += "\"timestamp\":\"" + TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS) + "\",";
    json += "\"symbols\":[";

    // ✅ วนสแกนทุก Symbol ที่โบรกเกอร์มี (ไม่ใช่แค่ Market Watch)
    int count = 0;
    int total = SymbolsTotal(false);  // ✅ false = ทุก symbol ของโบรกเกอร์

    LogMessage(LOG_INFO, "[BROKER_SCAN] Scanning " + IntegerToString(total) + " symbols from broker (ALL)...");

    for(int i = 0; i < total; i++) {
       string sym = SymbolName(i, false);  // ✅ false = ทุก symbol ของโบรกเกอร์

       if(!SymbolSelect(sym, true)) {
          LogMessage(LOG_DEBUG, "[BROKER_SCAN] Cannot select symbol: " + sym);
          continue;
       }

       // ดึงข้อมูล Symbol
       double contract_size = SymbolInfoDouble(sym, SYMBOL_TRADE_CONTRACT_SIZE);
       double volume_min = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
       double volume_max = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
       double volume_step = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
       int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);

       // เพิ่มเครื่องหมายคั่น
       if(count > 0) json += ",";

       // สร้าง JSON Object
       json += "{";
       json += "\"name\":\"" + sym + "\",";
       json += "\"contract_size\":" + DoubleToString(contract_size, 0) + ",";
       json += "\"volume_min\":" + DoubleToString(volume_min, 2) + ",";
       json += "\"volume_max\":" + DoubleToString(volume_max, 2) + ",";
       json += "\"volume_step\":" + DoubleToString(volume_step, 2) + ",";
       json += "\"digits\":" + IntegerToString(digits);
       json += "}";

       count++;

       // Log progress ทุก 50 symbols
       if(count % 50 == 0) {
          LogMessage(LOG_INFO, "[BROKER_SCAN] Progress: " + IntegerToString(count) + "/" + IntegerToString(total));
       }
    }

    json += "]}";

    LogMessage(LOG_INFO, "[BROKER_SCAN] Collected " + IntegerToString(count) + " symbols");

    // ⭐ ใช้ API_ServerURL (centralized)
    string url = API_ServerURL;

    // เติม /api/broker/register ถ้ายังไม่มี
    if(StringFind(url, "/api/broker/register") < 0) {
       // ลบ trailing slash
       if(StringSubstr(url, StringLen(url)-1) == "/") {
          url = StringSubstr(url, 0, StringLen(url)-1);
       }
       url += "/api/broker/register";
    }

    if(url == "" || url == "/api/broker/register") {
       LogMessage(LOG_ERROR, "[BROKER_SCAN] ❌ API_ServerURL is empty!");
       Alert("⚠️ Please set API_ServerURL in EA settings");
       return;
    }

    // ส่งข้อมูลไป Server
    LogMessage(LOG_INFO, "[BROKER_SCAN] Sending data to: " + url);
    LogMessage(LOG_INFO, "[BROKER_SCAN] Timeout: " + IntegerToString(API_Timeout) + " ms");

    string result = SendHttpRequest(url, json, API_Timeout);

    // ตรวจสอบผลลัพธ์
    if(StringFind(result, "\"success\":true") >= 0 || StringFind(result, "\"success\": true") >= 0) {
       // ✅ ไม่เซ็ต flag เพราะต้องส่งทุกรอบ

       LogMessage(LOG_INFO, "[BROKER_SCAN] ═══════════════════════════════════════");
       LogMessage(LOG_INFO, "[BROKER_SCAN] ✅ SUCCESS!");
       LogMessage(LOG_INFO, "[BROKER_SCAN] Account: " + AccountNumber);
       LogMessage(LOG_INFO, "[BROKER_SCAN] Broker: " + AccountInfoString(ACCOUNT_COMPANY));
       LogMessage(LOG_INFO, "[BROKER_SCAN] Symbols: " + IntegerToString(count));
       LogMessage(LOG_INFO, "[BROKER_SCAN] Server: " + url);
       LogMessage(LOG_INFO, "[BROKER_SCAN] Sent automatically on EA Init");
       LogMessage(LOG_INFO, "[BROKER_SCAN] ═══════════════════════════════════════");

       // แสดง Alert ให้ผู้ใช้เห็น
       Alert("✅ Broker data sent successfully!\n" + 
             "Account: " + AccountNumber + "\n" +
             "Symbols: " + IntegerToString(count));

    } else {
       LogMessage(LOG_ERROR, "[BROKER_SCAN] ═══════════════════════════════════════");
       LogMessage(LOG_ERROR, "[BROKER_SCAN] ❌ FAILED to send data");
       LogMessage(LOG_ERROR, "[BROKER_SCAN] Server: " + url);
       LogMessage(LOG_ERROR, "[BROKER_SCAN] Response: " + result);
       LogMessage(LOG_ERROR, "[BROKER_SCAN] ═══════════════════════════════════════");

       Alert("⚠️ Failed to send broker data!\n" +
             "Check EA logs for details\n" +
             "Server: " + url);
    }
 }

//+------------------------------------------------------------------+
//| Check if Balance Update is Needed (เช็คกับ server)                |
//+------------------------------------------------------------------+
bool CheckBalanceUpdateNeeded() {
   // ถ้ายังไม่ถึงเวลา re-check ให้ใช้ค่าเดิม
   datetime now = TimeCurrent();
   if(now - g_last_balance_check < g_balance_check_interval) {
      return g_balance_update_needed;  // ใช้ cache
   }

   // เวลาเช็คครั้งใหม่แล้ว
   g_last_balance_check = now;

   // สร้าง URL
   string url = API_ServerURL;
   if(StringSubstr(url, StringLen(url)-1) == "/") {
      url = StringSubstr(url, 0, StringLen(url)-1);
   }
   url += "/api/balance/need-update/" + AccountNumber;

   // เรียก API (GET request)
   string result = SendHttpGetRequest(url, API_Timeout);

   // Parse response
   if(StringFind(result, "\"need_update\":true") >= 0 || StringFind(result, "\"need_update\": true") >= 0) {
      g_balance_update_needed = true;
      LogMessage(LOG_INFO, "[BALANCE_CHECK] ✅ Balance updates ENABLED (Copy trading uses volume % mode)");
      return true;
   } else if(StringFind(result, "\"need_update\":false") >= 0 || StringFind(result, "\"need_update\": false") >= 0) {
      g_balance_update_needed = false;
      LogMessage(LOG_INFO, "[BALANCE_CHECK] ⏸️ Balance updates DISABLED (Not needed for this account)");
      return false;
   } else {
      // Error หรือไม่สามารถ parse ได้ -> ส่งไปก่อน (safe default)
      g_balance_update_needed = true;
      LogMessage(LOG_WARNING, "[BALANCE_CHECK] ⚠️ Cannot check - defaulting to ENABLED");
      return true;
   }
}

//+------------------------------------------------------------------+
//| Send Account Balance to Server (ส่งเฉพาะเมื่อจำเป็น)             |
//+------------------------------------------------------------------+
void SendAccountBalance(bool force_send = false) {
   if(API_ServerURL == "") {
      return;  // ไม่มี URL
   }

   // 🔥 เช็คว่าต้องส่ง balance หรือไม่
   if(!force_send && !CheckBalanceUpdateNeeded()) {
      return;  // ไม่จำเป็นต้องส่ง
   }

   // ดึงข้อมูล account
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double margin = AccountInfoDouble(ACCOUNT_MARGIN);
   double free_margin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   string currency = AccountInfoString(ACCOUNT_CURRENCY);

   datetime now = TimeCurrent();
   bool should_send = force_send;

   // ตรวจสอบว่าควรส่งหรือไม่
   if(!should_send) {
      // 1. Heartbeat: ส่งอย่างน้อยทุก 5 นาที
      if(now - g_last_balance_send >= g_balance_send_interval) {
         should_send = true;
         LogMessage(LOG_DEBUG, "[BALANCE] Sending heartbeat");
      }
      // 2. Balance เปลี่ยนแปลงมากกว่า threshold
      else if(g_last_balance > 0) {
         double balance_change_pct = MathAbs((balance - g_last_balance) / g_last_balance * 100.0);
         double equity_change_pct = MathAbs((equity - g_last_equity) / g_last_equity * 100.0);

         if(balance_change_pct > g_balance_change_threshold || equity_change_pct > g_balance_change_threshold) {
            should_send = true;
            LogMessage(LOG_DEBUG,
               "[BALANCE] Significant change detected - Balance: " +
               DoubleToString(balance_change_pct, 2) + "%, Equity: " +
               DoubleToString(equity_change_pct, 2) + "%"
            );
         }
      }
      // 3. ครั้งแรกที่ส่ง
      else if(g_last_balance == 0) {
         should_send = true;
      }
   }

   if(!should_send) {
      return;  // ไม่จำเป็นต้องส่ง
   }

   // สร้าง JSON
   string json = "{";
   json += "\"account\":\"" + AccountNumber + "\",";
   json += "\"balance\":" + DoubleToString(balance, 2) + ",";
   json += "\"equity\":" + DoubleToString(equity, 2) + ",";
   json += "\"margin\":" + DoubleToString(margin, 2) + ",";
   json += "\"free_margin\":" + DoubleToString(free_margin, 2) + ",";
   json += "\"currency\":\"" + currency + "\"";
   json += "}";

   // สร้าง URL
   string url = API_ServerURL;
   if(StringFind(url, "/api/account/balance") < 0) {
      if(StringSubstr(url, StringLen(url)-1) == "/") {
         url = StringSubstr(url, 0, StringLen(url)-1);
      }
      url += "/api/account/balance";
   }

   // ส่งข้อมูล
   string result = SendHttpRequest(url, json, API_Timeout);

   // ตรวจสอบผลลัพธ์
   if(StringFind(result, "\"success\":true") >= 0 || StringFind(result, "\"success\": true") >= 0) {
      g_last_balance_send = now;
      g_last_balance = balance;
      g_last_equity = equity;
      LogMessage(LOG_DEBUG,
         "[BALANCE] Sent: Balance=" + DoubleToString(balance, 2) +
         " Equity=" + DoubleToString(equity, 2) +
         " " + currency
      );
   } else {
      LogMessage(LOG_WARNING, "[BALANCE] Failed to send: " + result);
   }
}



int OnInit() {
   AccountNumber = IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN));
   g_magic = (MagicNumberInput > 0 ? MagicNumberInput : ComputeAutoMagic());
   
   LogMessage(LOG_INFO, "=== All-in-One Trading EA v2.2 Started ===");
   LogMessage(LOG_INFO, "Account: " + AccountNumber);
   LogMessage(LOG_INFO, "Magic: " + IntegerToString(g_magic));
   
   if(!EnableWebhook && !EnableMaster && !EnableSlave) {
      Alert("?? Please enable at least one mode!");
      LogMessage(LOG_ERROR, "No mode enabled");
      return(INIT_PARAMETERS_INCORRECT);
   }
   
   string modes = "";
   if(EnableWebhook) modes += "WEBHOOK ";
   if(EnableMaster) modes += "MASTER ";
   if(EnableSlave) modes += "SLAVE ";
   LogMessage(LOG_INFO, "Enabled Modes: " + modes);
   
   if(EnableWebhook) {
      LogMessage(LOG_INFO, "=== Initializing Webhook Mode ===");
      LogMessage(LOG_INFO, "WebhookAutoCloseBySymbol: " + (WebhookAutoCloseBySymbol ? "TRUE" : "FALSE"));
      LogMessage(LOG_INFO, "WebhookCloseOppositeBeforeOpen: " + (WebhookCloseOppositeBeforeOpen ? "TRUE" : "FALSE"));
      LogMessage(LOG_INFO, "Webhook will poll API at: " + API_ServerURL);
   }
   
   if(EnableMaster) {
      LogMessage(LOG_INFO, "=== Initializing Master Mode ===");

      if(Master_APIKey == "") {
         Alert("?? Master Mode requires API Key!");
         LogMessage(LOG_ERROR, "Master Mode requires API Key");
         return(INIT_PARAMETERS_INCORRECT);
      }

      if(API_ServerURL == "") {
         Alert("?? Server URL is required!");
         LogMessage(LOG_ERROR, "Server URL is required");
         return(INIT_PARAMETERS_INCORRECT);
      }

      LogMessage(LOG_INFO, "Master API Key: " + StringSubstr(Master_APIKey, 0, 8) + "...");
      LogMessage(LOG_INFO, "Master Server: " + API_ServerURL);
      LogMessage(LOG_INFO, "Master mode: Send signals only (does not execute trades)");
      InitMasterPositions();
   }
   
   if(EnableSlave) {
      LogMessage(LOG_INFO, "=== Initializing Slave Mode ===");
      LogMessage(LOG_INFO, "Slave will poll API at: " + API_ServerURL);
      LogMessage(LOG_INFO, "Slave mode: 100% copy Master signals (reversal logic disabled)");
   }
   
   // ⭐ ส่งข้อมูลโบรกเกอร์ (ใหม่)
   ScanAndSendBrokerData();

   Initialized = true;

   // ⭐ ใช้ API polling interval เดียวสำหรับทุก mode
   int timer_seconds = 1;
   if(EnableWebhook || EnableSlave) {
      timer_seconds = API_PollSeconds;
   }

   EventSetTimer(MathMax(1, timer_seconds));

   LogMessage(LOG_INFO, "? Initialization complete");
   LogMessage(LOG_INFO, "Timer interval: " + IntegerToString(timer_seconds) + " seconds");
   if(EnableWebhook || EnableSlave) {
      LogMessage(LOG_INFO, "? API Mode enabled - Commands will be polled from " + API_ServerURL);
   }

   // ✅ ส่ง Heartbeat ครั้งแรก (Hard-coded: เปิดเสมอ)
   LogMessage(LOG_INFO, "=== Heartbeat Enabled (Auto) ===");
   LogMessage(LOG_INFO, "Interval: " + IntegerToString(HEARTBEAT_INTERVAL) + "s");
   SendHeartbeat();

   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) {
   EventKillTimer();
   LogMessage(LOG_INFO, "EA Stopped");
}


//+------------------------------------------------------------------+
//| ⭐ NEW: Export Symbol Info for Tick Value Auto-Detection        |
//+------------------------------------------------------------------+
void ExportSymbolInfo(string symbol) { /* disabled by Broker Data Scanner */ }


//+------------------------------------------------------------------+
//| ⭐ NEW: Poll Commands from API                                   |
//+------------------------------------------------------------------+
void PollCommandsFromAPI() {
   if(!EnableWebhook && !EnableSlave) return;

   string account = IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN));
   string url = API_ServerURL + "/api/commands/" + account + "?limit=10";

   // Prepare HTTP request
   string headers = "";
   char post[];
   char result[];
   string result_headers;
   int timeout = API_Timeout;

   // Send GET request
   int res = WebRequest("GET", url, headers, timeout, post, result, result_headers);

   if(res == 200) {
      string json_response = CharArrayToString(result);
      ProcessAPICommands(json_response);
   }
   else if(res == -1) {
      LogMessage(LOG_ERROR, "[API] WebRequest error: " + IntegerToString(GetLastError()) +
                 " - Check URL whitelist in Tools > Options > Expert Advisors");
   }
   else if(res != 404) {
      LogMessage(LOG_WARNING, "[API] HTTP " + IntegerToString(res));
   }
}

//+------------------------------------------------------------------+
//| Process Commands from API Response                              |
//+------------------------------------------------------------------+
void ProcessAPICommands(string json_response) {
   // Simple JSON parsing - check if success
   if(StringFind(json_response, "\"success\":true") < 0) {
      LogMessage(LOG_DEBUG, "[API] No success in response");
      return;
   }

   // Check if count > 0
   if(StringFind(json_response, "\"count\":0") >= 0) {
      // No new commands
      return;
   }

   // Extract commands array (simplified - assumes well-formatted JSON)
   int commands_start = StringFind(json_response, "\"commands\":[");
   if(commands_start < 0) return;

   int commands_end = StringFind(json_response, "]", commands_start);
   if(commands_end < 0) return;

   string commands_json = StringSubstr(json_response, commands_start + 12, commands_end - commands_start - 12);

   // Split by "},{" to get individual commands
   string command_parts[];
   int count = StringSplit(commands_json, StringGetCharacter("},{", 0), command_parts);

   LogMessage(LOG_INFO, "[API] Received " + IntegerToString(count) + " command(s)");

   // Process each command
   for(int i = 0; i < count; i++) {
      string cmd = command_parts[i];

      // Extract queue_id
      string queue_id = ExtractJSONString(cmd, "queue_id");
      if(queue_id == "") continue;

      // Extract command fields
      string action = ExtractJSONString(cmd, "action");
      string symbol = ExtractJSONString(cmd, "symbol");
      string comment = ExtractJSONString(cmd, "comment");
      double volume = ExtractJSONNumber(cmd, "volume");
      double tp = ExtractJSONNumber(cmd, "take_profit");
      double sl = ExtractJSONNumber(cmd, "stop_loss");

      // 🔥 รองรับ Pending Orders
      string order_type = ExtractJSONString(cmd, "order_type");
      double price = ExtractJSONNumber(cmd, "price");

      // ✅ รองรับ close/modify แบบละเอียด
      ulong ticket = (ulong)ExtractJSONNumber(cmd, "ticket");
      int index = (int)ExtractJSONNumber(cmd, "index");

      LogMessage(LOG_INFO, "[API] Processing: " + action + " " + symbol +
                          (volume > 0 ? " vol=" + DoubleToString(volume, 2) : "") +
                          (order_type != "" ? " type=" + order_type : "") +
                          (price > 0 ? " price=" + DoubleToString(price, 2) : "") +
                          (ticket > 0 ? " ticket=" + IntegerToString((int)ticket) : "") +
                          (index > 0 ? " index=" + IntegerToString(index) : "") +
                          (comment != "" ? " comment=" + comment : ""));

      // Execute trade
      bool success = ExecuteAPICommand(action, symbol, volume, tp, sl, comment, ticket, index, order_type, price);

      // Acknowledge command
      AcknowledgeCommand(queue_id, success);
   }
}

//+------------------------------------------------------------------+
//| Execute API Command (รองรับ close/modify แบบละเอียด)             |
//+------------------------------------------------------------------+
bool ExecuteAPICommand(string action, string symbol, double volume, double tp, double sl,
                       string comment = "", ulong ticket = 0, int index = 0,
                       string order_type = "market", double price = 0.0) {
   // Map symbol using fuzzy matching
   string mapped_symbol = ResolveSymbolFuzzy(symbol);
   if(mapped_symbol == "" && symbol != "") {
      LogMessage(LOG_ERROR, "[API] Cannot map symbol: " + symbol);
      return false;
   }

   // Execute based on action
   StringToUpper(action);  // Built-in function modifies in place

   // ✅ Support CALL = BUY, PUT = SELL
   if(action == "CALL") action = "BUY";
   if(action == "PUT") action = "SELL";

   // 🔥 BUY/SELL Actions - รองรับ Pending Orders
   if(action == "BUY" || action == "LONG") {
      string ot = (order_type != "" ? order_type : "market");
      return SendOrderAdvanced("BUY", ot, mapped_symbol, volume, price, sl, tp, comment, "", "API");
   }
   else if(action == "SELL" || action == "SHORT") {
      string ot = (order_type != "" ? order_type : "market");
      return SendOrderAdvanced("SELL", ot, mapped_symbol, volume, price, sl, tp, comment, "", "API");
   }

   // 🔥 MODIFY Actions - รองรับ by ticket, comment, symbol
   else if(action == "MODIFY") {
      // Priority: ticket > comment > symbol
      if(ticket > 0) {
         LogMessage(LOG_INFO, "[API_MODIFY] By ticket=" + IntegerToString((int)ticket));
         return ModifyPositionByTicket(ticket, tp, sl);
      }
      else if(comment != "") {
         LogMessage(LOG_INFO, "[API_MODIFY] By comment=" + comment);
         return ModifyPositionBySL_TP(mapped_symbol, comment, tp, sl);
      }
      else if(mapped_symbol != "") {
         LogMessage(LOG_INFO, "[API_MODIFY] By symbol=" + mapped_symbol);
         return ModifyPositionBySL_TP(mapped_symbol, "", tp, sl);
      }
      LogMessage(LOG_WARNING, "[API_MODIFY] No ticket, comment, or symbol specified");
      return false;
   }

   // 🔥 CLOSE Actions - รองรับ by ticket, comment, index, volume, symbol
   else if(action == "CLOSE") {
      // Priority: ticket > comment+volume > index > volume+symbol > symbol
      if(ticket > 0 && volume > 0) {
         LogMessage(LOG_INFO, "[API_CLOSE] Partial close by ticket=" + IntegerToString((int)ticket) + " vol=" + DoubleToString(volume, 2));
         return ClosePositionByTicketAndVolume(ticket, volume, "API");
      }
      else if(ticket > 0) {
         LogMessage(LOG_INFO, "[API_CLOSE] Full close by ticket=" + IntegerToString((int)ticket));
         return ClosePositionByTicket(ticket, "API");
      }
      else if(comment != "" && volume > 0) {
         LogMessage(LOG_INFO, "[API_CLOSE] Partial close by comment=" + comment + " vol=" + DoubleToString(volume, 2));
         return ClosePositionByCommentAndVolume(comment, volume, "API");
      }
      else if(comment != "") {
         LogMessage(LOG_INFO, "[API_CLOSE] Full close by comment=" + comment);
         return ClosePositionByExactComment(comment, "API");
      }
      else if(index > 0) {
         LogMessage(LOG_INFO, "[API_CLOSE] By index=" + IntegerToString(index));
         return ClosePositionByIndex(mapped_symbol, index, "API");
      }
      else if(mapped_symbol != "" && volume > 0) {
         LogMessage(LOG_INFO, "[API_CLOSE] By symbol=" + mapped_symbol + " vol=" + DoubleToString(volume, 2));
         return ClosePositionsByAmount(mapped_symbol, volume, "API");
      }
      else if(mapped_symbol != "") {
         LogMessage(LOG_INFO, "[API_CLOSE] All positions for symbol=" + mapped_symbol);
         return CloseAllPositionsBySymbol(mapped_symbol, "API");
      }
      LogMessage(LOG_WARNING, "[API_CLOSE] No valid close parameters");
      return false;
   }

   // 🔥 CLOSE_SYMBOL - ปิดทุก positions ของ symbol นั้น
   else if(action == "CLOSE_SYMBOL") {
      return CloseAllPositionsBySymbol(mapped_symbol, "API");
   }

   LogMessage(LOG_WARNING, "[API] Unknown action: " + action);
   return false;
}

//+------------------------------------------------------------------+
//| Acknowledge Command                                              |
//+------------------------------------------------------------------+
void AcknowledgeCommand(string queue_id, bool success, string error_msg = "") {
   string account = IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN));
   string url = API_ServerURL + "/api/commands/" + account + "/ack";

   // Build JSON body
   string json_body = "{\"queue_id\":\"" + queue_id + "\",\"success\":" +
                      (success ? "true" : "false") + ",\"error\":\"" + error_msg + "\"}";

   // Prepare HTTP request
   string headers = "Content-Type: application/json\r\n";
   char post[];
   char result[];
   string result_headers;
   int timeout = API_Timeout;

   // Convert JSON to char array
   StringToCharArray(json_body, post, 0, StringLen(json_body));

   // Send POST request
   int res = WebRequest("POST", url, headers, timeout, post, result, result_headers);

   if(res == 200) {
      LogMessage(LOG_DEBUG, "[API] Acknowledged: " + queue_id);
   }
   else {
      LogMessage(LOG_WARNING, "[API] Failed to acknowledge " + queue_id + " (HTTP " + IntegerToString(res) + ")");
   }
}

//+------------------------------------------------------------------+
//| Helper: Extract JSON string value                               |
//+------------------------------------------------------------------+
string ExtractJSONString(string json, string key) {
   string search = "\"" + key + "\":\"";
   int start = StringFind(json, search);
   if(start < 0) return "";

   start += StringLen(search);
   int end = StringFind(json, "\"", start);
   if(end < 0) return "";

   return StringSubstr(json, start, end - start);
}

//+------------------------------------------------------------------+
//| Helper: Extract JSON number value                               |
//+------------------------------------------------------------------+
double ExtractJSONNumber(string json, string key) {
   string search = "\"" + key + "\":";
   int start = StringFind(json, search);
   if(start < 0) return 0.0;

   start += StringLen(search);
   int end = start;

   // Find end of number (comma, brace, or end of string)
   while(end < StringLen(json)) {
      ushort ch = StringGetCharacter(json, end);
      if(ch == ',' || ch == '}' || ch == ']' || ch == ' ' || ch == '\n' || ch == '\r') break;
      end++;
   }

   string num_str = StringSubstr(json, start, end - start);
   return StringToDouble(num_str);
}

//+------------------------------------------------------------------+
//| Timer Event - API Polling & Master Monitoring                   |
//+------------------------------------------------------------------+
void OnTimer() {
   if(!Initialized) return;

   // ✅ Send Heartbeat ทุก 30 วินาที (Hard-coded: เปิดเสมอ)
   SendHeartbeat();

   // ⭐ Poll commands from API (Webhook & Slave modes)
   if(EnableWebhook || EnableSlave) {
      PollCommandsFromAPI();
   }

   // ⭐ Check Master positions and send signals (with batch processing support)
   if(EnableMaster) {
      CheckMasterPositions();
      // CheckMasterPendingOrders();  // 🔥 ปิดการ Copy Pending Orders (เปิดเฉพาะ market orders)
   }

   // ⭐ Send account balance to server (every 30 seconds)
   SendAccountBalance();
}



void OnTradeTransaction(const MqlTradeTransaction& trans,
                       const MqlTradeRequest& request,
                       const MqlTradeResult& result) {
   if(!Initialized) return;

   // ✅ Send balance immediately after any trade
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD) {
      SendAccountBalance(true);  // Force send
   }

   // ===== 🔥 MASTER: Atomic Lock Processing (FIXED) =====
   // ป้องกัน race condition เมื่อ Master เปิด orders หลายๆ ตัวอย่างรวดเร็ว
   if(EnableMaster && trans.type == TRADE_TRANSACTION_DEAL_ADD) {
      
      // 1️⃣ เช็คว่ากำลังประมวลผลอยู่หรือไม่
      if(g_is_processing_master) {
         LogMessage(LOG_DEBUG, "[MASTER] 🔒 Already processing, skip this transaction");
         return; // ❌ ถ้ากำลังทำงาน ข้ามไป
      }
      
      // 2️⃣ เช็คว่าเพิ่งประมวลผลไปหรือไม่ (debounce 1 วินาที)
      if(TimeCurrent() - g_last_master_process_time < 1) {
         LogMessage(LOG_DEBUG, "[MASTER] 🕐 Processed recently, skip");
         return; // ❌ ถ้าเพิ่งส่งไปไม่ถึง 1 วินาที ข้ามไป
      }
      
      // 3️⃣ ล็อค - ป้องกัน race condition
      g_is_processing_master = true;
      LogMessage(LOG_INFO, "[MASTER] 🔒 Lock acquired, processing positions...");
      
      // 4️⃣ รอให้ MT5 อัพเดท position ให้แน่ใจ (สำคัญมาก!)
      Sleep(300);
      
      // 5️⃣ ประมวลผล - จะจับ orders ทั้งหมดที่เปิดพร้อมกัน
      CheckMasterPositions();
      
      // 6️⃣ บันทึกเวลา
      g_last_master_process_time = TimeCurrent();
      
      // 7️⃣ ปลดล็อค
      g_is_processing_master = false;
      LogMessage(LOG_INFO, "[MASTER] 🔓 Lock released");
   }

   // ✅ SLAVE/MAP: detect partial close/open and auto-update map to new ticket
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD) {
      // หา position ใหม่ที่ยังไม่อยู่ใน Map
      for(int i = 0; i < PositionsTotal(); i++) {
         ulong new_ticket = PositionGetTicket(i);
         if(!PositionSelectByTicket(new_ticket)) continue;
         
         string pos_symbol = PositionGetString(POSITION_SYMBOL);
         double pos_volume = PositionGetDouble(POSITION_VOLUME);
         
         // เช็คว่า ticket นี้ไม่อยู่ใน Map
         bool ticket_exists = false;
         for(int j = 0; j < g_map_count; j++) {
            if(g_order_map[j].slave_ticket == new_ticket) {
               ticket_exists = true;
               break;
            }
         }
         
         if(!ticket_exists) {
            // หา mapping ที่มี symbol เดียวกันและ volume ใกล้เคียง
            for(int k = 0; k < g_map_count; k++) {
               if(g_order_map[k].symbol == pos_symbol) {
                  
                  // เช็คว่า position เก่ายังมีอยู่หรือไม่
                  if(!PositionSelectByTicket(g_order_map[k].slave_ticket)) {
                     
                     LogMessage(LOG_INFO, "[AUTO_UPDATE] Updating map: " + 
                                g_order_map[k].master_comment + 
                                " ticket " + IntegerToString((int)g_order_map[k].slave_ticket) + 
                                " → " + IntegerToString((int)new_ticket));
                     
                     // อัพเดท Map
                     g_order_map[k].slave_ticket = new_ticket;
                     g_order_map[k].volume = pos_volume;
                     return;
                  }
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Send Heartbeat to Server (No Token Required)                     |
//+------------------------------------------------------------------+
void SendHeartbeat() {
   // ✅ Hard-coded: Heartbeat เปิดเสมอ

   // ตรวจสอบว่าถึงเวลาส่งแล้วหรือยัง (ทุก 30 วินาที)
   if(TimeCurrent() - g_last_heartbeat_time < HEARTBEAT_INTERVAL)  // ✅ Hard-coded: 30 วินาที
      return;

   g_last_heartbeat_time = TimeCurrent();

   string account = IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN));
   string broker = AccountInfoString(ACCOUNT_COMPANY);
   string symbol = _Symbol;

   // JSON ไม่มี token (server ไม่บังคับ token แล้ว)
   string jsonData = StringFormat(
      "{\"account\":\"%s\",\"broker\":\"%s\",\"symbol\":\"%s\"}",
      account, broker, symbol
   );

   // สร้าง URL สำหรับ heartbeat
   string url = API_ServerURL;
   if(StringFind(url, "/api/ea/heartbeat") < 0) {
      // ถ้า URL ไม่ได้ระบุ endpoint ให้เพิ่มเอง
      if(StringSubstr(url, StringLen(url)-1) == "/") {
         url = StringSubstr(url, 0, StringLen(url)-1);
      }
      url += "/api/ea/heartbeat";
   }

   string result = SendHttpRequest(url, jsonData, API_Timeout);

   // ตรวจสอบผลลัพธ์
   if(StringFind(result, "\"success\":true") >= 0) {
      if(StringFind(result, "Account activated") >= 0) {
         LogMessage(LOG_INFO, "[HEARTBEAT] ✅ Account Activated!");
         Comment("✅ Account Activated\nStatus: Online\nBroker: " + broker);
      }
      else if(StringFind(result, "back online") >= 0) {
         LogMessage(LOG_INFO, "[HEARTBEAT] ✅ Back Online!");
      }
      else {
         LogMessage(LOG_DEBUG, "[HEARTBEAT] ✓ Sent");
      }
   }
   else if(StringFind(result, "not registered") >= 0) {
      LogMessage(LOG_WARNING, "[HEARTBEAT] ⚠️ Account not in system");
      Comment("⚠️ Not Registered\nAdd account: " + account + "\nin Account Management");
   }
   else if(StringLen(result) > 0) {
      LogMessage(LOG_WARNING, "[HEARTBEAT] Response: " + result);
   }
}



//+------------------------------------------------------------------+
