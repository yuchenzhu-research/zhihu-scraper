# C++ Refactoring Reference

Modern C++ (C++17/20) refactoring patterns using std::variant, std::optional, concepts, and structured bindings. Lean on the compiler and sanitizers as your safety net.

---

## Extract and Inline

```cpp
// BEFORE: long function with interleaved concerns
double processTransaction(const Transaction& tx) {
    if (tx.amount <= 0) throw std::invalid_argument("bad amount");
    if (tx.account.empty()) throw std::invalid_argument("no account");
    double fee = tx.amount > 10000 ? tx.amount * 0.01 : tx.amount * 0.02;
    double tax = (tx.amount + fee) * 0.08;
    return tx.amount + fee + tax;
}

// AFTER: each concern is a named function
void validateTransaction(const Transaction& tx) {
    if (tx.amount <= 0) throw std::invalid_argument("bad amount");
    if (tx.account.empty()) throw std::invalid_argument("no account");
}
double computeFee(double amount) {
    return amount > 10000 ? amount * 0.01 : amount * 0.02;
}
double processTransaction(const Transaction& tx) {
    validateTransaction(tx);
    double fee = computeFee(tx.amount);
    return tx.amount + fee + (tx.amount + fee) * 0.08;
}
```

## Move and Reorganize

```cpp
// BEFORE: switch on type tag — must update every switch for new shapes
enum class ShapeType { Circle, Rectangle };
struct Shape { ShapeType type; double radius, width, height; };

double area(const Shape& s) {
    switch (s.type) {
        case ShapeType::Circle:    return 3.14159 * s.radius * s.radius;
        case ShapeType::Rectangle: return s.width * s.height;
    }
}

// AFTER: std::variant — compiler errors guide updates when adding types
struct Circle    { double radius; };
struct Rectangle { double width, height; };
using Shape = std::variant<Circle, Rectangle>;

double area(const Shape& s) {
    return std::visit([](const auto& shape) -> double {
        using T = std::decay_t<decltype(shape)>;
        if constexpr (std::is_same_v<T, Circle>)
            return 3.14159 * shape.radius * shape.radius;
        else if constexpr (std::is_same_v<T, Rectangle>)
            return shape.width * shape.height;
    }, s);
}
```

## Simplify Conditionals

```cpp
// BEFORE: nested conditionals with optional checks
std::string formatUser(const User& user) {
    if (user.name.has_value()) {
        if (user.email.has_value())
            return *user.name + " <" + *user.email + ">";
        else return *user.name;
    } else return "anonymous";
}

// AFTER: guard clauses with early returns
std::string formatUser(const User& user) {
    if (!user.name.has_value())  return "anonymous";
    if (!user.email.has_value()) return *user.name;
    return *user.name + " <" + *user.email + ">";
}
```

## Refactoring Data

```cpp
// BEFORE: primitive obsession — raw doubles for money
double applyDiscount(double price, double discount) {
    return price - discount;  // could go negative, no currency info
}

// AFTER: value object enforces invariants
class Money {
    int cents_;
public:
    explicit Money(int cents) : cents_(cents) {
        if (cents < 0) throw std::invalid_argument("Money cannot be negative");
    }
    static Money fromDollars(double d) {
        return Money(static_cast<int>(d * 100 + 0.5));
    }
    Money operator-(const Money& o) const { return Money(cents_ - o.cents_); }
    int cents() const { return cents_; }
};

Money applyDiscount(Money price, Money discount) {
    return price - discount;  // type-safe, enforces non-negative
}
```

## Dealing with Inheritance

```cpp
// BEFORE: virtual base class for code reuse
class Animal {
public:
    virtual ~Animal() = default;
    virtual std::string speak() const = 0;
    void log(const std::string& msg) { std::cout << msg << "\n"; }
};
class Dog : public Animal {
    std::string speak() const override { return "Woof"; }
};

// AFTER: concept + composition — no inheritance
template<typename T>
concept Speaker = requires(const T& t) {
    { t.speak() } -> std::convertible_to<std::string>;
};

class Dog { public: std::string speak() const { return "Woof"; } };

template<Speaker T>
void announce(const T& animal, Logger& logger) {
    logger.log(animal.speak());
}
```

## Breaking Dependencies in Legacy Code

```cpp
// BEFORE: untestable — constructs real DB connection inline
class OrderRepository {
public:
    void save(const Order& order) {
        DatabaseConnection db("prod_host", 5432);
        db.execute("INSERT INTO orders ...");
    }
};

// AFTER: inject dependency via constructor
class Database {
public:
    virtual ~Database() = default;
    virtual void execute(const std::string& sql) = 0;
};

class OrderRepository {
    std::shared_ptr<Database> db_;
public:
    explicit OrderRepository(std::shared_ptr<Database> db) : db_(std::move(db)) {}
    void save(const Order& order) { db_->execute("INSERT INTO orders ..."); }
};

// Test double — no real database needed
class FakeDatabase : public Database {
public:
    std::vector<std::string> executed;
    void execute(const std::string& sql) override { executed.push_back(sql); }
};
```
