import 'package:flutter_test/flutter_test.dart';
import 'package:todo/todo.dart';

void main() {
  late TodoList list;

  setUp(() {
    list = TodoList()
      ..add('Dars qilish')
      ..add('Sport')
      ..add('Kitob oʻqish')
      ..toggle(1);
  });

  test('Bajarilgan vazifa qolganlar sonidan chiqadi', () {
    expect(list.remaining, 2);
  });

  test('Bajarilmaganlar filtri', () {
    final titles = list.filtered(Filter.active).map((task) => task.title);

    expect(titles, ['Dars qilish', 'Kitob oʻqish']);
  });

  test('Bajarilganlar filtri', () {
    expect(list.filtered(Filter.done).single.title, 'Sport');
  });

  test('Ikki marta belgilansa vazifa yana bajarilmagan boʻladi', () {
    list.toggle(1);

    expect(list.remaining, 3);
  });
}
