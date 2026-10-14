"""The running system for the whole series: five seller stubs and the request budget.

Every page uses these exact numbers. Nothing here talks to a real network.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Seller:
    name: str
    latency_ms: int  # how long the seller takes to answer
    price: int  # the offer it returns for any item


@dataclass(frozen=True)
class Offer:
    seller: str
    price: int


class SellerError(Exception):
    """Raised by a seller in fault mode instead of answering."""


SELLERS = (
    Seller("seller-a", 80, 1249),
    Seller("seller-b", 120, 1199),
    Seller("seller-c", 150, 1229),
    Seller("seller-d", 200, 1215),
    Seller("seller-e", 900, 1149),
)
BUDGET_MS = 250  # the gateway must answer within this


def cheapest(offers):
    """The lowest-priced offer, or None if no seller answered."""
    return min(offers, key=lambda offer: offer.price, default=None)
