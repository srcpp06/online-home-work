import 'package:flutter/material.dart';

class Counter {
  int value = 0;

  void increment() => value++;
}

class CounterView extends StatefulWidget {
  const CounterView({super.key});

  @override
  State<CounterView> createState() => _CounterViewState();
}

class _CounterViewState extends State<CounterView> {
  final _counter = Counter();

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        body: Center(child: Text('${_counter.value}')),
        floatingActionButton: FloatingActionButton(
          onPressed: () => setState(_counter.increment),
          child: const Icon(Icons.add),
        ),
      ),
    );
  }
}
