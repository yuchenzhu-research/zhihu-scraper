# Java Defensive Programming Reference

Idiomatic Java patterns for each defensive principle. Draws from Effective Java (Bloch), modern Java features (records, sealed classes, Optional), and established enterprise patterns.

---

## Immutability

```java
// Variables: final by default
final var timeout = Duration.ofSeconds(30);
final var user = getCurrentUser();
final var items = List.copyOf(rawItems);  // immutable copy

// Only omit final when reassignment is genuinely needed
int total = 0;  // accumulator: justified
for (final var item : cart.items()) {
    total += item.price();
}

// Prefer stream transformations over mutable accumulation
final long total = cart.items().stream()
    .mapToLong(Item::price)
    .sum();

// Records: immutable by construction (Java 16+)
public record Coordinate(double latitude, double longitude) {}
public record OrderLine(ProductId productId, int quantity, long unitPrice) {}
// Fields are final, constructor is generated, equals/hashCode are correct

// Traditional immutable class when records aren't enough
public final class Config {
    private final String host;
    private final int port;
    private final Duration timeout;

    public Config(String host, int port, Duration timeout) {
        this.host = Objects.requireNonNull(host, "host must not be null");
        this.port = port;
        this.timeout = Objects.requireNonNull(timeout, "timeout must not be null");
    }

    public String host() { return host; }
    public int port() { return port; }
    public Duration timeout() { return timeout; }
}

// Parameters: mark final in method signatures
public OrderResult process(final Order order) { ... }

// Collections: return unmodifiable views
public List<Item> items() {
    return Collections.unmodifiableList(items);
}
// Or use List.copyOf() for a true immutable copy
```

## Minimal Visibility

```java
public class OrderProcessor {
    // Fields: always private
    private final Database db;
    private final TaxService taxService;

    public OrderProcessor(Database db, TaxService taxService) {
        this.db = Objects.requireNonNull(db);
        this.taxService = Objects.requireNonNull(taxService);
    }

    // Public: the contract
    public OrderResult process(Order order) {
        validate(order);
        final var tax = calculateTax(order);
        return persist(order, tax);
    }

    // Private: implementation details
    private void validate(Order order) { ... }
    private BigDecimal calculateTax(Order order) { ... }
    private OrderResult persist(Order order, BigDecimal tax) { ... }
}

// Seal classes to prevent uncontrolled inheritance (Java 17+)
public sealed class Shape permits Circle, Rectangle, Triangle {}
public final class Circle extends Shape { ... }
public final class Rectangle extends Shape { ... }
public final class Triangle extends Shape { ... }
// No other class can extend Shape

// Final classes when no subclassing is intended
public final class PaymentGateway {
    // Safe to refactor internals — no subclasses depend on behavior
}

// Package-private (default access) for internal helpers
class OrderValidator {  // no public modifier — package-private
    // Only visible within the same package
}

// Module system (Java 9+): export only public API packages
// module-info.java
module com.example.orders {
    exports com.example.orders.api;         // public contract
    // com.example.orders.internal is NOT exported
}
```

## Design by Contract

```java
import java.util.Objects;

public class BinarySearch {
    /**
     * Precondition: list must be sorted in ascending order.
     * Postcondition: returns index of target, or -1 if not found.
     */
    public static <T extends Comparable<T>> int search(List<T> list, T target) {
        // Preconditions
        Objects.requireNonNull(list, "list must not be null");
        Objects.requireNonNull(target, "target must not be null");
        assert isSorted(list) : "list must be sorted";

        // ... implementation ...

        // Postcondition
        assert result == -1 || list.get(result).equals(target)
            : "postcondition violated: result doesn't match target";
        return result;
    }

    private static <T extends Comparable<T>> boolean isSorted(List<T> list) {
        for (int i = 1; i < list.size(); i++) {
            if (list.get(i - 1).compareTo(list.get(i)) > 0) return false;
        }
        return true;
    }
}

// Class invariants
public class BankAccount {
    private final String owner;
    private long balanceCents;  // invariant: >= 0

    public BankAccount(String owner, long initialBalanceCents) {
        this.owner = Objects.requireNonNull(owner);
        if (initialBalanceCents < 0) {
            throw new IllegalArgumentException("Balance must be non-negative");
        }
        this.balanceCents = initialBalanceCents;
    }

    public void withdraw(long amountCents) {
        if (amountCents <= 0) {
            throw new IllegalArgumentException("Amount must be positive");
        }
        if (amountCents > balanceCents) {
            throw new IllegalStateException("Insufficient funds");
        }
        balanceCents -= amountCents;
        assert balanceCents >= 0 : "invariant violated: negative balance";
    }
}

// Objects.requireNonNull at every public entry point
public void sendEmail(EmailAddress to, String subject, String body) {
    Objects.requireNonNull(to, "to must not be null");
    Objects.requireNonNull(subject, "subject must not be null");
    Objects.requireNonNull(body, "body must not be null");
    // ...
}
```

## Boundary Validation

```java
// Parse, don't validate — create validated types at the boundary
public record EmailAddress(String value) {
    public EmailAddress {
        Objects.requireNonNull(value, "email must not be null");
        final var trimmed = value.trim();
        if (trimmed.isEmpty() || !trimmed.contains("@")) {
            throw new IllegalArgumentException("Invalid email: " + value);
        }
        value = trimmed;  // compact constructor reassignment
    }

    public static Optional<EmailAddress> tryParse(String raw) {
        try {
            return Optional.of(new EmailAddress(raw));
        } catch (IllegalArgumentException e) {
            return Optional.empty();
        }
    }
}

public record PositiveInt(int value) {
    public PositiveInt {
        if (value <= 0) {
            throw new IllegalArgumentException("Must be positive: " + value);
        }
    }
}

// At the API boundary: validate and convert
public OrderResult handleCreateOrder(JsonNode raw) {
    if (!raw.has("items") || !raw.get("items").isArray()) {
        throw new BadRequestException("Payload must contain 'items' array");
    }

    final var items = StreamSupport.stream(raw.get("items").spliterator(), false)
        .map(node -> {
            final var productId = ProductId.parse(node.get("id").asText());
            final var quantity = new PositiveInt(node.get("quantity").asInt());
            return new OrderItem(productId, quantity);
        })
        .toList();  // unmodifiable list (Java 16+)

    final var order = new Order(items);  // trusted from here inward
    return processOrder(order);
}
```

## Defensive Copies

```java
public class Inventory {
    private final List<Item> items;

    public Inventory(List<Item> items) {
        // Defensive copy on ingress
        this.items = List.copyOf(items);  // immutable copy
    }

    public List<Item> items() {
        // Already immutable — safe to return directly
        return items;
    }
}

// For mutable internal collections where you need modification
public class MutableInventory {
    private final List<Item> items;

    public MutableInventory(List<Item> items) {
        // Copy on ingress
        this.items = new ArrayList<>(items);
    }

    public List<Item> items() {
        // Defensive copy on egress
        return Collections.unmodifiableList(items);
    }

    public void addItem(Item item) {
        items.add(Objects.requireNonNull(item));
    }
}

// Dates and mutable objects: always copy
public class Event {
    private final Instant startTime;  // Instant is immutable — safe
    private final Date legacyDate;    // Date is mutable — must copy

    public Event(Instant startTime, Date legacyDate) {
        this.startTime = startTime;
        this.legacyDate = new Date(legacyDate.getTime());  // defensive copy
    }

    public Date legacyDate() {
        return new Date(legacyDate.getTime());  // defensive copy on egress
    }
}
```

## Resource Safety

```java
// Try-with-resources: automatic cleanup
try (final var conn = dataSource.getConnection();
     final var stmt = conn.prepareStatement(sql);
     final var rs = stmt.executeQuery()) {
    while (rs.next()) {
        // process rows
    }
}   // all three resources closed in reverse order

// Custom AutoCloseable
public class TempDirectory implements AutoCloseable {
    private final Path path;

    public TempDirectory(String prefix) throws IOException {
        this.path = Files.createTempDirectory(prefix);
    }

    public Path path() { return path; }

    @Override
    public void close() throws IOException {
        // Clean up recursively
        Files.walk(path)
            .sorted(Comparator.reverseOrder())
            .forEach(p -> {
                try { Files.delete(p); }
                catch (IOException ignored) {}
            });
    }
}

// Usage
try (final var tmp = new TempDirectory("build")) {
    doWork(tmp.path());
}   // directory deleted no matter what
```

## Safe Defaults

```java
// Exhaustive matching with sealed types and switch expressions (Java 21+)
public sealed interface OrderStatus
    permits Pending, Confirmed, Shipped, Delivered, Cancelled {}
public record Pending() implements OrderStatus {}
public record Confirmed(Instant confirmedAt) implements OrderStatus {}
public record Shipped(String trackingId) implements OrderStatus {}
public record Delivered(Instant deliveredAt) implements OrderStatus {}
public record Cancelled(String reason) implements OrderStatus {}

public String nextAction(OrderStatus status) {
    return switch (status) {
        case Pending p -> "confirm_payment";
        case Confirmed c -> "prepare_shipment";
        case Shipped s -> "track_delivery";
        case Delivered d -> "request_review";
        case Cancelled c -> "process_refund";
        // Compiler enforces exhaustiveness — adding new subtype = compile error
    };
}

// Avoid boolean parameters — use enums
public enum Compression { ENABLED, DISABLED }
public enum Encryption { ENABLED, DISABLED }

public void writeFile(Path path, byte[] data,
                      Compression compression, Encryption encryption) { ... }
// Call site:
writeFile(outputPath, payload, Compression.ENABLED, Encryption.DISABLED);

// Optional instead of null for values that might be absent
public Optional<User> findUser(UserId id) {
    // Forces caller to handle the absent case
    ...
}
// Never: public User findUser(UserId id) { return null; }
```
