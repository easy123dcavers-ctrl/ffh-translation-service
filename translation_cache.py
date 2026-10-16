"""Small, opt-in, process-local translation cache. No persistence or network IO."""
from collections import OrderedDict
from threading import RLock
from time import monotonic


class TranslationCache:
    """Bounded, TTL-limited exact-input cache, isolated by language and model generation."""

    def __init__(self, max_entries=128, ttl_seconds=600, max_source_chars=512,
                 max_output_chars=4096, clock=None):
        if min(max_entries, ttl_seconds, max_source_chars, max_output_chars) <= 0:
            raise ValueError("cache limits must be positive")
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self.max_source_chars = max_source_chars
        self.max_output_chars = max_output_chars
        self.clock = clock or monotonic
        self.entries = OrderedDict()
        self.lock = RLock()

    def clear(self):
        with self.lock:
            self.entries.clear()

    def run(self, source, from_lang, to_lang, model_generation, compute):
        # Do not retain long content, non-string inputs or blank requests.
        eligible = isinstance(source, str) and 0 < len(source) <= self.max_source_chars
        if not eligible:
            return compute()
        key = (from_lang, to_lang, model_generation, source)
        with self.lock:
            entry = self.entries.get(key)
            if entry is not None:
                expiry, result = entry
                if expiry > self.clock():
                    self.entries.move_to_end(key)
                    return result
                del self.entries[key]
        # Compute outside the lock; exceptions deliberately do not populate the cache.
        result = compute()
        if isinstance(result, str) and result.strip() and len(result) <= self.max_output_chars:
            with self.lock:
                self.entries[key] = (self.clock() + self.ttl_seconds, result)
                self.entries.move_to_end(key)
                while len(self.entries) > self.max_entries:
                    self.entries.popitem(last=False)
        return result
