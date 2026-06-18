from myapp.app import Task, TaskManager



def test_create_task():
    task = Task("Test Task", 1)
    assert task.description == "Test Task"
    assert task.priority == 1
    assert task.completed == False

def test_mark_task_completed():
    task = Task("Test Task", 1)
    task.mark_completed()
    assert task.completed == True

def test_add_task():
    manager = TaskManager()
    manager.add_task("Test Task", 1)
    assert len(manager.tasks) == 1
    assert manager.tasks[0].description == "Test Task"

def test_mark_task_completed_in_manager():
    manager = TaskManager()
    manager.add_task("Test Task", 1)
    manager.mark_task_completed("Test Task")
    assert manager.tasks[0].completed == True

def test_load_tasks_from_file_recreates_tasks(tmp_path):
    file_path = tmp_path / "tasks.txt"
    content = "Task 1,1,True\nTask 2,2,False\n"
    file_path.write_text(content)
    manager = TaskManager()
    manager.load_tasks_from_file(str(file_path))
    assert len(manager.tasks) == 2
    task1 = manager.tasks[0]
    task2 = manager.tasks[1]
    assert task1.description == "Task 1"
    assert task1.priority == 1
    assert task1.completed is True
    assert task2.description == "Task 2"
    assert task2.priority == 2
    assert task2.completed is False


def test_count_pending_tasks_returns_correct_count():
    manager = TaskManager()
    manager.add_task("Task 1", 1)
    manager.add_task("Task 2", 2)
    manager.mark_task_completed("Task 1")
    assert manager.count_pending_tasks() == 1


def test_filter_tasks_by_priority_returns_correct_tasks():
    manager = TaskManager()
    manager.add_task("Task 1", 1)
    manager.add_task("Task 2", 2)
    manager.add_task("Task 3", 1)
    filtered = manager.filter_tasks_by_priority(1)
    assert len(filtered) == 2
    assert all(task.priority == 1 for task in filtered)


def test_sort_tasks_by_priority_orders_tasks():
    manager = TaskManager()
    manager.add_task("Task 1", 5)
    manager.add_task("Task 2", 1)
    manager.add_task("Task 3", 3)
    manager.sort_tasks_by_priority()
    priorities = [task.priority for task in manager.tasks]
    assert priorities == [1, 3, 5]


def test_update_task_priority_changes_priority():
    manager = TaskManager()
    manager.add_task("Task 1", 1)
    manager.update_task_priority("Task 1", 5)
    assert manager.tasks[0].priority == 5


def test_remove_task_removes_correct_task():
    manager = TaskManager()
    manager.add_task("Task 1", 1)
    manager.add_task("Task 2", 2)
    manager.remove_task("Task 1")
    assert len(manager.tasks) == 1
    assert manager.tasks[0].description == "Task 2"


def test_list_completed_tasks_only_shows_completed(capfd):
    manager = TaskManager()
    manager.add_task("Task 1", 1)
    manager.add_task("Task 2", 2)
    manager.mark_task_completed("Task 1")
    manager.list_completed_tasks()
    out, err = capfd.readouterr()
    assert "Task: Task 1, Priority: 1, Status: Completed" in out
    assert "Task: Task 2" not in out


def test_list_pending_tasks_only_shows_pending(capfd):
    manager = TaskManager()
    manager.add_task("Task 1", 1)
    manager.add_task("Task 2", 2)
    manager.mark_task_completed("Task 2")
    manager.list_pending_tasks()
    out, err = capfd.readouterr()
    assert "Task: Task 1, Priority: 1, Status: Pending" in out
    assert "Task: Task 2" not in out


def test_list_tasks_prints_all_tasks(capfd):
    manager = TaskManager()
    manager.add_task("Task 1", 1)
    manager.add_task("Task 2", 2)
    manager.list_tasks()
    out, err = capfd.readouterr()
    assert "Task: Task 1, Priority: 1, Status: Pending" in out
    assert "Task: Task 2, Priority: 2, Status: Pending" in out


