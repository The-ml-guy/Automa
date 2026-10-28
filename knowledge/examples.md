# Technical Code Snippets & Concrete Examples

> **NOTICE FOR AI ENGINE**:
> Use these concrete code examples and architectural blueprints when a post calls for specific, practical implementations.
> Keep code snippets concise, syntactically correct, and immediately legible on mobile and desktop feeds.

---

### Snippet EX-001: Exponential Backoff with Jitter in Python
```python
import time
import random

def retry_with_backoff(operation, max_attempts=4, base_delay=2.0, max_delay=60.0):
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except Exception as err:
            if attempt == max_attempts:
                raise err
            # Full jitter: random sleep between 0 and min(max_delay, base * 2^attempt)
            sleep_time = random.uniform(0, min(max_delay, base_delay * (2 ** (attempt - 1))))
            time.sleep(sleep_time)
```
- **Why it matters**: Prevents "thundering herd" problems where hundreds of retrying workers overwhelm a recovering API simultaneously.

---

### Snippet EX-002: Hardening SQLite Concurrency with WAL Mode
```python
import sqlite3

def get_optimized_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=10.0, isolation_level=None) # autocommit mode
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn
```
- **Why it matters**: WAL mode allows concurrent readers to proceed uninterrupted while a writer commits changes, eliminating the classic "database table locked" error in Python applications.

---

### Snippet EX-003: Content SHA-256 Fingerprint Deduplication
```python
import hashlib
import re

def compute_content_fingerprint(text: str, platform: str) -> str:
    # Normalize: lowercase, collapse whitespace, strip punctuation
    normalized = re.sub(r"[^\w\s]", "", text.lower())
    normalized = " ".join(normalized.split())
    payload = f"{platform.lower()}::{normalized}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
```
- **Why it matters**: Guarantees identical or nearly identical copy cannot be scheduled twice on the same network even if titles or timestamps vary slightly.
