import os
import re
import json
import logging
from typing import Dict, List, Optional
from difflib import SequenceMatcher
import requests

logger = logging.getLogger(__name__)

class SymbolMapper:
    """Auto symbol mapping with enhanced fuzzy matching"""
    
    def __init__(self):
        self.mapping_cache = {}
        self.base_mappings = {}
        self.custom_mappings = {}
        self.symbol_whitelist = set()
        
        # ✅ เพิ่ม built-in comprehensive mappings
        self._init_comprehensive_mappings()
        
        # Load base mappings from reference repo
        self._load_base_mappings()
        
        # Load custom user mappings
        self._load_custom_mappings()
        
        logger.info("[SYMBOL_MAPPER] Initialized successfully")
        logger.info(f"[SYMBOL_MAPPER] Loaded {len(self.base_mappings)} base mappings")
        logger.info(f"[SYMBOL_MAPPER] Loaded {len(self.custom_mappings)} custom mappings")
        logger.info(f"[SYMBOL_MAPPER] Built-in comprehensive mappings ready")
    
    def _init_comprehensive_mappings(self):
        """เตรียม mapping ที่ครอบคลุมสำหรับ symbol ยอดนิยม"""
        self.comprehensive_mappings = {
            # ===== GOLD VARIATIONS =====
            'XAUUSD': ['XAUUSD', 'XAUUSDs', 'XAUUSDm', 'XAUUSDc', 'XAUUSD.cash', 'XAUUSD.spot', 'GOLD', 'GOLDm'],
            'GOLD': ['GOLD', 'XAUUSD', 'XAUUSDs', 'XAUUSDm', 'GOLDm', 'GOLD.spot'],
            
            # ===== OIL VARIATIONS =====
            'USOIL': ['USOIL', 'usoil.cash', 'USOIL.cash', 'USOILm', 'USOILs', 'CRUDE', 'OIL', 'WTI'],
            'CRUDE': ['CRUDE', 'USOIL', 'usoil.cash', 'WTI', 'OIL'],
            'WTI': ['WTI', 'USOIL', 'usoil.cash', 'CRUDE'],
            'OIL': ['OIL', 'USOIL', 'usoil.cash', 'WTI', 'CRUDE'],
            
            # ===== S&P 500 VARIATIONS =====
            'SP500': ['SP500', 'US500', 'SPX500', 'S&P500', 'SPY', 'ES', 'US500m', 'SPX500m'],
            'US500': ['US500', 'SP500', 'SPX500', 'S&P500', 'US500m', 'US500s'],
            'SPX500': ['SPX500', 'SP500', 'US500', 'S&P500', 'SPX500m'],
            
            # ===== NASDAQ VARIATIONS =====
            'NAS100': ['NAS100', 'NASDAQ', 'NDX', 'QQQ', 'US100', 'NAS100m', 'US100m'],
            'NASDAQ': ['NASDAQ', 'NAS100', 'US100', 'NDX', 'QQQ'],
            'US100': ['US100', 'NAS100', 'NASDAQ', 'US100m', 'US100s'],
            
            # ===== DOW JONES VARIATIONS =====
            'DJ30': ['DJ30', 'DJIA', 'DOW', 'US30', 'YM', 'DJ30m', 'US30m'],
            'US30': ['US30', 'DJ30', 'DJIA', 'DOW', 'US30m', 'US30s'],
            'DJIA': ['DJIA', 'DJ30', 'US30', 'DOW'],
            'DOW': ['DOW', 'DJIA', 'DJ30', 'US30'],
            
            # ===== BITCOIN VARIATIONS =====
            'BTCUSD': ['BTCUSD', 'BTCUSDm', 'BTCUSDs', 'BTCUSD.cash', 'BTC', 'BITCOIN'],
            'BTC': ['BTC', 'BTCUSD', 'BTCUSDm', 'BITCOIN'],
            'BITCOIN': ['BITCOIN', 'BTC', 'BTCUSD', 'BTCUSDm'],
            
            # ===== MAJOR FOREX PAIRS =====
            'EURUSD': ['EURUSD', 'EURUSDm', 'EURUSDs', 'EURUSD.mini', 'EURUSD.cash'],
            'GBPUSD': ['GBPUSD', 'GBPUSDm', 'GBPUSDs', 'GBPUSD.pro', 'GBPUSD.cash'],
            'USDJPY': ['USDJPY', 'USDJPYm', 'USDJPYs', 'USDJPY.fx', 'USDJPY.cash'],
            'AUDUSD': ['AUDUSD', 'AUDUSDm', 'AUDUSDs', 'AUDUSD.cash'],
            'USDCAD': ['USDCAD', 'USDCADm', 'USDCADs', 'USDCAD.cash'],
            'USDCHF': ['USDCHF', 'USDCHFm', 'USDCHFs', 'USDCHF.cash'],
            'NZDUSD': ['NZDUSD', 'NZDUSDm', 'NZDUSDs', 'NZDUSD.cash'],
            
            # ===== CROSS PAIRS =====
            'EURGBP': ['EURGBP', 'EURGBPm', 'EURGBPs', 'EURGBP.cash'],
            'EURJPY': ['EURJPY', 'EURJPYm', 'EURJPYs', 'EURJPY.cash'],
            'GBPJPY': ['GBPJPY', 'GBPJPYm', 'GBPJPYs', 'GBPJPY.cash'],
            
            # ===== SILVER =====
            'XAGUSD': ['XAGUSD', 'XAGUSDm', 'XAGUSDs', 'XAGUSD.cash', 'SILVER', 'SILVERm'],
            'SILVER': ['SILVER', 'XAGUSD', 'XAGUSDm', 'SILVERm'],
            
            # ===== COMMODITIES =====
            'WHEAT': ['WHEAT', 'WHEATm', 'WHEAT.cash'],
            'CORN': ['CORN', 'CORNm', 'CORN.cash'],
            'SOYBEAN': ['SOYBEAN', 'SOYBEANm', 'SOYBEAN.cash'],
        }
    
    def _load_base_mappings(self):
        """Load base symbol mappings from reference repo (4607)"""
        try:
            # Try to load from local file first
            mappings_file = 'data/symbol_mappings.json'
            if os.path.exists(mappings_file):
                with open(mappings_file, 'r', encoding='utf-8') as f:
                    self.base_mappings = json.load(f)
                    logger.info(f"[SYMBOL_MAPPER] Loaded base mappings from {mappings_file}")
                    return
            
            # Otherwise try to fetch from remote
            url = "https://raw.githubusercontent.com/Jayfrej/4607/main/data/symbol_mappings.json"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                self.base_mappings = resp.json()
                logger.info(f"[SYMBOL_MAPPER] Loaded base mappings from remote")
            else:
                logger.warning(f"[SYMBOL_MAPPER] Failed to load base mappings: {resp.status_code}")
        except Exception as e:
            logger.error(f"[SYMBOL_MAPPER] Error loading base mappings: {str(e)}")
            self.base_mappings = {}
    
    def _load_custom_mappings(self):
        """Load custom mappings from local project file"""
        try:
            path = 'data/custom_symbol_mappings.json'
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    self.custom_mappings = json.load(f)
                logger.info(f"[SYMBOL_MAPPER] Loaded custom mappings: {len(self.custom_mappings)}")
            else:
                self.custom_mappings = {}
        except Exception as e:
            logger.error(f"[SYMBOL_MAPPER] Error loading custom mappings: {str(e)}")
            self.custom_mappings = {}

    def set_whitelist(self, symbols: List[str]):
        """Set available symbols whitelist"""
        self.symbol_whitelist = set(symbols) if symbols else set()
        # Clear cache when whitelist changes
        self.mapping_cache.clear()
        logger.debug(f"[SYMBOL_MAPPER] Updated whitelist: {len(self.symbol_whitelist)} symbols")

    def _from_custom_mappings(self, symbol: str) -> Optional[str]:
        """Check custom mappings"""
        return self.custom_mappings.get(symbol)

    def _from_base_mappings(self, symbol: str) -> Optional[str]:
        """Check base mappings"""
        return self.base_mappings.get(symbol)

    def _from_comprehensive_mappings(self, symbol: str, candidates: List[str]) -> Optional[str]:
        """ใช้ comprehensive mapping ที่เตรียมไว้"""
        symbol_upper = symbol.upper()
        
        # ตรวจสอบใน comprehensive mappings
        if symbol_upper in self.comprehensive_mappings:
            possible_matches = self.comprehensive_mappings[symbol_upper]
            logger.debug(f"[SYMBOL_MAPPER] Found comprehensive mapping for {symbol}: {possible_matches}")
            
            # หาใน candidates
            for candidate in candidates:
                for possible in possible_matches:
                    if candidate.upper() == possible.upper():
                        logger.info(f"[SYMBOL_MAPPER] ✅ Comprehensive mapping: {symbol} → {candidate}")
                        return candidate
        
        return None

    def _normalize_symbol(self, symbol: str) -> str:
        """Enhanced symbol normalization - ปรับปรุงให้จัดการครอบคลุมมากขึ้น"""
        if not symbol:
            return ""
        
        # Convert to uppercase first
        normalized = symbol.upper().strip()
        
        # ✅ เพิ่ม suffix และ prefix ใหม่ๆ ที่พบบ่อย
        suffixes_to_remove = [
            # Single letter suffixes (ที่พบบ่อยที่สุด)
            's', 'm', 'c', 'i', 'f', 'p', 'x', 'z', 'e',  # เช่น XAUUSDs, XAUUSDm
            
            # Multiple letter suffixes  
            '_s', '.s', '_m', '.m', '_c', '.c', '_i', '.i',
            '_mini', '.mini', '_micro', '.micro', '_maj', '.maj',
            '.cash', '_cash', '.spot', '_spot', '.raw', '_raw',
            '_fx', '.fx', '.pro', '_pro', '.ecn', '_ecn',
            '.stp', '_stp', '.dma', '_dma', '.ndd', '_ndd',
            
            # Broker-specific suffixes
            'dm', 'sm', 'lm', 'xl', 'xs', 'md', 'lg',  # เช่น BTCUSDm → BTCUSD
            '_var', '.var', '_fix', '.fix', '_float', '.float',
            
            # Time-based และ Version suffixes
            '_1', '_2', '_3', '_4', '_5', '_6', '_7', '_8', '_9',
            '.1', '.2', '.3', '.4', '.5', '.6', '.7', '.8', '.9',
            '_v1', '_v2', '_v3', '.v1', '.v2', '.v3',
        ]
        
        # ลองลบ suffix ทีละตัว (เรียงจากยาวไปสั้น)
        suffixes_to_remove.sort(key=len, reverse=True)
        
        for suffix in suffixes_to_remove:
            if normalized.endswith(suffix.upper()):
                normalized = normalized[:-len(suffix)]
                logger.debug(f"[SYMBOL_MAPPER] Removed suffix '{suffix}': {symbol} → {normalized}")
                break
        
        # Remove common prefixes
        prefixes_to_remove = [
            'M_', 'MINI_', 'MICRO_', 'FX_', 'FOREX_', 'CFD_', 
            'SPOT_', 'CASH_', 'DMA_', 'STP_', 'ECN_', 'PRO_',
            'RAW_', 'VAR_', 'FIX_', 'NDD_', 'B_', 'A_'
        ]
        
        for prefix in prefixes_to_remove:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
                logger.debug(f"[SYMBOL_MAPPER] Removed prefix '{prefix}': {symbol} → {normalized}")
                break
        
        # Remove special characters and trailing numbers
        normalized = re.sub(r'[^a-zA-Z0-9]', '', normalized)
        normalized = re.sub(r'\d+$', '', normalized)  # Remove trailing numbers
        
        return normalized

    def _similarity(self, a: str, b: str) -> float:
        """คำนวณความคล้าย - ปรับปรุงให้แม่นยำขึ้น"""
        if not a or not b:
            return 0.0
        
        # Basic similarity
        basic_score = SequenceMatcher(None, a, b).ratio()
        
        # ✅ เพิ่ม bonus สำหรับการ match แบบพิเศษ
        
        # Bonus 1: ถ้า normalized version เหมือนกัน
        norm_a = self._normalize_symbol(a)
        norm_b = self._normalize_symbol(b)
        if norm_a == norm_b and norm_a:
            basic_score = max(basic_score, 0.9)  # ให้คะแนนสูง
            logger.debug(f"[SYMBOL_MAPPER] Normalized match: {a}({norm_a}) ≈ {b}({norm_b}) = {basic_score}")
        
        # Bonus 2: ถ้าตัวหนึ่งมี suffix ที่รู้จัก
        known_suffixes = ['s', 'm', 'c', 'i', 'f', 'p', 'x', 'dm', 'sm', 'lm', 'cash', 'spot', 'mini']
        for suffix in known_suffixes:
            if (a.lower() == b.lower() + suffix.lower()) or (b.lower() == a.lower() + suffix.lower()):
                basic_score = max(basic_score, 0.85)
                logger.debug(f"[SYMBOL_MAPPER] Suffix match: {a} ≈ {b} = {basic_score}")
                break
        
        # Bonus 3: ถ้าเป็น common substitutions
        common_subs = {
            ('SP500', 'US500'): 0.95,
            ('NAS100', 'US100'): 0.95,
            ('DJ30', 'US30'): 0.95,
            ('USOIL', 'CRUDE'): 0.9,
            ('GOLD', 'XAUUSD'): 0.9,
            ('SILVER', 'XAGUSD'): 0.9,
            ('BTC', 'BTCUSD'): 0.9,
            ('BITCOIN', 'BTCUSD'): 0.85,
        }
        
        for (s1, s2), score in common_subs.items():
            if (a.upper() == s1 and b.upper() == s2) or (a.upper() == s2 and b.upper() == s1):
                basic_score = max(basic_score, score)
                logger.debug(f"[SYMBOL_MAPPER] Common substitution: {a} ≈ {b} = {basic_score}")
                break
        
        return basic_score

    def _try_exact_case_insensitive(self, symbol: str, candidates: List[str]) -> Optional[str]:
        """ลองหา exact match แบบไม่สนใจ case"""
        lower = symbol.lower()
        for s in candidates:
            if s.lower() == lower:
                logger.debug(f"[SYMBOL_MAPPER] Case-insensitive match: {symbol} → {s}")
                return s
        return None

    def _try_normalized_match(self, symbol: str, candidates: List[str]) -> Optional[str]:
        """ลองหา match หรือ normalized version"""
        target = self._normalize_symbol(symbol)
        if not target:
            return None
            
        for s in candidates:
            # ตรวจสอบ normalized version
            if self._normalize_symbol(s) == target:
                logger.debug(f"[SYMBOL_MAPPER] Normalized match: {symbol}({target}) → {s}")
                return s
        return None

    def _try_fuzzy(self, symbol: str, candidates: List[str], threshold: float = 0.55) -> Optional[str]:
        """
        ลองหา fuzzy match - ใช้ threshold 0.55 (55%) เป็น default
        เพื่อให้ครอบคลุมกรณีที่คล้ายกันมากกว่าครึ่ง แต่ไม่เกินไป
        """
        if not candidates:
            return None
            
        best = None
        best_score = threshold
        
        # ลองทั้ง original และ normalized
        for s in candidates:
            # Score 1: เปรียบเทียบตรงๆ
            score1 = self._similarity(symbol, s)
            
            # Score 2: เปรียบเทียบ normalized
            score2 = self._similarity(self._normalize_symbol(symbol), self._normalize_symbol(s))
            
            # เอาคะแนนสูงสุด
            score = max(score1, score2)
            
            if score > best_score:
                best_score = score
                best = s
                logger.debug(f"[SYMBOL_MAPPER] Fuzzy candidate: {symbol} ≈ {s} = {score:.3f}")
        
        if best:
            logger.info(f"[SYMBOL_MAPPER] ✅ Fuzzy match: {symbol} → {best} (score: {best_score:.3f})")
        
        return best

    def map_symbol(self, symbol: str, available_symbols: Optional[List[str]] = None) -> Optional[str]:
        """
        Public API: map incoming symbol to broker symbol - ปรับปรุงลำดับการค้นหา
        Default threshold = 0.55 (55% similarity) เพื่อให้ครอบคลุมแต่ไม่เกินไป
        """
        try:
            if not symbol:
                return None
            
            # Cache check
            cache_key = f"{symbol}_{hash(str(sorted(available_symbols or [])))}"
            if cache_key in self.mapping_cache:
                result = self.mapping_cache[cache_key]
                logger.debug(f"[SYMBOL_MAPPER] Cache hit: {symbol} → {result}")
                return result
            
            candidates = list(self.symbol_whitelist or [])
            if available_symbols:
                candidates = list(available_symbols)

            logger.debug(f"[SYMBOL_MAPPER] Mapping '{symbol}' against {len(candidates)} candidates")

            # 1) ลองหา exact match ก่อน (case-sensitive)
            if candidates and symbol in candidates:
                self.mapping_cache[cache_key] = symbol
                logger.debug(f"[SYMBOL_MAPPER] Exact match: {symbol}")
                return symbol

            # 2) ลอง custom mappings
            mapped = self._from_custom_mappings(symbol)
            if mapped and (not candidates or mapped in candidates):
                self.mapping_cache[cache_key] = mapped
                logger.debug(f"[SYMBOL_MAPPER] Custom mapping: {symbol} → {mapped}")
                return mapped

            # 3) ลอง base mappings
            mapped = self._from_base_mappings(symbol)
            if mapped and (not candidates or mapped in candidates):
                self.mapping_cache[cache_key] = mapped
                logger.debug(f"[SYMBOL_MAPPER] Base mapping: {symbol} → {mapped}")
                return mapped

            # ✅ 4) ลอง comprehensive mappings (ใหม่!)
            if candidates:
                comprehensive = self._from_comprehensive_mappings(symbol, candidates)
                if comprehensive:
                    self.mapping_cache[cache_key] = comprehensive
                    return comprehensive

            # 5) ลอง exact match (case-insensitive)
            if candidates:
                ci = self._try_exact_case_insensitive(symbol, candidates)
                if ci:
                    self.mapping_cache[cache_key] = ci
                    return ci

            # 6) ลอง normalized match
            if candidates:
                nm = self._try_normalized_match(symbol, candidates)
                if nm:
                    self.mapping_cache[cache_key] = nm
                    return nm

            # ✅ 7) ลอง fuzzy match (threshold 0.55 = 55% เป็น default)
            if candidates:
                fm = self._try_fuzzy(symbol, candidates, threshold=0.55)  # 55% similarity
                if fm:
                    self.mapping_cache[cache_key] = fm
                    return fm

            # 8) ลอง fuzzy match ด้วย threshold ต่ำขึ้น (สำหรับกรณียากๆ)
            if candidates:
                fm_low = self._try_fuzzy(symbol, candidates, threshold=0.45)  # 45% minimum
                if fm_low:
                    logger.warning(f"[SYMBOL_MAPPER] Low-confidence match: {symbol} → {fm_low}")
                    self.mapping_cache[cache_key] = fm_low
                    return fm_low

            # 9) ไม่พบ
            logger.warning(f"[SYMBOL_MAPPER] ❌ No mapping found for '{symbol}'")
            self.mapping_cache[cache_key] = None
            return None

        except Exception as e:
            logger.error(f"[SYMBOL_MAPPER] map_symbol error: {str(e)}")
            return None

    # ✅ เพิ่มฟังก์ชันป้องกันการ map ผิดแบบ (เช่น XAUUSD → XAUEUR)
    def _is_valid_mapping(self, source: str, target: str) -> bool:
        """ตรวจสอบว่าการ mapping นั้นสมเหตุสมผลหรือไม่"""
        # ถ้ามี base currency ที่ต่างกันมาก ให้ถือว่าไม่ valid
        source_norm = self._normalize_symbol(source)
        target_norm = self._normalize_symbol(target)
        
        # ถ้า normalized แล้วต่างกันมาก (< 50%) ให้ reject
        similarity = SequenceMatcher(None, source_norm, target_norm).ratio()
        if similarity < 0.5:
            logger.debug(f"[SYMBOL_MAPPER] Invalid mapping rejected: {source} → {target} (similarity: {similarity:.3f})")
            return False
            
        return True

    def add_custom_mapping(self, src: str, dst: str) -> bool:
        """เพิ่ม custom mapping"""
        try:
            if not src or not dst:
                return False
            self.custom_mappings[src] = dst
            self._save_custom_mappings()
            # invalidate cache
            self.mapping_cache.clear()
            logger.info(f"[SYMBOL_MAPPER] Added custom mapping: {src} → {dst}")
            return True
        except Exception as e:
            logger.error(f"[SYMBOL_MAPPER] add_custom_mapping error: {str(e)}")
            return False

    def remove_custom_mapping(self, src: str) -> bool:
        """ลบ custom mapping"""
        try:
            if src in self.custom_mappings:
                removed = self.custom_mappings.pop(src, None)
                self._save_custom_mappings()
                self.mapping_cache.clear()
                logger.info(f"[SYMBOL_MAPPER] Removed custom mapping: {src} → {removed}")
                return True
            return False
        except Exception as e:
            logger.error(f"[SYMBOL_MAPPER] remove_custom_mapping error: {str(e)}")
            return False

    def _save_custom_mappings(self):
        """บันทึก custom mappings ลงไฟล์"""
        try:
            os.makedirs('data', exist_ok=True)
            path = 'data/custom_symbol_mappings.json'
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.custom_mappings, f, ensure_ascii=False, indent=2)
            logger.debug(f"[SYMBOL_MAPPER] Saved custom mappings to {path}")
        except Exception as e:
            logger.error(f"[SYMBOL_MAPPER] Failed to save custom mappings: {str(e)}")

    def export_mappings(self, filename: str = 'data/exported_symbol_mappings.json'):
        """ส่งออก mappings ทั้งหมด"""
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            payload = {
                "base": self.base_mappings,
                "custom": self.custom_mappings,
                "comprehensive": self.comprehensive_mappings,
                "cache": self.mapping_cache
            }
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            logger.info(f"[SYMBOL_MAPPER] Exported mappings to {filename}")
            
        except Exception as e:
            logger.error(f"[SYMBOL_MAPPER] Failed to export mappings: {str(e)}")
    
    def test_mapping(self, test_symbols: List[str], available_symbols: Optional[List[str]] = None) -> Dict:
        """ทดสอบ mapping สำหรับ symbol ต่างๆ"""
        results = {}
        for symbol in test_symbols:
            mapped = self.map_symbol(symbol, available_symbols)
            results[symbol] = {
                'mapped': mapped,
                'success': mapped is not None,
                'normalized': self._normalize_symbol(symbol),
                'similarity': self._similarity(symbol, mapped) if mapped else 0.0
            }
        return results

    def get_stats(self) -> Dict:
        """ดูสถิติ mapping"""
        return {
            'base_mappings_count': len(self.base_mappings),
            'custom_mappings_count': len(self.custom_mappings),
            'comprehensive_mappings_count': len(self.comprehensive_mappings),
            'cache_size': len(self.mapping_cache),
            'whitelist_size': len(self.symbol_whitelist)
        }

    # สำหรับการ debug
    def debug_symbol_similarity(self, symbol1: str, symbol2: str) -> Dict:
        """ดู similarity score ระหว่าง 2 symbol"""
        return {
            'original_score': SequenceMatcher(None, symbol1, symbol2).ratio(),
            'normalized_score': SequenceMatcher(None, 
                self._normalize_symbol(symbol1), 
                self._normalize_symbol(symbol2)).ratio(),
            'enhanced_score': self._similarity(symbol1, symbol2),
            'symbol1_normalized': self._normalize_symbol(symbol1),
            'symbol2_normalized': self._normalize_symbol(symbol2),
            'is_valid_mapping': self._is_valid_mapping(symbol1, symbol2)
        }