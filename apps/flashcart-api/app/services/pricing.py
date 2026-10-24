"""Server-side pricing. The only place totals are computed — client-supplied prices are never used."""

FREE_SHIPPING_THRESHOLD_PAISE = 99_900  # ₹999

SHIPPING_FEES_PAISE = {
    "economic": 0,
    "regular": 4_900,
    "next_day": 14_900,
    "instant": 29_900,
}


def shipping_fee(method: str, subtotal_paise: int) -> int:
    if subtotal_paise == 0:
        return 0
    if method == "regular" and subtotal_paise >= FREE_SHIPPING_THRESHOLD_PAISE:
        return 0
    return SHIPPING_FEES_PAISE[method]
