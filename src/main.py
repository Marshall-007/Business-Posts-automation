"""CLI entry point.

Usage:
    python -m src.main platforms                      # show configuration status
    python -m src.main preview                        # generate without publishing
    python -m src.main post                           # generate and publish
    python -m src.main post --platforms telegram,facebook
"""

import argparse
import sys

from . import content_generator, flows, history
from .config import Credentials, load_business_config
from .platforms import PostError, build_platforms


def main() -> int:
    parser = argparse.ArgumentParser(description="Business posts automation")
    parser.add_argument("command", choices=["platforms", "preview", "post"])
    parser.add_argument(
        "--platforms",
        help="Comma-separated subset of platforms to publish to (default: all configured)",
    )
    parser.add_argument(
        "--flow",
        help="Run a named flow from data/flows.json (overrides platforms/caption/image)",
    )
    args = parser.parse_args()

    creds = Credentials()
    business_config = load_business_config()

    # A flow can override the platform list, caption, and Instagram image.
    flow = None
    platform_filter = args.platforms
    if args.flow:
        flow = flows.get_flow(args.flow)
        if flow is None:
            print(f"Unknown flow: {args.flow}", file=sys.stderr)
            return 2
        if flow.get("platforms"):
            platform_filter = ",".join(flow["platforms"])
        if flow.get("image_url"):
            business_config = {**business_config, "image_urls": [flow["image_url"]]}

    platforms = build_platforms(creds, business_config)

    if args.command == "platforms":
        print(f"Content generation: {'Claude API' if creds.anthropic_api_key else 'templates (no ANTHROPIC_API_KEY)'}")
        for p in platforms:
            status = "configured" if p.is_configured() else "not configured"
            print(f"  {p.name:<10} {status}")
        return 0

    enabled = [p for p in platforms if p.is_configured()]
    if platform_filter:
        wanted = {name.strip().lower() for name in platform_filter.split(",")}
        unknown = wanted - {p.name for p in platforms}
        if unknown:
            print(f"Unknown platform(s): {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        enabled = [p for p in enabled if p.name in wanted]

    if flow and flow.get("caption"):
        topic = flow.get("name", args.flow)
        posts = content_generator.posts_from_caption(business_config, flow["caption"])
    else:
        topic, posts = content_generator.generate_posts(
            business_config, creds.anthropic_api_key
        )
    print(f"Topic: {topic}\n")

    if args.command == "preview":
        for name, text in posts.items():
            print(f"--- {name} ---\n{text}\n")
        if not enabled:
            print("(No platforms configured — nothing would be published.)")
        else:
            print(f"Would publish to: {', '.join(p.name for p in enabled)}")
        return 0

    # post
    if not enabled:
        print(
            "No platforms are configured. Add credentials (see SETUP.md) and retry.",
            file=sys.stderr,
        )
        return 1

    results: dict[str, str] = {}
    failures = 0
    for platform in enabled:
        text = posts[platform.name]
        try:
            post_id = platform.publish(text)
            results[platform.name] = f"ok:{post_id}"
            print(f"[ok]   {platform.name}: published (id={post_id})")
        except PostError as exc:
            failures += 1
            results[platform.name] = f"error:{exc}"
            print(f"[fail] {platform.name}: {exc}", file=sys.stderr)
        except Exception as exc:  # network errors etc.
            failures += 1
            results[platform.name] = f"error:{exc}"
            print(f"[fail] {platform.name}: unexpected error: {exc}", file=sys.stderr)

    if any(v.startswith("ok:") for v in results.values()):
        history.record_post(topic, results)

    if failures:
        print(f"\n{failures} platform(s) failed.", file=sys.stderr)
        return 1
    print("\nAll posts published successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
