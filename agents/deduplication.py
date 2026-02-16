"""
Request Deduplication Service
Prevents duplicate executions from network retries or repeated confirmations
Uses in-memory cache with 30-second TTL
"""
import hashlib
import json
import time
from typing import Dict, Any, Optional
from threading import Lock


class DeduplicationService:
    """
    In-memory request deduplication with 30-second window
    Thread-safe for concurrent requests
    """
    
    def __init__(self, ttl_seconds: int = 30):
        self.cache: Dict[str, tuple[Any, float]] = {}  # {hash: (response, expiry_time)}
        self.ttl_seconds = ttl_seconds
        self.lock = Lock()
    
    def compute_hash(self, user_id: str, intent: str, entities: Dict[str, Any], timestamp: float) -> str:
        """
        Compute request hash based on user, intent, entities, and rounded timestamp
        
        Rounding timestamp to nearest minute ensures similar requests within
        the same minute get the same hash
        """
        # Round to nearest minute
        rounded_ts = int(timestamp) - (int(timestamp) % 60)
        
        # Sort entities to ensure consistent hashing
        entities_str = json.dumps(entities, sort_keys=True)
        
        hash_input = f"{user_id}|{intent}|{entities_str}|{rounded_ts}"
        return hashlib.sha256(hash_input.encode()).hexdigest()
    
    def is_duplicate(self, user_id: str, intent: str, entities: Dict[str, Any]) -> tuple[bool, Optional[Any]]:
        """
        Check if request is a duplicate
        
        Returns:
            (is_duplicate, cached_response)
        """
        request_hash = self.compute_hash(user_id, intent, entities, time.time())
        
        with self.lock:
            # Clean expired entries
            self._clean_expired()
            
            if request_hash in self.cache:
                cached_response, expiry = self.cache[request_hash]
                if time.time() < expiry:
                    print(f"[DEDUP] Duplicate request detected for {intent}, returning cached response")
                    return True, cached_response
            
            return False, None
    
    def cache_response(self, user_id: str, intent: str, entities: Dict[str, Any], response: Any):
        """Cache response for deduplication"""
        request_hash = self.compute_hash(user_id, intent, entities, time.time())
        expiry = time.time() + self.ttl_seconds
        
        with self.lock:
            self.cache[request_hash] = (response, expiry)
            print(f"[DEDUP] Cached response for {intent}, expires in {self.ttl_seconds}s")
    
    def should_bypass(self, message: str) -> bool:
        """
        Check if user explicitly requested retry/resend
        Bypass deduplication in these cases
        """
        bypass_keywords = [
            "retry", "resend", "send again", "try again",
            "once more", "one more time", "please send",
            "send it", "do it again"
        ]
        message_lower = message.lower()
        
        for keyword in bypass_keywords:
            if keyword in message_lower:
                print(f"[DEDUP] Bypass keyword detected: '{keyword}'")
                return True
        
        return False
    
    def _clean_expired(self):
        """Remove expired entries from cache"""
        current_time = time.time()
        expired_keys = [k for k, (_, expiry) in self.cache.items() if current_time >= expiry]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            print(f"[DEDUP] Cleaned {len(expired_keys)} expired entries")
    
    def clear(self):
        """Clear all cached entries"""
        with self.lock:
            self.cache.clear()
            print("[DEDUP] Cache cleared")


# Global instance
_dedup_service = DeduplicationService(ttl_seconds=30)


def check_duplicate(user_id: str, intent: str, entities: Dict[str, Any], message: str) -> tuple[bool, Optional[Any]]:
    """
    Check if request is duplicate (module-level convenience function)
    
    Returns:
        (is_duplicate, cached_response)
    """
    # Bypass if explicit retry
    if _dedup_service.should_bypass(message):
        return False, None
    
    return _dedup_service.is_duplicate(user_id, intent, entities)


def cache_response(user_id: str, intent: str, entities: Dict[str, Any], response: Any):
    """Cache response for future deduplication"""
    _dedup_service.cache_response(user_id, intent, entities, response)
