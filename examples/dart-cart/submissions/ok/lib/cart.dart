class Product {
  const Product(this.name, this.price, {this.quantity = 1});

  final String name;
  final int price;
  final int quantity;
}

class Cart {
  final List<Product> _items = [];

  void add(Product product) {
    final index = _items.indexWhere((item) => item.name == product.name);
    if (index == -1) {
      _items.add(product);
      return;
    }
    final old = _items[index];
    _items[index] =
        Product(old.name, old.price, quantity: old.quantity + product.quantity);
  }

  void remove(String name) => _items.removeWhere((item) => item.name == name);

  int get itemCount {
    var count = 0;
    for (final item in _items) {
      count += item.quantity;
    }
    return count;
  }

  int get total {
    var sum = 0;
    for (final item in _items) {
      sum += item.price * item.quantity;
    }
    return sum;
  }

  int totalWithDiscount(int percent) {
    if (percent < 0 || percent > 100) throw ArgumentError('percent: $percent');
    return total * (100 - percent) ~/ 100;
  }
}
