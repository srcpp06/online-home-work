import 'package:cart/cart.dart';
import 'package:test/test.dart';

void main() {
  late Cart cart;

  setUp(() {
    cart = Cart()..add(const Product('Kitob', 50000, quantity: 2));
  });

  group('Chegirma:', () {
    test('10% da jami 10% kamayadi', () {
      expect(cart.totalWithDiscount(10), 90000);
    });

    test('0% da jami oʻzgarmaydi', () {
      expect(cart.totalWithDiscount(0), 100000);
    });

    test('100% da jami 0 ga teng', () {
      expect(cart.totalWithDiscount(100), 0);
    });

    test('notoʻgʻri foiz ArgumentError beradi', () {
      expect(() => cart.totalWithDiscount(101), throwsArgumentError);
      expect(() => cart.totalWithDiscount(-5), throwsArgumentError);
    });
  });
}
