# Rust Defensive Programming Reference

Idiomatic Rust patterns for each defensive principle. Rust's ownership model, type system, and compiler enforce many defensive practices at compile time. The patterns here focus on leveraging those guarantees and filling the gaps.

---

## Immutability

```rust
// Variables: immutable by default — this is already Rust's default
let timeout = Duration::from_secs(30);
let user = get_current_user();

// Only add mut when mutation is genuinely needed
let mut total = 0;
for item in &cart.items {
    total += item.price;  // accumulator: justified mutability
}

// Prefer transformations over mutation
let total: u64 = cart.items.iter().map(|item| item.price).sum();

// Struct fields: no pub unless the module contract requires it
pub struct Config {
    host: String,       // private: only accessible within the module
    port: u16,
    timeout: Duration,
}

impl Config {
    // Expose through accessors, not public fields
    pub fn host(&self) -> &str { &self.host }
    pub fn port(&self) -> u16 { self.port }
}

// Use &self (not &mut self) for methods that don't modify state
impl Account {
    pub fn balance(&self) -> f64 { self.balance }
    pub fn name(&self) -> &str { &self.name }
}
```

## Minimal Visibility

```rust
// Module-level: pub(crate) is your friend in large codebases
pub(crate) struct InternalHelper {
    field: String,
}

// Public API: only what the module exposes
pub struct OrderProcessor { /* fields private */ }

impl OrderProcessor {
    // Public: part of the contract
    pub fn process(&self, order: &Order) -> Result<OrderResult, OrderError> {
        self.validate(order)?;
        let tax = self.calculate_tax(order)?;
        self.persist(order, tax)
    }

    // Private: implementation detail
    fn validate(&self, order: &Order) -> Result<(), OrderError> { ... }
    fn calculate_tax(&self, order: &Order) -> Result<Decimal, OrderError> { ... }
    fn persist(&self, order: &Order, tax: Decimal) -> Result<OrderResult, OrderError> { ... }
}

// Re-export only the public contract from lib.rs or mod.rs
pub use order_processor::OrderProcessor;
pub use order_processor::OrderResult;
pub use order_processor::OrderError;
// Internal types remain hidden

// Seal types against external implementation using a private trait bound
mod sealed {
    pub trait Sealed {}
}
pub trait Transport: sealed::Sealed {
    fn send(&self, data: &[u8]) -> Result<(), Error>;
}
// External crates can use Transport but can't implement it
```

## Design by Contract

```rust
// Preconditions: use debug_assert! for internal invariants
pub fn binary_search<T: Ord>(sorted_slice: &[T], target: &T) -> Option<usize> {
    debug_assert!(
        sorted_slice.windows(2).all(|w| w[0] <= w[1]),
        "binary_search requires a sorted slice"
    );
    // ... implementation
}

// For public APIs: return Result or use newtypes instead of asserting
pub fn divide(numerator: f64, denominator: NonZeroF64) -> f64 {
    // Can't even call this with zero — the type prevents it
    numerator / denominator.get()
}

// Class invariants via the type system
pub struct SortedVec<T: Ord> {
    inner: Vec<T>,  // invariant: always sorted
}

impl<T: Ord> SortedVec<T> {
    pub fn new() -> Self {
        Self { inner: Vec::new() }
    }

    pub fn insert(&mut self, value: T) {
        let pos = self.inner.binary_search(&value).unwrap_or_else(|e| e);
        self.inner.insert(pos, value);
        debug_assert!(self.inner.windows(2).all(|w| w[0] <= w[1]));
    }

    pub fn as_slice(&self) -> &[T] {
        &self.inner
    }
}
```

## Boundary Validation (Parse, Don't Validate)

```rust
// Newtype pattern: wrap primitives to enforce constraints
pub struct EmailAddress(String);

impl EmailAddress {
    pub fn parse(raw: &str) -> Result<Self, ValidationError> {
        let trimmed = raw.trim();
        if trimmed.is_empty() || !trimmed.contains('@') {
            return Err(ValidationError::InvalidEmail(raw.to_string()));
        }
        Ok(Self(trimmed.to_string()))
    }

    pub fn as_str(&self) -> &str { &self.0 }
}

pub struct PositiveInt(u64);

impl PositiveInt {
    pub fn new(value: u64) -> Result<Self, ValidationError> {
        if value == 0 {
            return Err(ValidationError::MustBePositive);
        }
        Ok(Self(value))
    }

    pub fn get(&self) -> u64 { self.0 }
}

// At the API boundary: parse raw input into validated types
pub fn handle_create_order(raw: &RawPayload) -> Result<OrderResult, ApiError> {
    let items: Vec<OrderItem> = raw.items
        .iter()
        .map(|raw_item| {
            let product_id = ProductId::parse(&raw_item.id)?;
            let quantity = PositiveInt::new(raw_item.quantity)?;
            Ok(OrderItem { product_id, quantity })
        })
        .collect::<Result<Vec<_>, _>>()?;

    let order = Order { items };  // from here inward, types are trusted
    process_order(&order)
}
```

## Ownership and Borrowing (Rust's Defensive Copies)

```rust
// Rust's ownership model prevents most accidental sharing issues.
// Key patterns:

// Take ownership when storing data
pub struct UserProfile {
    name: String,          // owned — no external references to worry about
    tags: Vec<String>,
}

impl UserProfile {
    pub fn new(name: String, tags: Vec<String>) -> Self {
        Self { name, tags }  // ownership transferred in, caller can't mutate
    }

    // Return references for read access
    pub fn name(&self) -> &str { &self.name }
    pub fn tags(&self) -> &[String] { &self.tags }

    // Clone when caller needs an independent copy
    pub fn tags_owned(&self) -> Vec<String> { self.tags.clone() }
}

// Use Arc<T> for shared read-only data across threads
use std::sync::Arc;
let config: Arc<Config> = Arc::new(load_config());
// Multiple threads get cheap read-only access, no mutation possible

// Use Arc<Mutex<T>> only when shared mutation is genuinely required
use std::sync::Mutex;
let shared_state: Arc<Mutex<State>> = Arc::new(Mutex::new(State::new()));
```

## Resource Safety (RAII via Drop)

```rust
// Rust's Drop trait is automatic RAII — resources are released when
// the owner goes out of scope. Smart pointers, file handles, locks,
// and connections all implement Drop.

// File handles: automatically closed
{
    let file = File::create("output.txt")?;
    write!(file, "data")?;
}   // file closed here

// Mutex locks: automatically released
{
    let guard = mutex.lock().unwrap();
    guard.push(item);
}   // lock released here

// Custom resource management via Drop
pub struct TempDir {
    path: PathBuf,
}

impl TempDir {
    pub fn new(prefix: &str) -> io::Result<Self> {
        let path = create_temp_directory(prefix)?;
        Ok(Self { path })
    }

    pub fn path(&self) -> &Path { &self.path }
}

impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.path);
    }
}

// Usage: directory is cleaned up no matter how scope exits
let tmp = TempDir::new("build")?;
do_work(tmp.path())?;
// tmp dropped here — directory deleted
```

## Safe Defaults

```rust
// Exhaustive matching: compiler enforces handling all variants
#[derive(Debug)]
pub enum OrderStatus {
    Pending,
    Confirmed,
    Shipped,
    Delivered,
    Cancelled,
}

fn next_action(status: &OrderStatus) -> &'static str {
    match status {
        OrderStatus::Pending => "confirm_payment",
        OrderStatus::Confirmed => "prepare_shipment",
        OrderStatus::Shipped => "track_delivery",
        OrderStatus::Delivered => "request_review",
        OrderStatus::Cancelled => "process_refund",
        // No _ wildcard — adding a new variant forces updating all match sites
    }
}

// Avoid boolean parameters — use enums
#[derive(Clone, Copy)]
pub enum Compression { Enabled, Disabled }

#[derive(Clone, Copy)]
pub enum Encryption { Enabled, Disabled }

pub fn write_file(
    path: &Path,
    data: &[u8],
    compression: Compression,
    encryption: Encryption,
) -> io::Result<()> { ... }

// Call site:
write_file(&path, &data, Compression::Enabled, Encryption::Disabled)?;

// Make illegal states unrepresentable with enums
// Bad: struct with fields that can be in invalid combinations
// Good: enum where each variant carries only its valid data
pub enum PaymentState {
    Pending,
    Authorized { auth_code: String, amount: Decimal },
    Captured { auth_code: String, capture_id: String, amount: Decimal },
    Refunded { capture_id: String, refund_id: String },
    Failed { reason: String },
}
// A Refunded payment always has a capture_id — can't be constructed without one

// #[must_use] to prevent ignoring important return values
#[must_use]
pub fn validate_config(config: &Config) -> Result<(), ConfigError> { ... }
```
