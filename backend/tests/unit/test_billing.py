from decimal import Decimal

import pytest

from app.api.v1.billing import calculate_invoice_total
from app.utils.common import ApiError, MAX_MONEY


def test_invoice_total_uses_quantity_and_decimal_prices():
    prices = {1: Decimal("300.00"), 2: Decimal("250.00")}
    assert calculate_invoice_total(prices, {1: 1, 2: 2}) == Decimal("800.00")


def test_empty_invoice_is_rejected():
    with pytest.raises(ApiError, match="at least one invoice item") as error:
        calculate_invoice_total({}, {})
    assert error.value.status == 422


def test_invoice_total_over_the_storage_limit_is_rejected():
    with pytest.raises(ApiError, match="maximum allowed amount") as error:
        calculate_invoice_total({1: MAX_MONEY}, {1: 2})
    assert error.value.status == 422
