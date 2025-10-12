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

def test_remove_task_removes_task():
    manager = TaskManager()
    manager.add_task("Task 1", 1)
    manager.add_task("Task 2", 2)
    manager.remove_task("Task 1")
    assert len(manager.tasks) == 1
    assert manager.tasks[0].description == "Task 2"


def test_list_completed_tasks_only_completed(capfd):
    manager = TaskManager()
    manager.add_task("Task 1", 1)
    manager.add_task("Task 2", 2)
    manager.mark_task_completed("Task 2")
    manager.list_completed_tasks()
    out, err = capfd.readouterr()
    assert "Task: Task 2, Priority: 2, Status: Completed" in out
    assert "Task: Task 1" not in out


def test_list_pending_tasks_only_pending(capfd):
    manager = TaskManager()
    manager.add_task("Task 1", 1)
    manager.add_task("Task 2", 2)
    manager.mark_task_completed("Task 1")
    manager.list_pending_tasks()
    out, err = capfd.readouterr()
    assert "Task: Task 2, Priority: 2, Status: Pending" in out
    assert "Task: Task 1" not in out


def test_list_tasks_prints_all_tasks(capfd):
    manager = TaskManager()
    manager.add_task("Task 1", 1)
    manager.add_task("Task 2", 2)
    manager.list_tasks()
    out, err = capfd.readouterr()
    assert "Task: Task 1, Priority: 1, Status: Pending" in out
    assert "Task: Task 2, Priority: 2, Status: Pending" in out


