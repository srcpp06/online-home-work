import 'package:cart/cart.dart';
import 'package:test/test.dart';

void main() {
  late Cart cart;

  setUpAll(() {
    cart = Cart()..add(10000);
  });

  tearDownAll(() {
    cart.clear();
  });

  group('Chegirma', () {
    test('10% chegirma qoʻllanadi', () {
      expect(cart.totalWithDiscount(10), 9000);
    });

    test('0% chegirmada narx oʻzgarmaydi', () {
      expect(cart.totalWithDiscount(0), 10000);
    });
  });
}
