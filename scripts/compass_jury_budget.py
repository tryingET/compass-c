"""Fixed AK5673 conservative reservations, not invoices or account-spend proof."""

from decimal import Decimal

ALLOWANCE = Decimal("10")
PRIOR = Decimal("2.351733925") + Decimal("5.512782")
MAX_CALLS = 24
MAX_TOKENS = 8192
REQUEST_LIMIT = 160_000
RESPONSE_LIMIT = 2_000_000
# Bound escaped juror strings before they can enter adjudication prompts.
JUDGMENT_LIMIT = 12_000


def reservation(message_bytes):
    if type(message_bytes) is not int or not 0 <= message_bytes <= REQUEST_LIMIT:
        raise ValueError("message byte bound")
    return (
        Decimal(message_bytes + 4096) * Decimal("1.4") + Decimal(MAX_TOKENS) * Decimal("4.4")
    ) / Decimal(1_000_000)


class Budget:
    def __init__(self):
        self.total = PRIOR
        self.calls = 0

    @property
    def remaining(self):
        return ALLOWANCE - self.total

    def reserve(self, message_bytes):
        amount = reservation(message_bytes)
        if self.calls >= MAX_CALLS or amount > self.remaining:
            raise ValueError("pilot reservation cap reached")
        self.total += amount
        self.calls += 1
        return amount
