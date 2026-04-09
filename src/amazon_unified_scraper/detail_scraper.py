"""
    Detail page scraper for Amazon product pages.
    Uses requests + BeautifulSoup (no Selenium) for reliability and speed.
    Extracts: brand, sales, coupon, size, weight, bullet points,
    sub-category info, A+ content, and reviews.
"""

import logging
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from amazon_unified_scraper.models import DetailProduct
from amazon_unified_scraper.utils import random_user_agent, random_delay


class DetailScraper:
    """
    Scrapes Amazon product detail pages using HTTP requests + BeautifulSoup.
    No Selenium/ChromeDriver needed - avoids browser automation issues.
    """

    def __init__(self, postal_code: str | None = None, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger if logger else logging.getLogger(__name__)
        self._session = requests.Session()
        self._postal_code = postal_code
        # Rotating user agents
        self._ua_index = 0

    def _get_headers(self) -> dict:
        """Return fresh HTTP headers with rotating User-Agent + US locale."""
        ua = random_user_agent()
        return {
            "User-Agent": ua,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "TE": "Trailers",
        }

    def _parse(self, html: str, asin: str) -> DetailProduct:
        """Parse product detail HTML with BeautifulSoup."""
        soup = BeautifulSoup(html, "html.parser")

        # ── CAPTCHA / Anti-bot Detection ───────────────────────────────────────
        # Check for common CAPTCHA or blocked page indicators
        page_text = soup.get_text()[:500].lower()
        captcha_indicators = [
            "enter the characters you see below",
            "sorry, we just need to make sure you're not a robot",
            "type the characters you see",
            "captcha",
            "api-services-access",
        ]
        for indicator in captcha_indicators:
            if indicator in page_text:
                raise Exception(f"CAPTCHA/bot detection page for ASIN {asin}")

        # ── Brand ──────────────────────────────────────────────────────────────
        brand = None
        try:
            byline = soup.find("a", {"id": "bylineInfo"})
            if byline:
                brand = byline.get_text(strip=True)
                brand = re.sub(r"^Brand[:\s]+", "", brand, flags=re.I)
                brand = re.sub(r"^Visit the\s+", "", brand, flags=re.I).strip()
        except Exception:
            pass

        # ── Monthly sales (bought in past month/week) ────────────────────────────
        monthly_sales = None
        try:
            bought_pattern = re.compile(
                r"bought in past (?:month|week)|bought.*past.*(?:month|week)|月购买|过去.*月.*购买",
                re.I
            )
            sales_value_pattern = re.compile(
                r"\d[\d,]*\+\s*bought in past (?:month|week)|月购买\d+",
                re.I
            )
            for tag in soup.find_all(["span", "div", "p", "td", "li"]):
                text = tag.get_text(separator=" ", strip=True)
                if bought_pattern.search(text) and 0 < len(text) < 400 and len(text) > 5:
                    # Try to extract just the sales value (e.g., "6K+ bought in past week")
                    m = sales_value_pattern.search(text)
                    if m:
                        monthly_sales = m.group().strip()
                    else:
                        # Fall back to full text if no specific pattern found
                        monthly_sales = text
                    break
        except Exception:
            pass

        # ── Coupon ─────────────────────────────────────────────────────────────
        has_coupon = False
        coupon_text = None
        try:
            # Priority 1: look for actual discount amounts like "Save 8%" or "25% off"
            # Only check the element's own text, not children (to avoid page-wide text dumps)
            discount_pattern = re.compile(r"^Save\s*\d+%$|^Save\s*\d+\s*$", re.I)
            for el in soup.find_all(["span", "label", "div"]):
                text = el.get_text(strip=True)
                if discount_pattern.match(text):
                    has_coupon = True
                    coupon_text = text
                    break

            # Priority 2: coupon badge text like "5% off" (short, only % and off)
            if not has_coupon:
                pct_pattern = re.compile(r"^\d+%\s*off$")
                for el in soup.find_all(["span", "label"]):
                    text = el.get_text(strip=True)
                    if pct_pattern.match(text):
                        has_coupon = True
                        coupon_text = text
                        break

            # Priority 3: look for "with coupon" in a reasonable context
            # (skip if coupon_text is huge - that means we grabbed page text)
            if not has_coupon:
                coupon_el = soup.find(
                    ["span", "div"],
                    string=re.compile(r"with coupon", re.I)
                )
                if coupon_el:
                    txt = coupon_el.get_text(strip=True)
                    if txt and len(txt) < 50 and len(txt) > 2:
                        has_coupon = True
                        coupon_text = None  # exists but no specific amount
        except Exception:
            pass

        # ── Size & Weight ──────────────────────────────────────────────────────
        product_size = None
        product_weight = None

        def _extract_size_weight(table_or_div) -> None:
            nonlocal product_size, product_weight
            for row in table_or_div.find_all("tr"):
                header = row.find("th")
                value = row.find("td")
                if header and value:
                    h_text = header.get_text(strip=True).lower()
                    v_text = value.get_text(strip=True)
                    if not product_size and ("size" in h_text or "dimensions" in h_text or "item dimensions" in h_text):
                        product_size = v_text
                    if not product_weight and ("weight" in h_text or "item weight" in h_text):
                        product_weight = v_text

        # Try prodDetails (modern Amazon layout)
        try:
            prod_details = soup.find("div", {"id": "prodDetails"})
            if prod_details:
                _extract_size_weight(prod_details)
        except Exception:
            pass

        # Try tech specs table (older layout)
        if not product_size or not product_weight:
            try:
                tech_spec = soup.find("table", {"id": "productDetails_techSpec_section_1"})
                if tech_spec:
                    _extract_size_weight(tech_spec)
            except Exception:
                pass

        # Try detail bullets (alternate layout)
        if not product_size or not product_weight:
            try:
                detail_bullets = soup.find(
                    "div", {"id": re.compile(r"productDetails_detailBullets", re.I)}
                )
                if detail_bullets:
                    text = detail_bullets.get_text(strip=True)
                    for line in text.split("\n"):
                        ll = line.lower()
                        if ("size" in ll or "dimensions" in ll or "item weight" in ll) and ":" in line:
                            if not product_size and ("size" in ll or "dimensions" in ll):
                                product_size = line.split(":", 1)[1].strip()
                            if not product_weight and "weight" in ll:
                                product_weight = line.split(":", 1)[1].strip()
            except Exception:
                pass

        # ── Bullet Points ────────────────────────────────────────────────────────
        bullet_points = []
        try:
            bullets_container = soup.find("div", {"id": "feature-bullets"})
            if bullets_container:
                for li in bullets_container.find_all("li"):
                    text = li.get_text(strip=True)
                    if text and len(text) > 5 and "feature" not in text[:10].lower():
                        bullet_points.append(text)
        except Exception:
            pass

        if not bullet_points:
            try:
                for ul in soup.find_all("ul", {"class": re.compile(r"a-vertical|a-unordered")}):
                    for li in ul.find_all("li"):
                        text = li.get_text(strip=True)
                        if text and len(text) > 10 and len(bullet_points) < 5:
                            bullet_points.append(text)
            except Exception:
                pass

        bullet_points = [
            b for b in bullet_points
            if len(b) > 5
            and "image unavailable" not in b.lower()
            and "image not available" not in b.lower()
            and "see more" not in b.lower()
            and "video" not in b.lower()[:20]
        ][:5]

        # ── Sub-category name & rank ───────────────────────────────────────────
        sub_category_name = None
        sub_category_rank = None

        # Breadcrumb: Home > Category > SubCategory > Leaf
        # Take second-to-last link as sub_category (last is usually a leaf like "Tools")
        try:
            breadcrumbs = soup.find("div", {"id": "wayfinding-breadcrumbs_feature_div"})
            if breadcrumbs:
                links = breadcrumbs.find_all("a")
                if links:
                    sub_category_name = links[-2].get_text(strip=True) if len(links) >= 2 else links[-1].get_text(strip=True)
        except Exception:
            pass

        # Fallback: try desktop-breadcrumbs
        if not sub_category_name:
            try:
                breadcrumbs = soup.find("div", {"id": "desktop-breadcrumbs_feature_div"})
                if breadcrumbs:
                    links = breadcrumbs.find_all("a")
                    if links:
                        sub_category_name = links[-2].get_text(strip=True) if len(links) >= 2 else links[-1].get_text(strip=True)
            except Exception:
                pass

        # Best sellers rank from prodDetails table (modern layout)
        try:
            prod_details = soup.find("div", {"id": "prodDetails"})
            if prod_details:
                rank_lines = []
                for row in prod_details.find_all("tr"):
                    h = row.find("th")
                    v = row.find("td")
                    if h and v:
                        h_text = h.get_text(strip=True)
                        v_text = v.get_text(strip=True)
                        if "best sellers rank" in h_text.lower() or "rank" in h_text.lower():
                            rank_lines.append(v_text)
                if rank_lines:
                    sub_category_rank = rank_lines[0][:300]
        except Exception:
            pass

        # Fallback: old salesRank div
        if not sub_category_rank:
            try:
                bsr = soup.find("div", {"id": "salesRank"})
                if bsr:
                    text = bsr.get_text(strip=True)
                    if "#" in text:
                        sub_category_rank = text[:300]
                        if not sub_category_name:
                            for line in text.split("\n"):
                                if "#" in line and len(line) < 150:
                                    sub_category_name = line.strip()
                                    break
            except Exception:
                pass

        # ── A+ Content ──────────────────────────────────────────────────────────
        has_a_plus = bool(soup.find(["div", "section"], {"id": re.compile(r"aplus")}))

        # ── Rating & Review Count from prodDetails ──────────────────────────────
        rating = None
        review_count = None
        try:
            prod_details = soup.find("div", {"id": "prodDetails"})
            if prod_details:
                for row in prod_details.find_all("tr"):
                    h = row.find("th")
                    v = row.find("td")
                    if h and v:
                        h_text = h.get_text(strip=True)
                        v_text = v.get_text(strip=True)
                        if "customer reviews" in h_text.lower() or "rating" in h_text.lower():
                            # Value looks like "4.24.2 out of 5 stars(80)"
                            match = re.search(r"(\d\.\d)\s*out of 5 stars\s*\((\d+(?:,\d+)*)\)", v_text)
                            if match:
                                rating = match.group(1)
                                review_count = match.group(2).replace(",", "")
                            elif not rating:
                                # Try just the number
                                rm = re.search(r"(\d\.\d)\s*out of 5 stars", v_text)
                                if rm:
                                    rating = rm.group(1)
        except Exception:
            pass

        # ── Reviews ─────────────────────────────────────────────────────────────
        # Reviews are in <li data-hook="review"> on the main product page
        all_reviews: list[dict] = []
        try:
            review_blocks = soup.find_all("li", {"data-hook": "review"})
            for block in review_blocks:
                # Rating: try i[data-hook="review-star-rating"] first, then fallback
                rating_val = None
                rating_el = block.find("i", {"data-hook": "review-star-rating"})
                if rating_el:
                    rating_val = rating_el.get("aria-label") or rating_el.get_text(strip=True)
                if not rating_val:
                    rating_el = block.find("i", class_=re.compile(r"a-icon-star|a-star", re.I))
                    if rating_el:
                        rating_val = rating_el.get("aria-label") or rating_el.get_text(strip=True)

                # Title (may contain star rating text like "1.0 out of 5 stars")
                title_el = block.find("a", {"data-hook": "review-title"})
                title_text = title_el.get_text(strip=True) if title_el else None

                # Body: prefer review-collapsed over review-body (expanded text)
                text_el = block.find("div", {"data-hook": "review-collapsed"})
                if not text_el:
                    text_el = block.find("span", {"data-hook": "review-body"})
                text = text_el.get_text(separator=" ", strip=True) if text_el else None
                # Clean "Read more" text
                if text:
                    text = re.sub(r"\s+", " ", text)
                    text = text.replace("Read more", "").strip()

                if text:
                    # Extract star number from rating string like "1.0 out of 5 stars"
                    star_num: float = 0.0
                    if rating_val:
                        m = re.search(r"(\d+\.?\d*)\s*out of 5 stars", rating_val)
                        if m:
                            star_num = float(m.group(1))
                    elif title_text:
                        m = re.search(r"(\d+\.?\d*)\s*out of 5 stars", title_text)
                        if m:
                            star_num = float(m.group(1))
                            rating_val = title_text  # use full title as rating

                    all_reviews.append({
                        "rating": rating_val,
                        "star_num": star_num,
                        "text": text[:500],
                        "title": title_text[:100] if title_text else None,
                    })
        except Exception:
            pass

        # Prioritize low-star reviews (< 3 stars), fill with lowest available
        low_star_reviews = sorted([r for r in all_reviews if r.get("star_num", 0) < 3],
                                  key=lambda r: r.get("star_num", 0))
        if low_star_reviews:
            reviews = [{"rating": r["rating"], "text": r["text"]} for r in low_star_reviews[:5]]
        else:
            # No low-star reviews; sort all by star_num ascending
            sorted_reviews = sorted(all_reviews, key=lambda r: r.get("star_num", 0))
            reviews = [{"rating": r["rating"], "text": r["text"]} for r in sorted_reviews[:5]]

        if reviews:
            self._logger.info(f"  [Reviews] Got {len(reviews)} reviews (low-star priority)")

        self._logger.info(
            f"  ASIN {asin}: brand={brand}, bought={monthly_sales}, "
            f"coupon={has_coupon}, bullets={len(bullet_points)}, "
            f"reviews={len(reviews)}, A+={has_a_plus}"
        )

        return DetailProduct(
            asin_code=asin,
            brand=brand,
            bought_in_past_month=monthly_sales,
            has_coupon=has_coupon,
            coupon_text=coupon_text,
            product_size=product_size,
            product_weight=product_weight,
            bullet_points=bullet_points,
            sub_category_name=sub_category_name,
            sub_category_rank=sub_category_rank,
            has_a_plus=has_a_plus,
            rating=rating,
            review_count=review_count,
            reviews=reviews,
        )

    def scrape(self, url: str, asin: str) -> DetailProduct:
        """
        Scrape a single product detail page using HTTP requests.
        Applies random delay before fetching.
        """
        clean_url = f"https://www.amazon.com/dp/{asin}"
        if self._postal_code:
            clean_url = f"{clean_url}?location={self._postal_code}"

        random_delay(8.0, 15.0)

        headers = self._get_headers()
        self._logger.info(f"[HTTP] Fetching ASIN {asin}: {clean_url}")

        try:
            response = self._session.get(
                clean_url,
                headers=headers,
                timeout=20,
                allow_redirects=True,
            )
        except requests.RequestException as e:
            self._logger.warning(f"[HTTP] Request failed for ASIN {asin}: {e}")
            raise

        if response.status_code != 200:
            self._logger.warning(
                f"[HTTP] Non-200 status for ASIN {asin}: {response.status_code}"
            )
            raise Exception(f"HTTP {response.status_code}")

        return self._parse(response.text, asin)
