# Python Defensive Programming Reference

Idiomatic Python patterns for each defensive principle. Python lacks compile-time enforcement for many of these, so the patterns lean on type hints, runtime checks, conventions, and stdlib features that provide guardrails.

---

## Immutability

```python
from dataclasses import dataclass, field
from typing import Final, Sequence

# Variables: use Final for module-level and class-level constants
MAX_RETRIES: Final = 3
BASE_URL: Final = "https://api.example.com"

# Frozen dataclasses: immutable value objects
@dataclass(frozen=True)
class Coordinate:
    latitude: float
    longitude: float
    # Attempting coord.latitude = 5.0 raises FrozenInstanceError

@dataclass(frozen=True)
class OrderLine:
    product_id: str
    quantity: int
    unit_price: float

# Tuples over lists for fixed collections
ALLOWED_STATUSES = ("pending", "confirmed", "shipped", "delivered")

# frozenset for immutable sets
VALID_ROLES = frozenset({"admin", "editor", "viewer"})

# Parameters: never reassign
def process_order(order: Order) -> Receipt:
    # Don't do: order = transform(order)
    # Do: create new values
    validated = validate(order)
    enriched = enrich(validated)
    return create_receipt(enriched)
```

## Minimal Visibility

```python
class OrderProcessor:
    """Public interface is process() only. Everything else is private."""

    def __init__(self, db: Database, tax_service: TaxService) -> None:
        self._db = db               # private by convention
        self._tax_service = tax_service
        self._retry_count = 0

    def process(self, order: Order) -> OrderResult:
        """Public contract."""
        self._validate(order)
        tax = self._calculate_tax(order)
        return self._persist(order, tax)

    def _validate(self, order: Order) -> None:
        """Private: not part of the contract."""
        ...

    def _calculate_tax(self, order: Order) -> Decimal:
        """Private: implementation detail."""
        ...

    def _persist(self, order: Order, tax: Decimal) -> OrderResult:
        """Private: storage is an internal concern."""
        ...


# Use __all__ to control module exports
__all__ = ["OrderProcessor", "OrderResult"]
# Internal helpers not listed in __all__ are conventionally private


# Use __slots__ to prevent accidental attribute creation
class Config:
    __slots__ = ("host", "port", "timeout")

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
    # config.typo_field = "oops" raises AttributeError


# For truly immutable config, combine frozen dataclass + slots
@dataclass(frozen=True, slots=True)
class AppConfig:
    host: str
    port: int
    timeout_seconds: int
```

## Design by Contract

```python
from typing import assert_never

def calculate_discount(price: float, discount_pct: float) -> float:
    """Calculate discounted price.

    Preconditions:
        price >= 0
        0 <= discount_pct <= 100

    Postconditions:
        result >= 0
        result <= price
    """
    assert price >= 0, f"price must be non-negative, got {price}"
    assert 0 <= discount_pct <= 100, f"discount must be 0-100, got {discount_pct}"

    result = price * (1 - discount_pct / 100)

    assert result >= 0, f"postcondition violated: result {result} is negative"
    assert result <= price, f"postcondition violated: result {result} > price {price}"
    return result


# Class invariants: verify after state changes
class BankAccount:
    def __init__(self, owner: str, initial_balance: float) -> None:
        assert initial_balance >= 0, "Initial balance must be non-negative"
        self._owner = owner
        self._balance = initial_balance

    def _check_invariant(self) -> None:
        assert self._balance >= 0, f"Invariant violated: balance is {self._balance}"

    def withdraw(self, amount: float) -> None:
        assert amount > 0, f"Withdrawal amount must be positive, got {amount}"
        if amount > self._balance:
            raise ValueError(f"Insufficient funds: {amount} > {self._balance}")
        self._balance -= amount
        self._check_invariant()

    @property
    def balance(self) -> float:
        return self._balance
```

## Boundary Validation

```python
from dataclasses import dataclass
from typing import Self

# Parse, don't validate — create validated types at the boundary
@dataclass(frozen=True)
class EmailAddress:
    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        raw = raw.strip()
        if not raw or "@" not in raw:
            raise ValueError(f"Invalid email address: {raw!r}")
        return cls(value=raw)


@dataclass(frozen=True)
class PositiveInt:
    value: int

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError(f"Expected positive integer, got {self.value}")


# At the API boundary: validate and convert to internal types
def handle_create_order(raw_payload: dict) -> OrderResult:
    """Boundary function: validates external input."""
    if "items" not in raw_payload or not isinstance(raw_payload["items"], list):
        raise ValueError("Payload must contain 'items' list")

    items = []
    for raw_item in raw_payload["items"]:
        product_id = ProductId.parse(raw_item["id"])    # validated type
        quantity = PositiveInt(raw_item["quantity"])      # validated type
        items.append(OrderItem(product_id=product_id, quantity=quantity))

    order = Order(items=tuple(items))  # immutable from here inward
    return process_order(order)  # internal code trusts the types
```

## Defensive Copies

```python
from copy import copy
from types import MappingProxyType

class Inventory:
    def __init__(self, items: list[Item]) -> None:
        # Copy on ingress: caller can't mutate our internals
        self._items = list(items)

    @property
    def items(self) -> tuple[Item, ...]:
        # Return immutable view: caller can't modify our list
        return tuple(self._items)

    @property
    def item_count(self) -> int:
        return len(self._items)


class AppSettings:
    def __init__(self, settings: dict[str, str]) -> None:
        self._settings = dict(settings)  # defensive copy

    @property
    def settings(self) -> MappingProxyType:
        # Read-only view of the dict
        return MappingProxyType(self._settings)
```

## Resource Safety

```python
from contextlib import contextmanager
from pathlib import Path

# Context managers for deterministic cleanup
with open("data.csv") as f:
    contents = f.read()
# file is closed here, regardless of exceptions

# Custom context manager
@contextmanager
def database_transaction(db: Database):
    tx = db.begin_transaction()
    try:
        yield tx
        tx.commit()
    except Exception:
        tx.rollback()
        raise

with database_transaction(db) as tx:
    tx.execute("INSERT INTO orders ...")
    # auto-commits on success, auto-rolls-back on exception


# For classes that manage resources
class ConnectionPool:
    def __init__(self, dsn: str, pool_size: int) -> None:
        self._pool = create_pool(dsn, pool_size)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info) -> None:
        self._pool.close()

    def close(self) -> None:
        self._pool.close()
```

## Safe Defaults

```python
from enum import Enum, auto
from typing import assert_never

# Exhaustive matching with assert_never (Python 3.11+)
class OrderStatus(Enum):
    PENDING = auto()
    CONFIRMED = auto()
    SHIPPED = auto()
    DELIVERED = auto()
    CANCELLED = auto()

def next_action(status: OrderStatus) -> str:
    match status:
        case OrderStatus.PENDING:
            return "confirm_payment"
        case OrderStatus.CONFIRMED:
            return "prepare_shipment"
        case OrderStatus.SHIPPED:
            return "track_delivery"
        case OrderStatus.DELIVERED:
            return "request_review"
        case OrderStatus.CANCELLED:
            return "process_refund"
        case _ as unreachable:
            assert_never(unreachable)  # type checker catches missing cases


# Avoid boolean parameters — use enums
class Compression(Enum):
    ENABLED = auto()
    DISABLED = auto()

class Encryption(Enum):
    ENABLED = auto()
    DISABLED = auto()

def write_file(
    path: Path,
    data: bytes,
    compression: Compression,
    encryption: Encryption,
) -> None:
    ...

# Call site reads clearly:
write_file(output_path, payload, Compression.ENABLED, Encryption.DISABLED)


# Type hints: use strict types to prevent misuse
def send_email(
    to: EmailAddress,        # not str
    subject: str,
    body: str,
    reply_to: EmailAddress | None = None,
) -> None:
    ...
```
