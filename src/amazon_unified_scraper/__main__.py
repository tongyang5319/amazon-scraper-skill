"""
    CLI entry point for the unified Amazon scraper.
"""

import logging
import os
import sys

# Fix Windows console GBK encoding so Unicode characters print without crash
if sys.platform == "win32":
    os.system("chcp 65001 >NUL 2>&1")

import click

from amazon_unified_scraper.collector import UnifiedCollector
from amazon_unified_scraper.detail_scraper import DetailScraper


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@click.command()
@click.option(
    "--url",
    "-u",
    "urls",
    help="Amazon category page URL. Can be specified multiple times.",
    multiple=True,
    type=str,
)
@click.option(
    "--file",
    "-f",
    "url_file",
    help="Text file with one URL per line.",
    type=click.Path(exists=True),
    default=None,
)
@click.option(
    "--interactive",
    "-i",
    is_flag=True,
    default=False,
    help="Interactive mode: enter URLs one by one.",
)
@click.option(
    "--max-list",
    "max_list",
    help="Max products to scrape from list page per category (default: 100).",
    default=100,
    show_default=True,
    type=int,
)
@click.option(
    "--max-detail",
    "max_detail",
    help="Max products to visit detail pages per category (default: same as --max-list).",
    default=None,
    show_default=True,
    type=int,
)
@click.option(
    "--max-reviews",
    help="Max reviews to collect per product detail (default: 10).",
    default=10,
    show_default=True,
    type=int,
)
@click.option(
    "--delay-min",
    help="Minimum delay between detail page visits in seconds (default: 8.0).",
    default=8.0,
    show_default=True,
    type=float,
)
@click.option(
    "--delay-max",
    help="Maximum delay between detail page visits in seconds (default: 15.0).",
    default=15.0,
    show_default=True,
    type=float,
)
@click.option(
    "--output-dir",
    help="Folder to save CSV output (default: data/).",
    default="data",
    show_default=True,
    type=click.Path(),
)
@click.option(
    "--postal-code",
    help="Postal code for country/region targeting (e.g., 10001 for US New York).",
    default=None,
    type=str,
)
@click.option(
    "--format",
    "output_format",
    help="Output format: xlsx (default, with embedded product images) or csv.",
    default="xlsx",
    type=click.Choice(["csv", "xlsx"]),
)
@click.option(
    "--retry-asin",
    "retry_asins",
    help="Re-check specific ASIN(s) for missing fields (bought_in_past_month, etc.).",
    multiple=True,
    type=str,
)
@click.option(
    "--auto-retry/--no-auto-retry",
    "auto_retry",
    default=True,
    help="Automatically re-scrape products with missing fields after initial scrape (default: enabled).",
)
def scrape(
    urls: tuple[str],
    url_file: str | None,
    interactive: bool,
    max_list: int,
    max_detail: int | None,
    max_reviews: int,
    delay_min: float,
    delay_max: float,
    output_dir: str,
    postal_code: str | None,
    output_format: str,
    retry_asins: tuple[str],
    auto_retry: bool,
) -> None:
    """
    Unified Amazon scraper: list page + detail page.

    Scrapes New Releases / Best Sellers pages, visits each product's
    detail page, and outputs a CSV (and optionally XLSX with embedded images).

    Examples:
        # Single URL
        poetry run python -m amazon_unified_scraper \\
            -u "https://www.amazon.com/gp/new-releases/automotive/15706941"

        # Multiple URLs
        poetry run python -m amazon_unified_scraper \\
            -u "https://www.amazon.com/gp/new-releases/automotive/15706941" \\
            -u "https://www.amazon.com/gp/new-releases/electronics/2201763011"

        # From file
        poetry run python -m amazon_unified_scraper -f urls.txt

        # With images in XLSX
        poetry run python -m amazon_unified_scraper \\
            -u "..." --format xlsx

        # Re-check specific ASIN(s) for missing bought_in_past_month
        poetry run python -m amazon_unified_scraper \\
            --retry-asin B0FH1L3LM1 --retry-asin B0G48MHVYV

        # Auto-retry: automatically re-scrape products with missing fields
        poetry run python -m amazon_unified_scraper \\
            -u "..." --auto-retry

    Output:
        data/新品榜_{细分类目名}_{日期}.xlsx  (default, with images)
    """

    # ── Safe echo for Windows GBK console ─────────────────────────────────
    def _safe(val) -> str:
        """Convert value to safe string for GBK console output."""
        if val is None:
            return "N/A"
        s = str(val)
        try:
            s.encode("gbk")
            return s
        except UnicodeEncodeError:
            return s.encode("gbk", errors="replace").decode("gbk")

    # ── ASIN Retry Mode ────────────────────────────────────────────────────
    if retry_asins:
        click.echo(f"ASIN Retry Mode: {len(retry_asins)} ASIN(s) to re-check")
        click.echo("-" * 60)
        detail_scraper = DetailScraper(postal_code=postal_code)
        for asin in retry_asins:
            try:
                click.echo(f"\n  Re-checking ASIN: {asin}")
                detail = detail_scraper.scrape(f"https://www.amazon.com/dp/{asin}", asin)
                click.echo(f"  Result:")
                click.echo(f"    brand:              {_safe(detail.brand)}")
                click.echo(f"    bought_in_past_month: {_safe(detail.bought_in_past_month)}")
                click.echo(f"    has_coupon:        {detail.has_coupon}")
                if detail.coupon_text:
                    click.echo(f"    coupon_text:       {_safe(detail.coupon_text)}")
                click.echo(f"    product_size:      {_safe(detail.product_size)}")
                click.echo(f"    product_weight:    {_safe(detail.product_weight)}")
                click.echo(f"    sub_category_name: {_safe(detail.sub_category_name)}")
                click.echo(f"    sub_category_rank: {_safe(detail.sub_category_rank)}")
                click.echo(f"    rating:            {_safe(detail.rating)}")
                click.echo(f"    review_count:      {_safe(detail.review_count)}")
                click.echo(f"    has_a_plus:        {detail.has_a_plus}")
                if detail.bullet_points:
                    for i, bp in enumerate(detail.bullet_points[:3], 1):
                        click.echo(f"    bullet_{i}:        {_safe(bp[:60])}...")
            except Exception as e:
                click.echo(f"  Failed: {e}")
        return

    # Collect URLs
    all_urls: list[str] = list(urls)

    if interactive:
        click.echo("Enter URLs, one per line. Leave blank and press Enter to start.")
        while True:
            line = click.prompt("", default="", show_default=False).strip()
            if not line:
                break
            all_urls.append(line)
    elif url_file:
        with open(url_file, "r", encoding="utf-8") as fh:
            file_urls = [line.strip() for line in fh if line.strip()]
            all_urls.extend(file_urls)

    if not all_urls:
        click.echo("Error: No URLs provided. Use --url/-u, --file/-f, or --interactive/-i.")
        click.echo("Hint: Use --retry-asin to re-check specific ASIN(s) without a URL.")
        return

    # Deduplicate while preserving order
    seen = set()
    unique_urls = []
    for u in all_urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)

    os.makedirs(output_dir, exist_ok=True)

    collector = UnifiedCollector(
        output_dir=output_dir,
        delay_range=(delay_min, delay_max),
        postal_code=postal_code,
        output_format=output_format,
        auto_retry=auto_retry,
    )

    click.echo(f"Categories to process: {len(unique_urls)}")
    if postal_code:
        click.echo(f"Target postal code: {postal_code}")
    click.echo("-" * 60)

    results: list[str] = []
    for idx, url in enumerate(unique_urls, 1):
        click.echo(f"\n[{idx}/{len(unique_urls)}] {url}")
        result = collector.scrape_category(
            url=url,
            max_list_products=max_list,
            max_detail_products=max_detail,
            max_reviews=max_reviews,
        )
        if result:
            results.append(result)

    click.echo(f"\n{'='*60}")
    click.echo(f"All done. Processed {len(unique_urls)} categories.")
    if results:
        click.echo("Output files:")
        for r in results:
            click.echo(f"  {r}")


if __name__ == "__main__":
    scrape()
