"""
    List page scraper for Amazon New Releases / Best Sellers pages.
    Supports both the grid format (zg-item-immersion) and standard search result format.
"""

import logging
import os
import time
from typing import Optional

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement

from amazon_unified_scraper.models import ListProduct
from amazon_unified_scraper.utils import random_user_agent, random_jitter


class DriverInitError(BaseException):
    message = "Cannot initialize Chrome webdriver."


class ListScraper:
    """
    Scrapes product list pages (New Releases, Best Sellers, search results).
    Detects page type automatically and uses appropriate selectors.
    """

    # Selector sets for different page types
    # ── New Releases / Best Sellers (zg-grid format) ──
    NR_PRODUCT = "div[data-asin]"
    NR_RANK = "span.zg-bdg-text"
    NR_TITLE = "div[class*='p13n-sc-css-line-clamp']"
    NR_URL = "a[href*='/dp/']"
    NR_IMAGE = "img.p13n-sc-dynamic-image, img.a-dynamic-image"
    NR_PRICE = "span.p13n-sc-price, span._cDEzb_p13n-sc-price_3mJ9Z, span.a-color-price"
    NR_RATING = "a[aria-label*='out of 5 stars']"
    NR_NEXT = "nav[aria-label='pagination'] ul.a-pagination li.a-last a"

    # ── Standard search result pages ──
    STD_PRODUCT = "//div[@data-component-type='s-search-result']"
    STD_TITLE = ".//h2/a/span[@class='a-size-medium a-color-base a-text-normal'] | .//h2/a/span"
    STD_URL = ".//h2/a"
    STD_IMAGE = ".//img"
    STD_PRICE_W = ".//span[@class='a-price']//span[@class='a-price-whole']"
    STD_PRICE_F = ".//span[@class='a-price']//span[@class='a-price-fraction']"
    STD_RATING = ".//i[contains(@class,'a-icon-star')]//span[@class='a-icon-alt']"
    STD_REVIEWS = ".//span[contains(@aria-label,' rated')]"
    STD_NEXT = "//a[contains(@class,'s-pagination-next')]"

    def __init__(self, postal_code: str | None = None, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger if logger else logging.getLogger(__name__)
        self._postal_code = postal_code

    def _append_zipcode(self, url: str) -> str:
        """Append postal code to URL for country/region targeting.
        Amazon uses location=ZIPCODE to show region-specific content/pricing.
        """
        if not self._postal_code:
            return url
        # Remove any existing location/zipcode params to avoid duplicates
        import re
        url = re.sub(r"[?&]location=\w+", "", url)
        url = re.sub(r"[?&]zipcode=\w+", "", url)
        url = re.sub(r"[?&]th=\d+", "", url)
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}location={self._postal_code}"

    def _init_driver(self) -> webdriver.Chrome:
        """Create a Chrome webdriver with anti-detection settings."""
        import platform
        system = platform.system().lower()
        if system == "darwin":
            arch = platform.machine()
            driver_name = "chromedriver-mac-arm64" if "arm" in arch else "chromedriver-mac-x64"
            driver_exe = driver_name
        elif system == "windows":
            driver_exe = "chromedriver.exe"
            driver_name = "chromedriver-win64"
        else:
            driver_exe = "chromedriver"
            driver_name = "chromedriver-linux64"
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        chromedriver_path = os.path.join(project_root, "drivers", driver_name, driver_exe)

        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(f"--user-agent={random_user_agent()}")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        # Disable images for speed (less detection surface)
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.managed_default_content_settings.stylesheets": 2,
        }
        options.add_experimental_option("prefs", prefs)

        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)

        # Clear webdriver flag via CDP (Chrome DevTools Protocol)
        try:
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                    window.chrome = {runtime: {}};
                """
            })
        except Exception:
            pass

        return driver

    def _detect_page_type(self, driver: webdriver.Chrome) -> str:
        """Detect whether this is a New Releases or standard search page."""
        if driver.find_elements(By.CSS_SELECTOR, self.NR_PRODUCT):
            return "new_releases"
        if driver.find_elements(By.XPATH, self.STD_PRODUCT):
            return "standard"
        return "unknown"

    def _scroll_to_load_all(self, driver: webdriver.Chrome, page_type: str) -> int:
        """
        Scroll down a New Releases page repeatedly to trigger lazy-loading.
        Amazon's zg-grid only renders ~10 items at a time; scrolling loads more.
        Returns the number of scroll actions performed.
        """
        if page_type != "new_releases":
            return 0

        scroll_count = 0
        max_scrolls = 15  # safety limit
        last_count = 0

        for _ in range(max_scrolls):
            # Count current visible products
            elements = driver.find_elements(By.CSS_SELECTOR, self.NR_PRODUCT)
            current_count = len([e for e in elements if e.get_attribute("data-asin")])

            if current_count > last_count:
                self._logger.debug(f"    Scroll #{scroll_count+1}: {current_count} products loaded")
                last_count = current_count

            # Scroll to bottom of the grid
            try:
                driver.execute_script(
                    "window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});"
                )
                time.sleep(1.5)
                # After scrolling, check if more products appeared
                new_elements = driver.find_elements(By.CSS_SELECTOR, self.NR_PRODUCT)
                new_count = len([e for e in new_elements if e.get_attribute("data-asin")])
                if new_count <= current_count:
                    # No new products loaded, try a smaller scroll step
                    driver.execute_script(
                        "window.scrollBy(0, 800);"
                    )
                    time.sleep(1)
                    new_elements = driver.find_elements(By.CSS_SELECTOR, self.NR_PRODUCT)
                    new_count = len([e for e in new_elements if e.get_attribute("data-asin")])
                    if new_count <= current_count:
                        scroll_count += 1
                        break
                scroll_count += 1
            except Exception:
                break

        return scroll_count

    def _parse_nr_product(self, el: WebElement, rank: int) -> Optional[ListProduct]:
        """Parse a New Releases / Best Sellers product card."""
        asin = el.get_attribute("data-asin")

        # Title
        title = None
        try:
            title_el = el.find_element(By.CSS_SELECTOR, self.NR_TITLE)
            title = title_el.text.strip()
        except NoSuchElementException:
            pass

        # URL: find non-aria-hidden link
        url = None
        try:
            links = el.find_elements(By.CSS_SELECTOR, "a[href*='/dp/']")
            for link in links:
                if link.get_attribute("aria-hidden") != "true":
                    url = link.get_attribute("href")
                    break
        except NoSuchElementException:
            pass

        # Image
        image_url = None
        try:
            img_el = el.find_element(By.CSS_SELECTOR, "img.p13n-sc-dynamic-image")
            image_url = img_el.get_attribute("src")
        except NoSuchElementException:
            try:
                img_el = el.find_element(By.CSS_SELECTOR, "img.a-dynamic-image")
                image_url = img_el.get_attribute("src")
            except NoSuchElementException:
                pass

        # Price
        price = None
        for sel in ["span.p13n-sc-price", "span._cDEzb_p13n-sc-price_3mJ9Z", "span.a-color-price"]:
            try:
                price_el = el.find_element(By.CSS_SELECTOR, sel)
                txt = price_el.text.strip()
                if txt:
                    price = txt.replace("$", "").replace(",", "")
                    break
            except NoSuchElementException:
                pass

        # Rating & review count from aria-label
        rating = None
        review_count = None
        try:
            rating_link = el.find_element(By.CSS_SELECTOR, "a[aria-label*='out of 5 stars']")
            aria_label = rating_link.get_attribute("aria-label") or ""
            if "out of 5 stars" in aria_label:
                parts = aria_label.split(",")
                if len(parts) >= 1:
                    rating = parts[0].replace("out of 5 stars", "").strip()
                if len(parts) >= 2:
                    review_count = parts[1].replace("ratings", "").replace("rating", "").strip().replace(",", "")
        except NoSuchElementException:
            pass

        if not title or not asin:
            return None

        return ListProduct(
            list_rank=rank,
            title=title,
            url=url,
            asin_code=asin,
            image_url=image_url,
            price=price,
            rating=rating,
            review_count=review_count,
        )

    def _parse_std_product(self, el: WebElement, rank: int) -> Optional[ListProduct]:
        """Parse a standard search result product."""
        asin = el.get_attribute("data-asin")

        title = None
        try:
            title_el = el.find_element(By.XPATH, self.STD_TITLE)
            title = title_el.text.strip()
        except NoSuchElementException:
            pass

        url = None
        try:
            url_el = el.find_element(By.XPATH, self.STD_URL)
            url = url_el.get_attribute("href")
        except NoSuchElementException:
            pass

        image_url = None
        try:
            img_el = el.find_element(By.XPATH, self.STD_IMAGE)
            image_url = img_el.get_attribute("src")
        except NoSuchElementException:
            pass

        price = None
        try:
            pw_el = el.find_element(By.XPATH, self.STD_PRICE_W)
            pf_el = el.find_element(By.XPATH, self.STD_PRICE_F)
            price = f"{pw_el.text.replace(',', '')}.{pf_el.text}"
        except NoSuchElementException:
            pass

        rating = None
        try:
            rt_el = el.find_element(By.XPATH, self.STD_RATING)
            rating = rt_el.text.strip()
        except NoSuchElementException:
            pass

        review_count = None
        try:
            rv_el = el.find_element(By.XPATH, self.STD_REVIEWS)
            review_count = rv_el.text.strip().replace(",", "")
        except NoSuchElementException:
            pass

        if not title or not asin:
            return None

        return ListProduct(
            list_rank=rank,
            title=title,
            url=url,
            asin_code=asin,
            image_url=image_url,
            price=price,
            rating=rating,
            review_count=review_count,
        )

    def scrape_list_page(self, url: str, max_products: int = 100) -> tuple[list[ListProduct], str]:
        """
        Scrape up to max_products from a list page.
        Returns (list of ListProduct, sub_category_name extracted from page).

        Uses random User-Agent per page load for anti-detection.
        """
        driver = self._init_driver()
        sub_category_name = "unknown"

        try:
            products: list[ListProduct] = []
            current_page = 1
            page_url = url

            while len(products) < max_products:
                self._logger.info(f"  [Page {current_page}] Fetching...")
                target_url = page_url
                if self._postal_code:
                    target_url = self._append_zipcode(page_url)
                driver.get(target_url)
                time.sleep(4)

                page_type = self._detect_page_type(driver)
                self._logger.info(f"  [Page {current_page}] Type: {page_type}")

                if page_type == "unknown":
                    break

                # Extract sub-category name from page title
                if sub_category_name == "unknown":
                    try:
                        title_text = driver.title
                        # Title format: "Amazon.com: CategoryName - New Releases"
                        if ":" in title_text:
                            parts = title_text.split(":")
                            if len(parts) >= 2:
                                sub_category_name = parts[1].replace("New Releases", "").replace("Best Sellers", "").strip()
                        if not sub_category_name or sub_category_name == "unknown":
                            sub_category_name = driver.find_element(By.CSS_SELECTOR, "h1").text.strip()
                    except Exception:
                        pass

                if page_type == "new_releases":
                    elements = driver.find_elements(By.CSS_SELECTOR, self.NR_PRODUCT)
                else:
                    elements = driver.find_elements(By.XPATH, self.STD_PRODUCT)

                # For new_releases, scroll to trigger lazy-loading (zg-grid renders ~10 at a time)
                if page_type == "new_releases":
                    scrolls = self._scroll_to_load_all(driver, page_type)
                    if scrolls > 0:
                        self._logger.info(f"  [Page {current_page}] Scrolled {scrolls}x to load lazy products")
                    # Re-fetch after scrolling
                    elements = driver.find_elements(By.CSS_SELECTOR, self.NR_PRODUCT)

                if not elements:
                    self._logger.warning(f"  [Page {current_page}] No products found. Stopping.")
                    break

                rank_start = len(products) + 1
                for idx, el in enumerate(elements):
                    if len(products) >= max_products:
                        break
                    rank = rank_start + idx
                    try:
                        parsed = (
                            self._parse_nr_product(el, rank)
                            if page_type == "new_releases"
                            else self._parse_std_product(el, rank)
                        )
                        if parsed:
                            products.append(parsed)
                            self._logger.debug(f"    #{rank} {parsed.title[:40]}")
                    except Exception as e:
                        self._logger.warning(f"    Error parsing product #{rank}: {e}")
                        continue

                if len(products) >= max_products:
                    break

                # Pagination
                next_btn = None
                if page_type == "new_releases":
                    try:
                        next_btn = driver.find_element(By.CSS_SELECTOR, self.NR_NEXT)
                    except NoSuchElementException:
                        pass
                else:
                    try:
                        next_btn = driver.find_element(By.XPATH, self.STD_NEXT)
                    except NoSuchElementException:
                        pass

                if next_btn:
                    href = next_btn.get_attribute("href")
                    if href:
                        page_url = href
                        current_page += 1
                        random_jitter(0.5)
                    else:
                        break
                else:
                    break

            self._logger.info(f"  Total list products: {len(products)}")
            return products, sub_category_name

        finally:
            driver.quit()
