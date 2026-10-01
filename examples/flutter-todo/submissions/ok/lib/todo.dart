import 'package:flutter/material.dart';

class Task {
  const Task(this.title, {this.done = false});

  final String title;
  final bool done;

  Task toggled() => Task(title, done: !done);
}

enum Filter { all, active, done }

class TodoList {
  var _tasks = <Task>[];

  List<Task> get tasks => [..._tasks];

  bool add(String title) {
    if (title.trim().isEmpty) return false;
    _tasks = [..._tasks, Task(title.trim())];
    return true;
  }

  void toggle(int index) {
    _tasks = [
      for (var i = 0; i < _tasks.length; i++)
        i == index ? _tasks[i].toggled() : _tasks[i],
    ];
  }

  int get remaining => filtered(Filter.active).length;

  List<Task> filtered(Filter filter) {
    if (filter == Filter.all) return tasks;
    final wantDone = filter == Filter.done;
    return _tasks.where((task) => task.done == wantDone).toList();
  }
}

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

  @override
  Widget build(BuildContext context) {
    final tasks = _list.tasks;
    return MaterialApp(
      home: Scaffold(
        appBar: AppBar(title: Text('Qolgan: ${_list.remaining}')),
        body: ListView.builder(
          itemCount: tasks.length + 1,
          itemBuilder: (context, i) {
            if (i == 0) {
              return ListTile(
                title: TextField(key: const Key('title'), controller: _title),
                trailing: TextButton(
                  key: const Key('add'),
                  onPressed: () => setState(() {
                    if (_list.add(_title.text)) _title.clear();
                  }),
                  child: const Text('Qoʻshish'),
                ),
              );
            }
            final task = tasks[i - 1];
            return CheckboxListTile(
              title: Text(task.title),
              value: task.done,
              onChanged: (_) => setState(() => _list.toggle(i - 1)),
            );
          },
        ),
      ),
    );
  }
}
