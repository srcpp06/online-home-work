/// A line in the cart: a product, its price in so'm and how many.
class Product {
  const Product(this.name, this.price, {this.quantity = 1});

  final String name;
  final int price;
  final int quantity;
}

class Cart {
  final Map<String, Product> _items = {};

  /// Adds a product. The same name again only increases its quantity.
  void add(Product product) {
    final existing = _items[product.name];
    _items[product.name] = existing == null
        ? product
        : Product(
            product.name,
            product.price,
            quantity: existing.quantity + product.quantity,
          );
  }

  int get itemCount => _items.values.fold(0, (sum, item) => sum + item.quantity);

  int get total =>
      _items.values.fold(0, (sum, item) => sum + item.price * item.quantity);

  /// The total after a discount of [percent], which must be 0..100.
  int totalWithDiscount(int percent) {
    if (percent < 0 || percent > 100) {
      throw ArgumentError.value(percent, 'percent', 'must be from 0 to 100');
    }
    return total - total * percent ~/ 100;
  }
}
