import os
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import secrets

logger = logging.getLogger(__name__)

@dataclass
class ServerConfig:
    """Server configuration settings"""
    host: str = "0.0.0.0"
    port: int = 5000
    debug: bool = False
    secret_key: str = ""
    basic_user: str = "admin"
    basic_pass: str = "admin"

@dataclass
class WebhookConfig:
    """
    Webhook configuration settings.

    NOTE: In Multi-User SaaS mode, the 'token' field is LEGACY only.
    Each user gets their own webhook token stored in the user_tokens table.
    The global WEBHOOK_TOKEN is only for backward compatibility.
    """
    token: str = ""  # Legacy - per-user tokens are in database
    external_base_url: str = "http://localhost:5000"
    rate_limit: str = "10 per minute"

@dataclass
class MT5Config:
    """MT5 configuration settings"""
    main_path: str = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    instances_dir: str = r"C:\trading_bot\mt5_instances"
    profile_source: str = r"C:\Users\{}\AppData\Roaming\MetaQuotes\Terminal\XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
    delete_instance_files: bool = False

@dataclass
class EmailConfig:
    """Email notification configuration"""
    enabled: bool = False
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    from_email: str = ""
    to_emails: list = None
    
    def __post_init__(self):
        if self.to_emails is None:
            self.to_emails = []

@dataclass
class SymbolConfig:
    """Symbol mapping configuration - ✅ ปรับ default values ให้ดีขึ้น"""
    fetch_enabled: bool = True  # ✅ เปลี่ยนจาก False เป็น True
    fuzzy_match_threshold: float = 0.55  # ✅ เปลี่ยนจาก 0.6 เป็น 0.55 (55%)
    cache_expiry: int = 3600  # 1 ชั่วโมง
    auto_update_whitelist: bool = True  # เปิดการอัปเดต whitelist อัตโนมัติ
    
    # ✅ เพิ่ม settings ใหม่
    enable_comprehensive_mapping: bool = True  # เปิดใช้ comprehensive mapping
    minimum_similarity_threshold: float = 0.45  # threshold ต่ำสุด (45%)
    enable_fuzzy_fallback: bool = True  # เปิดใช้ fuzzy fallback
    case_sensitive: bool = False  # ไม่สนใจ case
    enable_normalization: bool = True  # เปิดใช้ normalization

@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    max_bytes: int = 10485760  # 10MB
    backup_count: int = 5
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

class ConfigManager:
    """Manage application configuration"""
    
    def __init__(self, env_file: str = ".env"):
        self.env_file = env_file
        self.config_file = "config.json"
        
        # Initialize configuration objects with improved defaults
        self.server = ServerConfig()
        self.webhook = WebhookConfig()
        self.mt5 = MT5Config()
        self.email = EmailConfig()
        self.symbol = SymbolConfig()  # ใช้ default ใหม่ที่ดีขึ้น
        self.logging = LoggingConfig()
        
        # Generate default tokens if missing
        self._generate_defaults()
        
        # Load configuration from files
        self._load_from_env()
        self._load_from_json()
        
        # Validate configuration
        self._validate_config()
        
        logger.info("[CONFIG] Configuration loaded successfully")
    
    def _generate_defaults(self):
        """Generate default values for security-sensitive settings"""
        if not self.server.secret_key:
            self.server.secret_key = secrets.token_hex(32)
            logger.info("[CONFIG] Generated new secret key")
        
        if not self.webhook.token:
            self.webhook.token = secrets.token_urlsafe(32)
            logger.info("[CONFIG] Generated new webhook token")
    
    def _load_from_env(self):
        """Load configuration from .env file"""
        try:
            from dotenv import load_dotenv
            if os.path.exists(self.env_file):
                load_dotenv(self.env_file)
            
            # Server config
            self.server.host = os.getenv('HOST', self.server.host)
            self.server.port = int(os.getenv('PORT', self.server.port))
            self.server.debug = os.getenv('DEBUG', 'False').lower() == 'true'
            self.server.secret_key = os.getenv('SECRET_KEY', self.server.secret_key)
            self.server.basic_user = os.getenv('BASIC_USER', self.server.basic_user)
            self.server.basic_pass = os.getenv('BASIC_PASS', self.server.basic_pass)
            
            # Webhook config
            self.webhook.token = os.getenv('WEBHOOK_TOKEN', self.webhook.token)
            self.webhook.external_base_url = os.getenv('EXTERNAL_BASE_URL', self.webhook.external_base_url)
            self.webhook.rate_limit = os.getenv('WEBHOOK_RATE_LIMIT', self.webhook.rate_limit)
            
            # MT5 config
            self.mt5.main_path = os.getenv('MT5_PATH', self.mt5.main_path)
            self.mt5.instances_dir = os.getenv('MT5_INSTANCES_DIR', self.mt5.instances_dir)
            self.mt5.profile_source = os.getenv('MT5_PROFILE_SOURCE', self.mt5.profile_source)
            self.mt5.delete_instance_files = os.getenv('DELETE_INSTANCE_FILES', 'False').lower() == 'true'
            
            # Email config
            self.email.enabled = os.getenv('EMAIL_ENABLED', 'False').lower() == 'true'
            self.email.smtp_server = os.getenv('SMTP_SERVER', self.email.smtp_server)
            self.email.smtp_port = int(os.getenv('SMTP_PORT', self.email.smtp_port))
            self.email.smtp_user = os.getenv('SMTP_USER', self.email.smtp_user)
            self.email.smtp_pass = os.getenv('SMTP_PASS', self.email.smtp_pass)
            self.email.from_email = os.getenv('FROM_EMAIL', self.email.smtp_user)
            
            to_emails_str = os.getenv('TO_EMAILS', '')
            if to_emails_str:
                self.email.to_emails = [email.strip() for email in to_emails_str.split(',') if email.strip()]
            
            # ✅ Symbol config - ใช้ default values ที่ดีขึ้น
            self.symbol.fetch_enabled = os.getenv('SYMBOL_FETCH_ENABLED', str(self.symbol.fetch_enabled)).lower() == 'true'
            self.symbol.fuzzy_match_threshold = float(os.getenv('FUZZY_MATCH_THRESHOLD', self.symbol.fuzzy_match_threshold))
            self.symbol.cache_expiry = int(os.getenv('SYMBOL_CACHE_EXPIRY', self.symbol.cache_expiry))
            self.symbol.auto_update_whitelist = os.getenv('AUTO_UPDATE_WHITELIST', str(self.symbol.auto_update_whitelist)).lower() == 'true'
            
            # ✅ เพิ่ม settings ใหม่
            self.symbol.enable_comprehensive_mapping = os.getenv('ENABLE_COMPREHENSIVE_MAPPING', str(self.symbol.enable_comprehensive_mapping)).lower() == 'true'
            self.symbol.minimum_similarity_threshold = float(os.getenv('MINIMUM_SIMILARITY_THRESHOLD', self.symbol.minimum_similarity_threshold))
            self.symbol.enable_fuzzy_fallback = os.getenv('ENABLE_FUZZY_FALLBACK', str(self.symbol.enable_fuzzy_fallback)).lower() == 'true'
            self.symbol.case_sensitive = os.getenv('SYMBOL_CASE_SENSITIVE', str(self.symbol.case_sensitive)).lower() == 'true'
            self.symbol.enable_normalization = os.getenv('ENABLE_SYMBOL_NORMALIZATION', str(self.symbol.enable_normalization)).lower() == 'true'
            
            # Logging config
            self.logging.level = os.getenv('LOG_LEVEL', self.logging.level).upper()
            self.logging.max_bytes = int(os.getenv('LOG_MAX_BYTES', self.logging.max_bytes))
            self.logging.backup_count = int(os.getenv('LOG_BACKUP_COUNT', self.logging.backup_count))
            
            logger.info("[CONFIG] Loaded configuration from .env file")
            
        except Exception as e:
            logger.error(f"[CONFIG] Failed to load .env file: {str(e)}")
    
    def _load_from_json(self):
        """Load configuration from JSON file"""
        if not os.path.exists(self.config_file):
            return
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Update configuration objects from JSON
            if 'server' in config_data:
                for key, value in config_data['server'].items():
                    if hasattr(self.server, key):
                        setattr(self.server, key, value)
            
            if 'webhook' in config_data:
                for key, value in config_data['webhook'].items():
                    if hasattr(self.webhook, key):
                        setattr(self.webhook, key, value)
            
            if 'mt5' in config_data:
                for key, value in config_data['mt5'].items():
                    if hasattr(self.mt5, key):
                        setattr(self.mt5, key, value)
            
            if 'email' in config_data:
                for key, value in config_data['email'].items():
                    if hasattr(self.email, key):
                        setattr(self.email, key, value)
            
            if 'symbol' in config_data:
                for key, value in config_data['symbol'].items():
                    if hasattr(self.symbol, key):
                        setattr(self.symbol, key, value)
            
            if 'logging' in config_data:
                for key, value in config_data['logging'].items():
                    if hasattr(self.logging, key):
                        setattr(self.logging, key, value)
            
            logger.info(f"[CONFIG] Loaded configuration from {self.config_file}")
            
        except Exception as e:
            logger.error(f"[CONFIG] Failed to load JSON config: {str(e)}")
    
    def _validate_config(self):
        """Validate configuration settings"""
        # Expand environment variables in paths
        self.mt5.instances_dir = os.path.expandvars(self.mt5.instances_dir)
        self.mt5.profile_source = os.path.expandvars(self.mt5.profile_source)
        
        # Validate MT5 paths
        if not os.path.exists(self.mt5.main_path):
            logger.warning(f"[CONFIG] MT5 executable not found: {self.mt5.main_path}")
        
        if not os.path.exists(self.mt5.profile_source):
            logger.warning(f"[CONFIG] MT5 profile source not found: {self.mt5.profile_source}")
        
        # Validate email config
        if self.email.enabled:
            if not self.email.smtp_user or not self.email.smtp_pass:
                logger.warning("[CONFIG] Email enabled but credentials missing")
                self.email.enabled = False
            
            if not self.email.to_emails:
                logger.warning("[CONFIG] Email enabled but no recipients configured")
                self.email.enabled = False
        
        # Validate external base URL
        if self.webhook.external_base_url.endswith('/'):
            self.webhook.external_base_url = self.webhook.external_base_url.rstrip('/')
            logger.info("[CONFIG] Removed trailing slash from external base URL")
        
        # ✅ Validate symbol config - ปรับปรุงให้ครอบคลุม
        if not 0.0 <= self.symbol.fuzzy_match_threshold <= 1.0:
            self.symbol.fuzzy_match_threshold = 0.55
            logger.warning("[CONFIG] Invalid fuzzy match threshold, reset to 0.55")
        
        if not 0.0 <= self.symbol.minimum_similarity_threshold <= 1.0:
            self.symbol.minimum_similarity_threshold = 0.45
            logger.warning("[CONFIG] Invalid minimum similarity threshold, reset to 0.45")
        
        # ตรวจสอบว่า minimum threshold ต้องต่ำกว่า main threshold
        if self.symbol.minimum_similarity_threshold >= self.symbol.fuzzy_match_threshold:
            self.symbol.minimum_similarity_threshold = self.symbol.fuzzy_match_threshold - 0.1
            logger.warning(f"[CONFIG] Adjusted minimum threshold to {self.symbol.minimum_similarity_threshold}")
        
        # Log สถานการณ์ symbol mapping
        logger.info(f"[CONFIG] Symbol mapping settings:")
        logger.info(f"  - Fetch enabled: {self.symbol.fetch_enabled}")
        logger.info(f"  - Fuzzy threshold: {self.symbol.fuzzy_match_threshold}")
        logger.info(f"  - Minimum threshold: {self.symbol.minimum_similarity_threshold}")
        logger.info(f"  - Comprehensive mapping: {self.symbol.enable_comprehensive_mapping}")
        logger.info(f"  - Normalization: {self.symbol.enable_normalization}")
    
    def save_config(self):
        """Save current configuration to JSON file"""
        try:
            config_data = {
                'server': asdict(self.server),
                'webhook': asdict(self.webhook),
                'mt5': asdict(self.mt5),
                'email': asdict(self.email),
                'symbol': asdict(self.symbol),
                'logging': asdict(self.logging)
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[CONFIG] Configuration saved to {self.config_file}")
            
        except Exception as e:
            logger.error(f"[CONFIG] Failed to save configuration: {str(e)}")
    
    def get_webhook_url(self) -> str:
        """Get complete webhook URL"""
        return f"{self.webhook.external_base_url}/webhook/{self.webhook.token}"
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary for display"""
        return {
            'server': {
                'host': self.server.host,
                'port': self.server.port,
                'debug': self.server.debug
            },
            'webhook': {
                'token_length': len(self.webhook.token),
                'external_url': self.webhook.external_base_url,
                'rate_limit': self.webhook.rate_limit
            },
            'mt5': {
                'executable_exists': os.path.exists(self.mt5.main_path),
                'profile_source_exists': os.path.exists(self.mt5.profile_source),
                'instances_dir': self.mt5.instances_dir
            },
            'email': {
                'enabled': self.email.enabled,
                'smtp_server': self.email.smtp_server,
                'recipients_count': len(self.email.to_emails)
            },
            'symbol': {
                'fetch_enabled': self.symbol.fetch_enabled,
                'fuzzy_threshold': self.symbol.fuzzy_match_threshold,
                'minimum_threshold': self.symbol.minimum_similarity_threshold,
                'comprehensive_mapping': self.symbol.enable_comprehensive_mapping,
                'auto_update': self.symbol.auto_update_whitelist,
                'normalization': self.symbol.enable_normalization
            }
        }
    
    def update_webhook_token(self) -> str:
        """Generate new webhook token"""
        old_token = self.webhook.token
        self.webhook.token = secrets.token_urlsafe(32)
        logger.info("[CONFIG] Generated new webhook token")
        return self.webhook.token
    
    # ✅ เพิ่มฟังก์ชันสำหรับการจัดการ symbol config
    def update_symbol_threshold(self, new_threshold: float) -> bool:
        """อัปเดต fuzzy match threshold"""
        if not 0.0 <= new_threshold <= 1.0:
            logger.error(f"[CONFIG] Invalid threshold: {new_threshold}")
            return False
        
        old_threshold = self.symbol.fuzzy_match_threshold
        self.symbol.fuzzy_match_threshold = new_threshold
        
        # ปรับ minimum threshold ถ้าจำเป็น
        if self.symbol.minimum_similarity_threshold >= new_threshold:
            self.symbol.minimum_similarity_threshold = max(0.0, new_threshold - 0.1)
        
        logger.info(f"[CONFIG] Updated fuzzy threshold: {old_threshold} → {new_threshold}")
        return True
    
    def toggle_comprehensive_mapping(self, enabled: bool) -> None:
        """เปิด/ปิด comprehensive mapping"""
        self.symbol.enable_comprehensive_mapping = enabled
        logger.info(f"[CONFIG] Comprehensive mapping: {'enabled' if enabled else 'disabled'}")
    
    def get_symbol_config_dict(self) -> Dict:
        """ส่งออก symbol config เป็น dict สำหรับใช้ใน symbol mapper"""
        return {
            'fetch_enabled': self.symbol.fetch_enabled,
            'fuzzy_match_threshold': self.symbol.fuzzy_match_threshold,
            'minimum_similarity_threshold': self.symbol.minimum_similarity_threshold,
            'enable_comprehensive_mapping': self.symbol.enable_comprehensive_mapping,
            'enable_fuzzy_fallback': self.symbol.enable_fuzzy_fallback,
            'case_sensitive': self.symbol.case_sensitive,
            'enable_normalization': self.symbol.enable_normalization,
            'cache_expiry': self.symbol.cache_expiry,
            'auto_update_whitelist': self.symbol.auto_update_whitelist
        }