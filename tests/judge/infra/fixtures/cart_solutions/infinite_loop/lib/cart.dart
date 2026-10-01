class Cart {
  final List<int> _prices = [];

  int get total {
    while (true) {}
  }

  void add(int price) => _prices.add(price);

  void clear() => _prices.clear();

  int totalWithDiscount(int percent) => total - total * percent ~/ 100;
}
