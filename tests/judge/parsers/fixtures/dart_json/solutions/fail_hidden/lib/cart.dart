class Cart {
  final List<int> _prices = [];

  int get total => _prices.fold(0, (sum, price) => sum + price);

  void add(int price) => _prices.add(price);

  void clear() => _prices.clear();

  int totalWithDiscount(int percent) => total - percent;
}
