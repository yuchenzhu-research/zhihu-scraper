# Python Refactoring Reference

Pythonic refactoring patterns using dataclasses, protocols, comprehensions, and modern type hints. Lean on type checkers (mypy/pyright) and characterization tests as your safety net.

---

## Extract and Inline

```python
# BEFORE: long method with inline comments explaining sections
def process_order(order: dict) -> dict:
    if not order.get("items"):
        raise ValueError("No items")
    for item in order["items"]:
        if item["quantity"] <= 0:
            raise ValueError(f"Bad quantity: {item['quantity']}")
    total = sum(i["price"] * i["quantity"] for i in order["items"])
    if total > 1000:
        total *= 0.9
    return {"items": order["items"], "total": total, "status": "pending"}

# AFTER: extracted functions named after intent
def process_order(order: dict) -> dict:
    validate_items(order["items"])
    total = calculate_total(order["items"])
    return {"items": order["items"], "total": total, "status": "pending"}

def validate_items(items: list[dict]) -> None:
    if not items:
        raise ValueError("No items")
    for item in items:
        if item["quantity"] <= 0:
            raise ValueError(f"Bad quantity: {item['quantity']}")

def calculate_total(items: list[dict]) -> float:
    total = sum(i["price"] * i["quantity"] for i in items)
    return total * 0.9 if total > 1000 else total
```

## Move and Reorganize

```python
# BEFORE: feature envy — method only touches Cart's data
class PricingService:
    def cart_total(self, cart: Cart) -> float:
        return sum(i.price * i.quantity for i in cart.items)

# AFTER: move method to where the data lives
class Cart:
    def __init__(self) -> None:
        self.items: list[CartItem] = []
    def total(self) -> float:
        return sum(i.price * i.quantity for i in self.items)
```

## Simplify Conditionals

```python
# BEFORE: nested conditionals obscure the logic
def calculate_fee(account: Account) -> float:
    if account.is_active:
        if account.years_active > 5:
            if account.balance > 10000:
                return 0.0
            else:
                return 10.0
        else:
            return 25.0
    else:
        return 50.0

# AFTER: guard clauses flatten the structure
def calculate_fee(account: Account) -> float:
    if not account.is_active:     return 50.0  # guard: inactive
    if account.years_active <= 5: return 25.0  # guard: newer
    if account.balance <= 10000:  return 10.0  # guard: lower balance
    return 0.0                                 # main path
```

## Refactoring Data

```python
from dataclasses import dataclass

# BEFORE: primitive obsession — raw strings carry domain meaning
def send_notification(email: str, phone: str, msg: str) -> None:
    if "@" not in email: raise ValueError("Invalid email")
    if not phone.startswith("+"): raise ValueError("Invalid phone")

# AFTER: value objects validate on creation, trusted everywhere after
@dataclass(frozen=True)
class Email:
    value: str
    def __post_init__(self) -> None:
        if "@" not in self.value:
            raise ValueError(f"Invalid email: {self.value!r}")

@dataclass(frozen=True)
class PhoneNumber:
    value: str
    def __post_init__(self) -> None:
        if not self.value.startswith("+"):
            raise ValueError(f"Invalid phone: {self.value!r}")

def send_notification(email: Email, phone: PhoneNumber, msg: str) -> None:
    ...  # No validation needed — types guarantee correctness
```

## Dealing with Inheritance

```python
from typing import Protocol

# BEFORE: inheritance for code reuse — OrderService is not a logger
class FileLogger:
    def log(self, msg: str) -> None:
        with open("app.log", "a") as f:
            f.write(msg + "\n")

class OrderService(FileLogger):
    def place_order(self, order: Order) -> None:
        self.log(f"Placing order {order.id}")

# AFTER: delegation via protocol
class Logger(Protocol):
    def log(self, msg: str) -> None: ...

class OrderService:
    def __init__(self, logger: Logger) -> None:
        self._logger = logger  # composition: injected dependency
    def place_order(self, order: Order) -> None:
        self._logger.log(f"Placing order {order.id}")
```

## Breaking Dependencies in Legacy Code

```python
from typing import Protocol
from datetime import datetime

# BEFORE: untestable — hard-coded clock and database
class ReportGenerator:
    def generate(self) -> Report:
        data = db.query("SELECT * FROM sales WHERE date = ?", datetime.now())
        return Report(data=data)

# AFTER: parameterize constructor — tests inject fakes
class Clock(Protocol):
    def now(self) -> datetime: ...

class SalesRepository(Protocol):
    def sales_for_date(self, date: datetime) -> list[dict]: ...

class ReportGenerator:
    def __init__(self, clock: Clock | None = None, repo: SalesRepository | None = None) -> None:
        self._clock = clock or _SystemClock()
        self._repo = repo or _RealSalesRepo()

    def generate(self) -> Report:
        return Report(data=self._repo.sales_for_date(self._clock.now()))
```
