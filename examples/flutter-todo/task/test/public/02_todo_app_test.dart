import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:todo/todo.dart';

void main() {
  testWidgets('Nom yozib Qoʻshish bosilsa vazifa ekranda koʻrinadi', (tester) async {
    await tester.pumpWidget(const TodoApp());
    expect(find.text('Qolgan: 0'), findsOneWidget);

    await tester.enterText(find.byKey(const Key('title')), 'Sut olish');
    await tester.tap(find.byKey(const Key('add')));
    await tester.pump();

    expect(find.text('Sut olish'), findsOneWidget);
    expect(find.text('Qolgan: 1'), findsOneWidget);
  });
}
