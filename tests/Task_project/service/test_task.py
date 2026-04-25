from pathlib import Path
import sys


project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import pytest
from unittest.mock import MagicMock, patch


# Create a minimal stand-in for entity.entity.Task so that imports in managers/task.py work
class DummyTask:
    def __init__(self, description: str, priority: int):
        self.description = description
        self.priority = priority
        self.completed = False

    def mark_completed(self):
        self.completed = True


# Build a minimal stand-in for managers.task module before anything imports it
managers_task_module = type(sys)("managers.task")
managers_task_module.TaskManager = type(
    "TaskManager",
    (),
    {
        "test_2": 3,
        "test": 1,
        "__init__": lambda self: setattr(self, "tasks", []),
        "add_task": MagicMock(),
        "clear_all_tasks": MagicMock(),
        "count_completed_tasks": MagicMock(return_value=0),
        "count_pending_tasks": MagicMock(return_value=0),
        "filter_tasks_by_priority": MagicMock(return_value=[]),
        "get_task": MagicMock(return_value=None),
        "list_completed_tasks": MagicMock(return_value=[]),
        "list_pending_tasks": MagicMock(return_value=[]),
        "list_tasks": MagicMock(return_value=[]),
        "load_tasks_from_file": MagicMock(),
        "mark_task_completed": MagicMock(),
        "remove_task": MagicMock(),
        "save_tasks_to_file": MagicMock(),
        "sort_tasks_by_priority": MagicMock(),
        "update_task_priority": MagicMock(),
    },
)

# Provide stand-ins in sys.modules so imports resolve without the real entity package
sys.modules["entity"] = type(sys)("entity")
sys.modules["entity.entity"] = type(sys)("entity.entity")
sys.modules["entity.entity"].Task = DummyTask
sys.modules["managers"] = type(sys)("managers")
sys.modules["managers.task"] = managers_task_module


from Task_project.service.task import TaskService


class TestTaskServiceCreateTask:
    @pytest.fixture
    def service(self):
        return TaskService()

    @pytest.mark.parametrize(
        "description, priority",
        [
            ("Test task", 1),
            ("Another task", 3),
            ("High priority task", 5),
            ("Low priority task", 2),
        ],
    )
    def test_create_task_valid_inputs_returns_success_message(
        self, service, description, priority
    ):
        """Проверяет, что метод возвращает корректное сообщение при валидных входных данных."""
        with patch.object(service.manager, "add_task") as mock_add_task:
            result = service.create_task(description, priority)
            mock_add_task.assert_called_once_with(description, priority)
            assert result == f"Task '{description}' created with priority {priority}"

    @pytest.mark.parametrize(
        "invalid_description",
        [
            "",
        ],
    )
    def test_create_task_empty_description_raises_value_error(
        self, service, invalid_description
    ):
        """Проверяет, что метод выбрасывает ValueError при пустом описании."""
        with pytest.raises(ValueError, match="Description cannot be empty"):
            service.create_task(invalid_description, 1)

    @pytest.mark.parametrize(
        "invalid_priority",
        [
            0,
            -1,
            6,
            10,
        ],
    )
    def test_create_task_invalid_priority_raises_value_error(
        self, service, invalid_priority
    ):
        """Проверяет, что метод выбрасывает ValueError при некорректном приорите."""
        with pytest.raises(ValueError, match="Priority must be between 1 and 5"):
            service.create_task("Valid description", invalid_priority)

    def test_create_task_task_parameter_is_unused(self, service):
        """Проверяет, что параметр task не влияет на поведение метода."""
        with patch.object(service.manager, "add_task") as mock_add_task:
            task_mock = MagicMock()
            result = service.create_task("Task with task param", 3, task=task_mock)
            mock_add_task.assert_called_once_with("Task with task param", 3)
            assert result == "Task 'Task with task param' created with priority 3"
