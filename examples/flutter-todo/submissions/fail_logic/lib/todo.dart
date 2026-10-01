import 'package:flutter/material.dart';

class Task {
  const Task(this.title, {this.done = false});

  final String title;
  final bool done;
}

enum Filter { all, active, done }

class TodoList {
  final List<Task> _tasks = [];

  List<Task> get tasks => List.unmodifiable(_tasks);

  /// Adds a task. Blank titles are ignored; returns whether the task was added.
  bool add(String title) {
    _tasks.add(Task(title.trim()));
    return true;
  }

  /// Marks the task done, or not done again.
  void toggle(int index) {
    final task = _tasks[index];
    _tasks[index] = Task(task.title, done: !task.done);
  }

  /// How many tasks are not done yet.
  int get remaining => _tasks.where((task) => !task.done).length;

  List<Task> filtered(Filter filter) => switch (filter) {
        Filter.all => tasks,
        Filter.active => _tasks.where((task) => !task.done).toList(),
        Filter.done => _tasks.where((task) => task.done).toList(),
      };
}

/// A text field with an add button, the list with checkboxes, and
/// "Qolgan: N" (tasks left) in the app bar.
class TodoApp extends StatefulWidget {
  const TodoApp({super.key});

  @override
  State<TodoApp> createState() => _TodoAppState();
}

class _TodoAppState extends State<TodoApp> {
  final _list = TodoList();
  final _title = TextEditingController();

  @override
  void dispose() {
    _title.dispose();
    super.dispose();
  }

  void _add() {
    setState(() {
      if (_list.add(_title.text)) _title.clear();
    });
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        appBar: AppBar(title: Text('Qolgan: ${_list.remaining}')),
        body: Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: TextField(key: const Key('title'), controller: _title),
                ),
                ElevatedButton(
                  key: const Key('add'),
                  onPressed: _add,
                  child: const Text('Qoʻshish'),
                ),
              ],
            ),
            Expanded(
              child: ListView(
                children: [
                  for (final (index, task) in _list.tasks.indexed)
                    CheckboxListTile(
                      title: Text(task.title),
                      value: task.done,
                      onChanged: (_) => setState(() => _list.toggle(index)),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
