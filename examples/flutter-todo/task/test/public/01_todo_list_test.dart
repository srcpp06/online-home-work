import 'package:flutter_test/flutter_test.dart';
import 'package:todo/todo.dart';

void main() {
  test('Yangi roʻyxat boʻsh', () {
    final list = TodoList();

    expect(list.tasks, isEmpty);
    expect(list.remaining, 0);
  });

  test('Vazifa qoʻshilganda roʻyxatga tushadi', () {
    final list = TodoList()..add('Kitob oʻqish');

    expect(list.tasks.single.title, 'Kitob oʻqish');
    expect(list.tasks.single.done, isFalse);
  });

  test('Boʻsh nomli vazifa qoʻshilmaydi', () {
    final list = TodoList();

    expect(list.add('   '), isFalse);
    expect(list.tasks, isEmpty);
  });
}
