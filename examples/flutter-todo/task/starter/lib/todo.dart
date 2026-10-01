import 'package:flutter/material.dart';

class Task {
  const Task(this.title, {this.done = false});

  final String title;
  final bool done;
}

enum Filter { all, active, done }

class TodoList {
  List<Task> get tasks => throw UnimplementedError();

  /// Adds a task. Blank titles are ignored; returns whether the task was added.
  bool add(String title) {
    throw UnimplementedError();
  }

  /// Marks the task done, or not done again.
  void toggle(int index) {
    throw UnimplementedError();
  }

  /// How many tasks are not done yet.
  int get remaining => throw UnimplementedError();

  List<Task> filtered(Filter filter) {
    throw UnimplementedError();
  }
}

/// A text field (Key('title')) with an add button (Key('add')), the list with
/// checkboxes, and "Qolgan: N" (tasks left) in the app bar.
class TodoApp extends StatefulWidget {
  const TodoApp({super.key});

  @override
  State<TodoApp> createState() => _TodoAppState();
}

class _TodoAppState extends State<TodoApp> {
  @override
  Widget build(BuildContext context) {
    throw UnimplementedError();
  }
}
