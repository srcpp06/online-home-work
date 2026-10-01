class Cart {
  final List<int> _prices = [];

  int get total {
    for (var i = 0; i < 100000; i++) {
      print('flood ' * 20);
    }
    return _prices.fold(0, (sum, price) => sum + price);
  }

  void add(int price) => _prices.add(price);

  void clear() => _prices.clear();

  int totalWithDiscount(int percent) => total - total * percent ~/ 100;
}
