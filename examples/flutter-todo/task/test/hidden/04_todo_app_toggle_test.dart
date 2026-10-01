import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:todo/todo.dart';

void main() {
  testWidgets('Katakcha bosilsa Qolgan soni kamayadi', (tester) async {
    await tester.pumpWidget(const TodoApp());
    await tester.enterText(find.byKey(const Key('title')), 'Dars qilish');
    await tester.tap(find.byKey(const Key('add')));
    await tester.pump();
    expect(find.text('Qolgan: 1'), findsOneWidget);

    await tester.tap(find.byType(Checkbox));
    await tester.pump();

    expect(find.text('Qolgan: 0'), findsOneWidget);
  });
}
