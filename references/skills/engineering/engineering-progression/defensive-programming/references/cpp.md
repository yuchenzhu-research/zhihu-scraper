# C++ Defensive Programming Reference

Idiomatic C++ patterns for each defensive principle. Draws heavily from Effective C++ and Effective Modern C++ (Meyers), the C++ Core Guidelines, and CERT C++ Coding Standards.

---

## Immutability

```cpp
// Variables: const by default
const auto timeout = std::chrono::seconds{30};
const auto& user = get_current_user();  // const reference

// Only mutable when accumulation or iteration requires it
int total = 0;  // justified: loop accumulator
for (const auto& item : cart.items()) {
    total += item.price();
}

// Prefer const auto& for range-based loops
for (const auto& entry : map) { /* read only */ }

// Member functions: mark const when they don't modify state
class Account {
    double balance() const { return balance_; }  // const member function
    std::string name() const { return name_; }
};

// Fields: const or initialized at construction, never reassigned
class Config {
    const std::string host_;
    const int port_;
    const std::chrono::seconds timeout_;
public:
    Config(std::string host, int port, std::chrono::seconds timeout)
        : host_{std::move(host)}, port_{port}, timeout_{timeout} {}
};

// Parameters: pass by const reference for read-only access
void process(const std::vector<Order>& orders);
void render(const std::string& template_name);

// Return const values from accessors to prevent modification
const std::vector<Item>& items() const { return items_; }
```

## Minimal Visibility

```cpp
class OrderProcessor {
public:
    // Only the contract: what external code actually calls
    OrderResult process(const Order& order);

private:
    // Everything else is private
    bool validate_inventory(const Order& order) const;
    double calculate_tax(const LineItem& item) const;
    void update_ledger(const OrderResult& result);

    // Fields are always private
    Database& db_;
    TaxService& tax_service_;
    Logger& logger_;
};

// Prefer non-member non-friend functions (Meyers Item 23)
// If a function doesn't need private access, don't make it a member
namespace order_utils {
    double compute_subtotal(const std::vector<LineItem>& items);
    std::string format_receipt(const OrderResult& result);
}

// Use the pimpl idiom to hide implementation from headers
// header: order_processor.h
class OrderProcessor {
public:
    OrderProcessor();
    ~OrderProcessor();
    OrderResult process(const Order& order);
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

// Seal classes using final
class PaymentGateway final {
    // Cannot be subclassed — safe to refactor internals
};

// Seal virtual methods when override chain should stop
class DerivedHandler final : public BaseHandler {
    void handle(const Request& req) final override;
};
```

## Design by Contract

```cpp
#include <cassert>

// Preconditions: verify at function entry
double divide(double numerator, double denominator) {
    assert(denominator != 0.0 && "divide: denominator must be non-zero");
    return numerator / denominator;
}

// For public APIs, use explicit checks that remain in production
std::optional<User> find_user(std::string_view user_id) {
    if (user_id.empty()) {
        // Contract violation at a public boundary: handle explicitly
        return std::nullopt;
    }
    // ... implementation
}

// Class invariants: verify in debug builds
class BoundedBuffer {
    std::vector<uint8_t> data_;
    size_t read_pos_ = 0;
    size_t write_pos_ = 0;

    void check_invariant() const {
        assert(read_pos_ <= write_pos_);
        assert(write_pos_ <= data_.size());
    }

public:
    void write(std::span<const uint8_t> input) {
        check_invariant();
        // ... write logic ...
        check_invariant();  // postcondition: invariant preserved
    }
};

// Use [[nodiscard]] to enforce checking return values
[[nodiscard]] ErrorCode initialize_subsystem();
[[nodiscard]] std::optional<Config> load_config(const std::string& path);
```

## Boundary Validation

```cpp
// Boundary: parse raw input into validated internal types
class EmailAddress {
public:
    // Factory that validates at construction — no invalid instances exist
    static std::optional<EmailAddress> parse(std::string_view raw) {
        if (raw.empty() || raw.find('@') == std::string_view::npos) {
            return std::nullopt;
        }
        return EmailAddress{std::string{raw}};
    }

    const std::string& value() const { return value_; }

private:
    explicit EmailAddress(std::string val) : value_{std::move(val)} {}
    std::string value_;
};

// At the API boundary: validate and convert
std::optional<OrderRequest> parse_order_request(const json& raw) {
    if (!raw.contains("items") || !raw["items"].is_array()) {
        return std::nullopt;
    }
    // Convert to internal types — from here inward, data is trusted
    OrderRequest req;
    for (const auto& item : raw["items"]) {
        auto product_id = ProductId::parse(item["id"].get<std::string>());
        if (!product_id) return std::nullopt;
        req.items.push_back(*product_id);
    }
    return req;
}
```

## Defensive Copies and Move Semantics

```cpp
class UserProfile {
    std::string name_;
    std::vector<std::string> tags_;

public:
    // Constructor: take ownership via move, don't retain external references
    UserProfile(std::string name, std::vector<std::string> tags)
        : name_{std::move(name)}, tags_{std::move(tags)} {}

    // Accessor: return const reference (caller can't modify internals)
    const std::string& name() const { return name_; }

    // Return a copy when caller might store or modify the result
    std::vector<std::string> tags() const { return tags_; }

    // Or return a span for read-only iteration without copying
    std::span<const std::string> tag_view() const { return tags_; }
};
```

## Resource Safety (RAII)

```cpp
// Smart pointers: never use raw new/delete
auto config = std::make_unique<Config>(load_config());
auto shared_cache = std::make_shared<Cache>(1024);

// Custom RAII wrapper for non-memory resources
class FileHandle {
    FILE* file_;
public:
    explicit FileHandle(const char* path, const char* mode)
        : file_{std::fopen(path, mode)} {
        if (!file_) throw std::runtime_error("Failed to open file");
    }
    ~FileHandle() { if (file_) std::fclose(file_); }

    // Non-copyable, movable
    FileHandle(const FileHandle&) = delete;
    FileHandle& operator=(const FileHandle&) = delete;
    FileHandle(FileHandle&& other) noexcept : file_{other.file_} {
        other.file_ = nullptr;
    }
    FileHandle& operator=(FileHandle&& other) noexcept {
        std::swap(file_, other.file_);
        return *this;
    }

    FILE* get() const { return file_; }
};

// Lock guard: scope-based mutex management
{
    const std::lock_guard<std::mutex> lock{mutex_};
    // critical section — automatically released at scope exit
    shared_data_.push_back(item);
}
```

## Safe Defaults

```cpp
// Exhaustive switch with no default — compiler warns on missing cases
enum class OrderStatus { Pending, Confirmed, Shipped, Delivered, Cancelled };

std::string_view to_string(OrderStatus status) {
    switch (status) {
        case OrderStatus::Pending:   return "pending";
        case OrderStatus::Confirmed: return "confirmed";
        case OrderStatus::Shipped:   return "shipped";
        case OrderStatus::Delivered: return "delivered";
        case OrderStatus::Cancelled: return "cancelled";
    }
    // No default — adding a new enum value triggers a compiler warning
    __builtin_unreachable();
}

// Avoid boolean parameters — use enums
enum class Compression { Enabled, Disabled };
enum class Encryption { Enabled, Disabled };
void write_file(const std::string& path, std::span<const uint8_t> data,
                Compression comp, Encryption enc);
// Call site reads clearly:
write_file("out.dat", data, Compression::Enabled, Encryption::Disabled);

// Delete unwanted special members explicitly
class Singleton {
public:
    static Singleton& instance();
    Singleton(const Singleton&) = delete;
    Singleton& operator=(const Singleton&) = delete;
};
```
