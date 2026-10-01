import 'package:cart/cart.dart';
import 'package:test/test.dart';

void main() {
  test('Savat boʻsh boʻlsa jami 0 ga teng', () {
    expect(Cart().total, 0);
  });

  test('Mahsulot qoʻshilganda jami ortadi', () {
    final cart = Cart()
      ..add(1500)
      ..add(2500);
    expect(cart.total, 4000);
  });
}
