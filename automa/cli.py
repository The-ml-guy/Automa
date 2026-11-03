"""
Command-Line Interface (CLI) for Automa.
Provides operator control for status inspection, manual runs, daemon execution,
and web dashboard launching.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
from datetime import datetime, timezone

from automa.config import get_settings, BASE_DIR
from automa.db.schema import init_db
from automa.db.repository import PostRepository
from automa.engine.generator import ContentEngine
from automa.scheduler.runner import SchedulerRunner
from automa.scheduler.windows_task import export_registration_script
from automa.web.server import run_dashboard_server


def cmd_status(args: argparse.Namespace) -> None:
    init_db()
    repo = PostRepository()
    settings = get_settings()
    counts = repo.get_queue_counts()
    recent = repo.get_recent_posts(limit=5)
    intel_stats = repo.get_intelligence_stats()

    print("\n" + "=" * 65)
    print(" AUTOMA AI CONTENT INTELLIGENCE & PUBLISHING SYSTEM")
    print("=" * 65)
    print(f" Environment:       {settings.environment}")
    print(f" Operation Mode:    {'DRY-RUN (Safe Simulation)' if settings.dry_run else 'LIVE'}")
    print(f" Publisher Engine:  {settings.publisher_type.upper()}")
    print(f" Reasoning Model:   {settings.gemini_model}")
    print(f" Config Timezone:   {settings.timezone}")
    print("-" * 65)
    print(" AI INTELLIGENCE HUB:")
    print(f"   Total Discovered : {intel_stats.get('total_discovered', 0)}")
    sources = intel_stats.get("source_breakdown", {})
    if sources:
        src_str = ", ".join(f"{k.upper()}: {v}" for k, v in sources.items())
        print(f"   By Source Feed   : {src_str}")
    print(f"   Verified Sources : {intel_stats.get('total_verified', 0)}")
    print(f"   Ranked Topics    : {intel_stats.get('total_ranked', 0)}")
    print(f"   7-Q Distillations: {intel_stats.get('total_distilled', 0)}")
    print("-" * 65)
    print(" QUEUE BREAKDOWN:")
    for status in ["SCHEDULED", "PUBLISHED", "MANUAL_REVIEW_REQUIRED", "RETRY_PENDING", "REJECTED", "FAILED"]:
        cnt = counts.get(status, 0)
        print(f"   {status:<25}: {cnt}")
    print("-" * 65)
    print(" RECENT POSTS:")
    if recent:
        for p in recent:
            print(f"   [{p.platform.upper():<9}] [{p.status:<12}] Score: {p.quality_score}/100 | {p.topic}")
    else:
        print("   (No posts recorded yet in database)")
    print("=" * 65 + "\n")


def cmd_discover(args: argparse.Namespace) -> None:
    from automa.agents.discovery import ResearchDiscoveryAgent
    init_db()
    print("[Automa] Running Agent A (Research Discovery Agent)...")
    agent = ResearchDiscoveryAgent()
    res = agent.execute({"limit_per_source": args.limit})
    print(f"[Automa] Discovery Complete. New Items Discovered: {res.get('new_items_count', 0)}")
    for src, cnt in res.get("source_breakdown", {}).items():
        print(f"   - {src.upper()}: {cnt} new item(s)")


def cmd_rank(args: argparse.Namespace) -> None:
    from automa.agents.ranking import TopicRankingAgent
    init_db()
    repo = PostRepository()
    if args.refresh:
        print("[Automa] Running Agent C (Topic Ranking Agent) on all discovered items...")
        agent = TopicRankingAgent(repo=repo)
        agent.execute()

    ranked = repo.get_top_ranked_topics(limit=args.limit)
    print(f"\n[Automa] Top Ranked AI/ML Topics ({len(ranked)} items):\n" + "-" * 75)
    for idx, r in enumerate(ranked, 1):
        print(f"[{idx}] Score: {r['total_score']:.1f}/100 | [{r['source_type'].upper()}] {r['title']}")
        print(f"    Scores: Recency={r['score_recency']} | Usefulness={r['score_usefulness']} | Significance={r['score_significance']} | Open-Source={r['score_accessibility']}")
        print(f"    URL: {r['url']}\n")


def cmd_pipeline(args: argparse.Namespace) -> None:
    from automa.agents.orchestrator import ContentIntelligencePipeline
    init_db()
    print("\n" + "=" * 65)
    print(" RUNNING END-TO-END MULTI-AGENT CONTENT INTELLIGENCE PIPELINE")
    print("=" * 65)
    orchestrator = ContentIntelligencePipeline()
    res = orchestrator.run_full_pipeline(
        discovery_limit_per_source=args.discovery_limit,
        target_platforms=["linkedin", "x"],
    )
    if res.get("success"):
        print(f"\n[Pipeline SUCCESS] Run ID: {res.get('pipeline_run_id')}")
        print(f"  Topic Selected: {res.get('topic_chosen')}")
        print(f"  Topic Score:    {res.get('topic_score')}/100")
        print(f"  Primary Source: {res.get('source_url')}")
        print(f"  Scheduled:      {res.get('posts_scheduled_count')} post(s)")
        print(f"  Flagged Review: {res.get('posts_review_count')} post(s)\n")
        for p in res.get("posts_created", []):
            print(f"  - [{p.get('platform').upper()}] Status: {p.get('status')} | Score: {p.get('quality_score')}/100")
    else:
        print(f"\n[Pipeline FAILED]: {res.get('error')}\n")


def cmd_generate(args: argparse.Namespace) -> None:
    init_db()
    print("[Automa] Running scheduled content generation cycle...")
    engine = ContentEngine()
    result = engine.run_scheduled_generation()
    print(f"[Automa] Generation Run Complete. Status: {result.get('status')}")
    if result.get("status") == "SKIPPED":
        print(f"  Reason: {result.get('reason')}")
    else:
        print(f"  Topic Chosen:     {result.get('topic')}")
        print(f"  Drafts Generated: {result.get('generated_count')}")
        print(f"  Posts Scheduled:  {result.get('scheduled_count')}")
        for p in result.get("posts", []):
            print(f"    - [{p.get('platform').upper()}] Status: {p.get('status')} | Score: {p.get('quality_score')}/100")


def cmd_publish(args: argparse.Namespace) -> None:
    init_db()
    force = getattr(args, "force", False)
    print(f"[Automa] Checking scheduled queue (force={force})...")
    runner = SchedulerRunner()
    result = runner.process_due_posts(force=force)
    print(f"[Automa] Publishing Cycle Finished.")
    print(f"  Published: {result.get('published', 0)}")
    print(f"  Failed:    {result.get('failed', 0)}")


def cmd_daemon(args: argparse.Namespace) -> None:
    init_db()
    print("[Automa] Launching persistent scheduler daemon...")
    print("[Automa] This process will run continuously in the background independent of the IDE.")
    print("[Automa] Press Ctrl+C to stop.")
    runner = SchedulerRunner()
    runner.start_daemon(blocking=True)


def cmd_autostart(args: argparse.Namespace) -> None:
    from automa.autostart import main as run_autostart
    run_autostart()


def cmd_web(args: argparse.Namespace) -> None:
    init_db()
    settings = get_settings()
    host = args.host or settings.web_host
    port = args.port or settings.web_port
    print(f"[Automa] Starting local dashboard at http://{host}:{port}")
    run_dashboard_server(host=host, port=port)


def cmd_review(args: argparse.Namespace) -> None:
    init_db()
    repo = PostRepository()
    reviews = repo.get_posts_requiring_review()
    if not reviews:
        print("\n[Automa] No posts currently require manual review. Zero backlog.\n")
        return

    print(f"\n[Automa] {len(reviews)} post(s) flagged by safety policy for manual review:\n")
    for idx, p in enumerate(reviews, 1):
        print(f" [{idx}] ID: {p.id} | Platform: {p.platform.upper()} | Topic: {p.topic}")
        print(f"     Reason: {p.manual_review_reason}")
        print(f"     Content Snippet:\n     {p.content[:150]}...\n")


def cmd_auth_linkedin(args: argparse.Namespace) -> None:
    import os
    from automa.publishers.linkedin_oauth import run_linkedin_auth_flow
    client_id = os.getenv("LINKEDIN_CLIENT_ID")
    client_secret = os.getenv("LINKEDIN_CLIENT_SECRET")
    redirect_uri = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8000/callback")

    if not client_id or not client_secret:
        print("[Error] LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET must be set in .env.")
        return

    try:
        run_linkedin_auth_flow(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)
    except Exception as e:
        print(f"[Error] LinkedIn OAuth flow failed: {e}")


def cmd_register_task(args: argparse.Namespace) -> None:
    script_path = export_registration_script()
    print(f"\n[Automa] Generated Windows Task Scheduler registration script at:")
    print(f"  {script_path}")
    print("\nTo install Automa as a persistent Windows background job:")
    print(f"  powershell -ExecutionPolicy Bypass -File \"{script_path}\"\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="automa",
        description="Automa: Autonomous, High-Quality Social Media Publishing System",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # status
    p_status = subparsers.add_parser("status", help="Display system status and queue metrics")
    p_status.set_defaults(func=cmd_status)

    # discover
    p_disc = subparsers.add_parser("discover", help="Run Agent A to discover fresh AI/ML research and code")
    p_disc.add_argument("--limit", type=int, default=5, help="Max items per source (default: 5)")
    p_disc.set_defaults(func=cmd_discover)

    # rank
    p_rank = subparsers.add_parser("rank", help="Run Agent C to score and view top-ranked AI topics")
    p_rank.add_argument("--limit", type=int, default=10, help="Max ranked topics to display (default: 10)")
    p_rank.add_argument("--refresh", action="store_true", help="Recalculate rankings across all discovered items")
    p_rank.set_defaults(func=cmd_rank)

    # pipeline
    p_pipe = subparsers.add_parser("pipeline", help="Run the complete autonomous multi-agent intelligence pipeline")
    p_pipe.add_argument("--discovery-limit", type=int, default=5, help="Items to fetch per source (default: 5)")
    p_pipe.set_defaults(func=cmd_pipeline)

    # generate
    p_gen = subparsers.add_parser("generate", help="Trigger an immediate content generation cycle")
    p_gen.set_defaults(func=cmd_generate)

    # publish
    p_pub = subparsers.add_parser("publish", help="Publish due scheduled posts now")
    p_pub.add_argument("--force", action="store_true", help="Force publication of all scheduled posts immediately")
    p_pub.set_defaults(func=cmd_publish)

    # daemon
    p_daemon = subparsers.add_parser("daemon", help="Run the persistent background scheduler")
    p_daemon.set_defaults(func=cmd_daemon)

    # start (alias for daemon)
    p_start = subparsers.add_parser("start", help="Start the 24/7 background scheduler")
    p_start.set_defaults(func=cmd_daemon)

    # autostart (runs pipeline once, then runs web dashboard + scheduler daemon)
    p_auto = subparsers.add_parser("autostart", help="Auto-start: run pipeline once + web server + scheduler")
    p_auto.set_defaults(func=cmd_autostart)

    # web
    p_web = subparsers.add_parser("web", help="Launch the local monitoring dashboard")
    p_web.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    p_web.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    p_web.set_defaults(func=cmd_web)

    # review
    p_rev = subparsers.add_parser("review", help="Inspect posts requiring manual review")
    p_rev.set_defaults(func=cmd_review)

    # auth-linkedin
    p_auth_li = subparsers.add_parser("auth-linkedin", help="Authenticate with LinkedIn to acquire Access Token and Person URN")
    p_auth_li.set_defaults(func=cmd_auth_linkedin)

    # register-task
    p_task = subparsers.add_parser("register-task", help="Generate Windows Task Scheduler registration script")
    p_task.set_defaults(func=cmd_register_task)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
