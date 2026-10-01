class Cart {
  final List<int> _prices = [];

  int get total => _prices.fold(0, (sum, price) => sum + price);

  void add(int price) => _prices.add(price);

  void clear() => throw StateError('savatni tozalab boʻlmaydi');

  int totalWithDiscount(int percent) => total - total * percent ~/ 100;
}
