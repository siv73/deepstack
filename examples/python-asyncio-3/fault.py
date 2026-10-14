"""Fault mode: seller-c raises at 150 ms. On the toy loop that ends the whole request."""

from gateway_v1 import compare, report
from sellers import BUDGET_MS

try:
    report(*compare("kettle-1l", budget_ms=BUDGET_MS, faulty={"seller-c"}))
except Exception as error:
    print(f"request failed: {type(error).__name__}: {error}")
