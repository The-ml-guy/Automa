# Verified Sources & Technical References

> **NOTICE FOR AI ENGINE**:
> When a post cites industry research, RFC standards, or official documentation, cite only verified sources listed here or authoritative primary references.
> Never cite fabricated studies or anonymous statistics.

---

### Source SRC-001: SQLite Official Documentation
- **Topic**: Write-Ahead Logging (WAL) and Concurrency Model
- **Reference**: https://sqlite.org/wal.html
- **Verified Facts**:
  - In WAL mode, changes are appended to a separate `-wal` file instead of directly overwriting the main database.
  - Readers never block writers, and writers never block readers.
  - Default checkpointing occurs automatically when the WAL file reaches 1,000 pages (~4MB).

---

### Source SRC-002: AWS Architecture Blog — Exponential Backoff And Jitter
- **Authors**: Marc Brooker, Amazon Web Services
- **Topic**: Distributed System Retries & Thundering Herd Prevention
- **Reference**: https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
- **Verified Facts**:
  - Unjittered exponential backoff clusters client retry attempts into simultaneous spikes.
  - "Full Jitter" (`random(0, backoff)`) produces the lowest overall network contention and fastest completion times under load.

---

### Source SRC-003: RFC 7231 / RFC 9110 — HTTP Semantics & Idempotent Methods
- **Topic**: Safe and Idempotent HTTP Methods
- **Reference**: https://www.rfc-editor.org/rfc/rfc9110#section-9.2.2
- **Verified Facts**:
  - Methods `GET`, `HEAD`, `PUT`, `DELETE` are defined as idempotent: multiple identical requests must produce the exact same side-effect as a single request.
  - `POST` is not inherently idempotent, requiring an application-level `Idempotency-Key` or unique fingerprint header to guarantee safe retries.

---

### Source SRC-004: Postiz Public API Specification
- **Topic**: Multi-Platform Social Media Scheduling API
- **Reference**: https://docs.postiz.com / https://github.com/gitroomhq/postiz-app
- **Verified Facts**:
  - Endpoint `POST /public/v1/posts` accepts `type: "now" | "schedule" | "draft"`.
  - Schedule requests require an ISO 8601 UTC timestamp in the `date` field.
  - Authentication is passed via the `Authorization: <api-key>` header.
