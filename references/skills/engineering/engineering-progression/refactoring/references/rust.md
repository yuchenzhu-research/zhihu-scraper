# Rust Refactoring Reference

Rust refactoring patterns using traits, enums, pattern matching, and the module system. Ownership and exhaustive matching make refactorings safer -- the compiler catches dangling references and missed cases. Run `cargo check` after every step.

---

## Extract and Inline

```rust
// BEFORE: long function doing validation, conversion, and formatting
fn process_measurement(raw: f64, unit: &str) -> String {
    if raw < -273.15 && unit == "celsius" { panic!("below absolute zero"); }
    let kelvin = match unit {
        "celsius" => raw + 273.15,
        "fahrenheit" => (raw - 32.0) * 5.0 / 9.0 + 273.15,
        _ => raw,
    };
    format!("{kelvin:.2} K")
}

// AFTER: each concern extracted, error handling via Result
fn validate(raw: f64, unit: &str) -> Result<(), String> {
    if raw < -273.15 && unit == "celsius" {
        return Err("below absolute zero".into());
    }
    Ok(())
}
fn to_kelvin(raw: f64, unit: &str) -> f64 {
    match unit {
        "celsius" => raw + 273.15,
        "fahrenheit" => (raw - 32.0) * 5.0 / 9.0 + 273.15,
        _ => raw,
    }
}
fn process_measurement(raw: f64, unit: &str) -> Result<String, String> {
    validate(raw, unit)?;
    Ok(format!("{:.2} K", to_kelvin(raw, unit)))
}
```

## Move and Reorganize

```rust
// BEFORE: free functions with match on enum
enum Shape { Circle { radius: f64 }, Rect { w: f64, h: f64 } }

fn area(s: &Shape) -> f64 {
    match s {
        Shape::Circle { radius } => std::f64::consts::PI * radius * radius,
        Shape::Rect { w, h } => w * h,
    }
}

// AFTER: move behavior into the enum via impl block
impl Shape {
    fn area(&self) -> f64 {
        match self {
            Shape::Circle { radius } => std::f64::consts::PI * radius * radius,
            Shape::Rect { w, h } => w * h,
        }
    }
}
```

## Simplify Conditionals

```rust
// BEFORE: nested conditionals
fn shipping_cost(order: &Order) -> f64 {
    if order.is_domestic {
        if order.weight_kg > 20.0 {
            if order.is_priority { 25.0 } else { 15.0 }
        } else { 5.0 }
    } else { 50.0 }
}

// AFTER: tuple pattern matching replaces nested ifs
fn shipping_cost(order: &Order) -> f64 {
    match (order.is_domestic, order.weight_kg > 20.0, order.is_priority) {
        (false, _, _)       => 50.0,  // international
        (true, false, _)    => 5.0,   // domestic, light
        (true, true, true)  => 25.0,  // domestic, heavy, priority
        (true, true, false) => 15.0,  // domestic, heavy, standard
    }
}
```

## Refactoring Data

```rust
// BEFORE: primitive obsession — raw String for email
fn send_welcome(email: &str) {
    if !email.contains('@') { panic!("invalid email"); }
}

// AFTER: newtype pattern — validated once, trusted everywhere
struct Email(String);
impl Email {
    fn new(raw: &str) -> Result<Self, String> {
        if !raw.contains('@') { return Err(format!("invalid email: {raw}")); }
        Ok(Email(raw.to_string()))
    }
    fn as_str(&self) -> &str { &self.0 }
}

fn send_welcome(email: &Email) {
    println!("Sending to {}", email.as_str());  // no validation needed
}
```

## Dealing with Inheritance

```rust
// BEFORE: bloated trait with defaults most types override
trait Notifier {
    fn format_message(&self, msg: &str) -> String { format!("[NOTIFY] {msg}") }
    fn send(&self, msg: &str);
}

// AFTER: split into focused traits, compose with generics
trait Formatter {
    fn format(&self, msg: &str) -> String;
}
trait Sender {
    fn send(&self, formatted: &str);
}

struct EmailFormatter;
impl Formatter for EmailFormatter {
    fn format(&self, msg: &str) -> String { format!("[EMAIL] {msg}") }
}

fn notify(fmt: &impl Formatter, sender: &impl Sender, msg: &str) {
    sender.send(&fmt.format(msg));
}
```

## Breaking Dependencies in Legacy Code

```rust
// BEFORE: reads real filesystem — untestable
fn count_config_entries() -> usize {
    let content = std::fs::read_to_string("/etc/app/config.toml").unwrap();
    content.lines().filter(|l| !l.trim().is_empty()).count()
}

// AFTER: parameterize with a trait
trait ConfigSource {
    fn read_config(&self) -> Result<String, std::io::Error>;
}
struct FileSource { path: std::path::PathBuf }
impl ConfigSource for FileSource {
    fn read_config(&self) -> Result<String, std::io::Error> {
        std::fs::read_to_string(&self.path)
    }
}
fn count_config_entries(src: &impl ConfigSource) -> Result<usize, std::io::Error> {
    Ok(src.read_config()?.lines().filter(|l| !l.trim().is_empty()).count())
}

#[cfg(test)]
mod tests {
    struct Fake(String);
    impl super::ConfigSource for Fake {
        fn read_config(&self) -> Result<String, std::io::Error> { Ok(self.0.clone()) }
    }
    #[test]
    fn counts_non_empty_lines() {
        assert_eq!(super::count_config_entries(&Fake("a=1\n\nb=2\n".into())).unwrap(), 2);
    }
}
```
