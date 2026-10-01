import 'package:counter/counter.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Ikki marta oshirilganda 2 boʻladi', () {
    final counter = Counter()
      ..increment()
      ..increment();
    expect(counter.value, 2);
  });
}
