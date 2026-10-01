class Cart {
  final List<int> _prices = [];

  int get total {
    final chunks = <List<int>>[];
    while (true) {
      chunks.add(List<int>.filled(1 << 20, 1));
    }
  }

  void add(int price) => _prices.add(price);

  void clear() => _prices.clear();

  int totalWithDiscount(int percent) => total - total * percent ~/ 100;
}
