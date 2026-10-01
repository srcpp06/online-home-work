import 'package:cart/cart.dart';
import 'package:test/test.dart';

void main() {
  test('Yangi savat boʻsh: jami 0 ga teng', () {
    final cart = Cart();

    expect(cart.total, 0);
    expect(cart.itemCount, 0);
  });

  test('Mahsulot qoʻshilganda jami ortadi', () {
    final cart = Cart()
      ..add(const Product('Non', 4000))
      ..add(const Product('Sut', 12000));

    expect(cart.total, 16000);
  });

  test('Bir xil mahsulot qayta qoʻshilsa soni ortadi', () {
    final cart = Cart()
      ..add(const Product('Non', 4000))
      ..add(const Product('Non', 4000, quantity: 2));

    expect(cart.itemCount, 3);
    expect(cart.total, 12000);
  });
}
