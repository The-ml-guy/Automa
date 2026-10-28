# Architectural Opinions & Technical Perspectives

> **NOTICE FOR AI ENGINE**:
> Use these perspectives when crafting thoughtful, defensible commentary.
> Never claim extreme or contrarian positions purely for engagement bait.
> Every opinion must be supported by practical tradeoffs and concrete failure modes.

---

### OPIN-001: Premature Microservices are Technical Debt in Disguise
- **Perspective**: Breaking a system into multiple microservices before understanding domain boundaries introduces distributed systems complexity (network partitions, partial failures, distributed tracing, cross-service transactions) without solving the underlying architectural problem.
- **Defensible Nuance**: Microservices are an organizational scaling pattern, not an engineering speed hack. A well-modularized single-process architecture or modular monolith with clean domain boundaries is faster to develop, cheaper to host, and significantly easier to reason about for 95% of applications.

---

### OPIN-002: Deterministic Verification Must Precede Stochastic LLM Output
- **Perspective**: You cannot rely on an LLM to reliably grade its own output. Asking a model "Are you sure this is correct?" yields false confidence.
- **Defensible Nuance**: Production AI pipelines must sandwich probabilistic models between deterministic boundaries:
  1. Strict input validation and schema constraints before prompting.
  2. Concrete linters, regex checkers, factual heuristic gates, and schema parsers after generation.
  If an output violates a hard programmatic constraint, reject or retry it deterministically rather than trusting self-assessment.

---

### OPIN-003: Cron is not an Orchestrator
- **Perspective**: Simple operating system cron (`crontab`) lacks lifecycle awareness, persistent state tracking, deduplication, and failure recovery.
- **Defensible Nuance**: While cron is fine for running a backup script, autonomous publishing and multi-step business pipelines require a persistent queue with discrete states (`QUEUED`, `PROCESSING`, `SUCCEEDED`, `RETRY_PENDING`, `FAILED`) and timeout heartbeats to survive server restarts and transient upstream outages.

---

### OPIN-004: Code Simplicity Outlives Clever Frameworks
- **Perspective**: The best code is the code you don't have to debug at 3 AM. Avoid adding heavy third-party dependencies when standard libraries or simple 50-line modules solve the problem cleanly.
- **Defensible Nuance**: Every added dependency introduces supply chain risk, maintenance churn, and potential deprecation. Value boring, predictable, well-tested code over the latest trending library.
