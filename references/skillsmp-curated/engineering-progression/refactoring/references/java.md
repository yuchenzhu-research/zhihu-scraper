# Java Refactoring Reference

Modern Java refactoring patterns using records, sealed classes, Optional, and streams. Java's strong type system and IDE tooling make mechanical refactorings safe and automated. Use these patterns to go beyond what the IDE offers.

---

## Extract and Inline

```java
// BEFORE: long method with interleaved concerns
public Invoice createInvoice(Order order) {
    if (order.getItems().isEmpty()) throw new IllegalArgumentException("empty");
    for (var item : order.getItems())
        if (item.quantity() <= 0) throw new IllegalArgumentException("bad qty");
    double subtotal = 0;
    for (var item : order.getItems()) subtotal += item.price() * item.quantity();
    double discount = subtotal > 500 ? subtotal * 0.1 : 0;
    return new Invoice(order.getId(), subtotal - discount);
}

// AFTER: each concern is a named method
public Invoice createInvoice(Order order) {
    validateOrder(order);
    double subtotal = computeSubtotal(order.getItems());
    return new Invoice(order.getId(), subtotal - computeDiscount(subtotal));
}
private void validateOrder(Order order) {
    if (order.getItems().isEmpty()) throw new IllegalArgumentException("empty");
    order.getItems().forEach(i -> {
        if (i.quantity() <= 0) throw new IllegalArgumentException("bad qty");
    });
}
private double computeSubtotal(List<OrderItem> items) {
    return items.stream().mapToDouble(i -> i.price() * i.quantity()).sum();
}
```

## Move and Reorganize

```java
// BEFORE: switch on type code string
public String nextAction(String status) {
    return switch (status) {
        case "pending"   -> "confirm_payment";
        case "confirmed" -> "prepare_shipment";
        default -> throw new IllegalArgumentException(status);
    };
}

// AFTER: sealed interface + records — compiler enforces exhaustiveness
sealed interface OrderStatus {
    String nextAction();
    record Pending()   implements OrderStatus {
        public String nextAction() { return "confirm_payment"; }
    }
    record Confirmed() implements OrderStatus {
        public String nextAction() { return "prepare_shipment"; }
    }
    record Shipped()   implements OrderStatus {
        public String nextAction() { return "track_delivery"; }
    }
}
```

## Simplify Conditionals

```java
// BEFORE: nested null checks
public String formatAddress(Customer c) {
    if (c != null)
        if (c.getAddress() != null)
            if (c.getAddress().getCity() != null)
                return c.getAddress().getCity() + ", " + c.getAddress().getCountry();
            else return c.getAddress().getCountry();
        else return "no address";
    return "unknown";
}

// AFTER: Optional chain eliminates null checks
public String formatAddress(Optional<Customer> customer) {
    return customer
        .flatMap(c -> Optional.ofNullable(c.getAddress()))
        .map(addr -> Optional.ofNullable(addr.getCity())
            .map(city -> city + ", " + addr.getCountry())
            .orElse(addr.getCountry()))
        .orElse("unknown");
}
```

## Refactoring Data

```java
// BEFORE: primitive obsession — validation scattered at every call site
public void registerUser(String email, String name, int age) {
    if (!email.contains("@")) throw new IllegalArgumentException("bad email");
    if (name.isBlank()) throw new IllegalArgumentException("blank name");
}

// AFTER: records with compact constructors validate on creation
public record Email(String value) {
    public Email { if (!value.contains("@")) throw new IllegalArgumentException(value); }
}
public record UserName(String value) {
    public UserName { if (value.isBlank()) throw new IllegalArgumentException("blank"); }
}

public void registerUser(Email email, UserName name) {
    // No validation — records guarantee valid data
}
```

## Dealing with Inheritance

```java
// BEFORE: inheritance for code reuse — Notifier is not an EmailClient
public class EmailClient {
    public void sendRaw(String to, String body) { /* SMTP */ }
}
public class OrderNotifier extends EmailClient {
    public void notifyShipped(Order order) {
        sendRaw(order.email(), "Order " + order.id() + " shipped!");
    }
}

// AFTER: composition via interface
public interface MessageSender { void send(String to, String body); }

public class OrderNotifier {
    private final MessageSender sender;
    public OrderNotifier(MessageSender sender) { this.sender = sender; }
    public void notifyShipped(Order order) {
        sender.send(order.email(), "Order " + order.id() + " shipped!");
    }
}
```

## Breaking Dependencies in Legacy Code

```java
// BEFORE: untestable — static calls to real clock and database
public class BillingService {
    public Invoice generate(long customerId) {
        var now = LocalDate.now();
        var charges = Database.query("SELECT * FROM charges WHERE id=?", customerId);
        double total = 0;
        for (var c : charges) total += c.amount();
        return new Invoice(customerId, total, now);
    }
}

// AFTER: inject dependencies via constructor
public interface ChargeRepository {
    List<Charge> findByCustomer(long id, int month);
}

public class BillingService {
    private final Clock clock;
    private final ChargeRepository charges;

    public BillingService(Clock clock, ChargeRepository charges) {
        this.clock = clock;
        this.charges = charges;
    }
    public Invoice generate(long customerId) {
        var now = LocalDate.now(clock);
        double total = charges.findByCustomer(customerId, now.getMonthValue())
            .stream().mapToDouble(Charge::amount).sum();
        return new Invoice(customerId, total, now);
    }
}
```
