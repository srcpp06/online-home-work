import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:warmup/main.dart';

void main() {
  testWidgets('tap increments the counter', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Counter()));
    expect(find.text('0'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.add));
    await tester.pump();

    expect(find.text('1'), findsOneWidget);
  });
}
