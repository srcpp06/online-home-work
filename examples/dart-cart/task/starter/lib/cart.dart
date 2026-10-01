/// A line in the cart: a product, its price in so'm and how many.
class Product {
  const Product(this.name, this.price, {this.quantity = 1});

  final String name;
  final int price;
  final int quantity;
}

class Cart {
  /// Adds a product. The same name again only increases its quantity.
  void add(Product product) {
    throw UnimplementedError();
  }

  /// Removes a product by name. Removing a missing product does nothing.
  void remove(String name) {
    throw UnimplementedError();
  }

  int get itemCount => throw UnimplementedError();

  int get total => throw UnimplementedError();

  /// The total after a discount of [percent], which must be 0..100.
  /// Any other percent throws an ArgumentError.
  int totalWithDiscount(int percent) {
    throw UnimplementedError();
  }
}
