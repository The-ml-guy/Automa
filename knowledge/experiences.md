# Engineering Experiences & Production Post-Mortems

> **NOTICE FOR AI ENGINE**: 
> Only reference technical lessons and scenarios explicitly detailed in this file. 
> Do NOT invent imaginary client names, company names, revenue numbers, or fabricated outages.
> If a topic lacks an entry here, explain the engineering principles objectively without framing it as personal biographical history.

---

### Entry EXP-001: Cron Job Overlaps & Silent Data Corruption
- **Context**: High-frequency cron worker executing batch processing tasks.
- **Problem Observed**: When processing load spiked, tasks took longer than the 5-minute cron interval. A second cron instance spawned while the first was still running, leading to race conditions, double-debiting, and locked database rows.
- **Engineering Resolution**: 
  - Replaced stateless cron execution with an advisory file/database lock and an explicit state machine (`QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`).
  - Implemented persistent heartbeat timestamps. If a worker died, the task timed out cleanly rather than hanging indefinitely.
- **Key Takeaway**: Cron is a scheduler, not an orchestrator. Never run un-gated concurrent batch jobs without an explicit distributed lock or persistent queue.

---

### Entry EXP-002: SQLite WAL Mode for High-Read, Moderate-Write Workloads
- **Context**: Moving a mid-sized microservice from managed cloud PostgreSQL to an embedded SQLite database on an NVMe instance.
- **Problem Observed**: Initial concurrency bottlenecks with "database is locked" errors during simultaneous reads and writes.
- **Engineering Resolution**:
  - Enabled WAL (Write-Ahead Logging) mode: `PRAGMA journal_mode = WAL;`.
  - Configured `busy_timeout = 5000` to allow writes to wait briefly rather than failing immediately.
  - Set `synchronous = NORMAL` for optimal balance of durability and write throughput.
- **Key Takeaway**: SQLite handles concurrent readers and a single writer seamlessly when WAL mode is active. For many internal tools and edge workloads, it eliminates multi-thousand dollar database hosting bills while delivering sub-millisecond latencies.

---

### Entry EXP-003: Third-Party API Webhook Deduplication
- **Context**: Ingesting external webhooks from payment and notification providers.
- **Problem Observed**: Network retries from upstream providers regularly sent duplicate webhook events within milliseconds, triggering duplicate notifications and side effects.
- **Engineering Resolution**:
  - Created an atomic idempotency table storing `(provider, event_id, created_at)`.
  - Used database-level unique constraints so concurrent duplicate payloads failed fast at the storage layer without executing business logic.
- **Key Takeaway**: In distributed systems, "at-least-once" delivery is the standard. If your consumers are not strictly idempotent, you do not have a reliable integration.
