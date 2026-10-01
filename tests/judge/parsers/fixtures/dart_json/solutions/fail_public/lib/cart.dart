class Cart {
  final List<int> _prices = [];

  int get total => _prices.isEmpty ? 0 : _prices.last;

  void add(int price) => _prices.add(price);

  void clear() => _prices.clear();

  int totalWithDiscount(int percent) => total - total * percent ~/ 100;
}
