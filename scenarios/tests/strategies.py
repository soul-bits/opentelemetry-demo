"""Hypothesis strategies for property-based testing of scenarios.

Provides randomized inputs for scenario activation/verification tests:
- ``randomized_place_order``: composite strategy for checkout flow
- ``SCENARIOS``: list of valid scenario IDs
"""

from __future__ import annotations

from hypothesis import strategies as st
import uuid


# Valid scenario identifiers
SCENARIOS = ["case1", "case2", "case3"]

# Product SKUs from src/load-generator/locustfile.py (astronomy shop)
PRODUCT_SKUS = [
    "OLJCESPC7Z",
    "9SCIE7Z8XX",
    "6E92ZMYYFZ",
    "0PUK6V6EV0",
    "LS4PSXUNUM",
    "L9ECAV7KIM",
    "HQTGWRL7D7",
    "FCBZT47FXV",
    "66VBJGIE7N",
    "1YMWWN1N4O",
]

# Valid currency codes
CURRENCIES = ["USD", "EUR", "CAD"]

# Quantity range
QUANTITIES = [1, 2, 3, 4, 5, 10]


@st.composite
def randomized_place_order(draw):
    """Generate a randomized checkout order (product ID, quantity, currency, user ID).

    Returns:
        dict with keys: product_id, quantity, currency, user_id
    """
    product_id = draw(st.sampled_from(PRODUCT_SKUS))
    quantity = draw(st.sampled_from(QUANTITIES))
    currency = draw(st.sampled_from(CURRENCIES))
    user_id = str(draw(st.uuids()))

    return {
        "product_id": product_id,
        "quantity": quantity,
        "currency": currency,
        "user_id": user_id,
    }
