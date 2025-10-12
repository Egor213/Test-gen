import pytest
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

def test_list_tasks():
    manager = TaskManager()
    manager.add_task("Test Task 1", 1)
    manager.add_task("Test Task 2", 2)
    tasks = manager.list_tasks()
    assert len(tasks) == 2

