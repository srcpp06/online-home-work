import 'package:cart/cart.dart';
import 'package:test/test.dart';

void main() {
  test('Mahsulot olib tashlansa jami kamayadi', () {
    final cart = Cart()
      ..add(const Product('Non', 4000))
      ..add(const Product('Sut', 12000))
      ..remove('Non');

    expect(cart.total, 12000);
  });

  test('Savatda yoʻq mahsulotni olib tashlash xato bermaydi', () {
    final cart = Cart()..add(const Product('Non', 4000));

    expect(() => cart.remove('Choy'), returnsNormally);
    expect(cart.total, 4000);
  });
}
