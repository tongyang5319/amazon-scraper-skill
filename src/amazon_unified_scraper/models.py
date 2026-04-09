"""
    Pydantic models for the unified Amazon scraper.
"""

from pydantic import BaseModel


class ListProduct(BaseModel):
    """Product data scraped from the list page (New Releases / Best Sellers)."""
    list_rank: int
    title: str
    url: str
    asin_code: str
    image_url: str
    price: str | None = None
    rating: str | None = None
    review_count: str | None = None


class DetailProduct(BaseModel):
    """Full product data enriched from the detail page."""
    asin_code: str
    brand: str | None = None
    bought_in_past_month: str | None = None
    has_coupon: bool = False
    coupon_text: str | None = None
    product_size: str | None = None
    product_weight: str | None = None
    bullet_points: list[str] = []
    sub_category_name: str | None = None
    sub_category_rank: str | None = None
    has_a_plus: bool = False
    rating: str | None = None
    review_count: str | None = None
    reviews: list[dict] = []  # [{"rating": "4.5", "text": "..."}, ...]


class EnrichedProduct(BaseModel):
    """Merged product: list page data + detail page data."""
    # From list page
    list_rank: int
    title: str
    url: str
    asin_code: str
    image_url: str
    price: str | None = None
    rating: str | None = None
    review_count: str | None = None
    # From detail page
    brand: str | None = None
    bought_in_past_month: str | None = None
    has_coupon: bool = False
    coupon_text: str | None = None
    product_size: str | None = None
    product_weight: str | None = None
    sub_category_name: str | None = None
    sub_category_rank: str | None = None
    has_a_plus: bool = False
    # Bullet points (individual columns)
    bullet_point_1: str | None = None
    bullet_point_2: str | None = None
    bullet_point_3: str | None = None
    bullet_point_4: str | None = None
    bullet_point_5: str | None = None
    # Reviews (individual columns with rating)
    review_1_rating: str | None = None
    review_1_text: str | None = None
    review_2_rating: str | None = None
    review_2_text: str | None = None
    review_3_rating: str | None = None
    review_3_text: str | None = None
    review_4_rating: str | None = None
    review_4_text: str | None = None
    review_5_rating: str | None = None
    review_5_text: str | None = None
