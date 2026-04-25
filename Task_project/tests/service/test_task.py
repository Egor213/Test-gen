from unittest.mock import patch

from entity.entity import Task
from service.task import TaskService
import pytest


class TestTaskServiceCreateTask:
    @pytest.fixture
    def task_service(self):
        return TaskService()

    @pytest.mark.parametrize(
        "description, priority, expected_error, expected_message",
        [
            ("", 3, ValueError, "Description cannot be empty"),
            ("Valid Task", 0, ValueError, "Priority must be between 1 and 5"),
            ("Valid Task", 6, ValueError, "Priority must be between 1 and 5"),
        ],
    )
    def test_create_task_validation_errors(
        self, task_service, description, priority, expected_error, expected_message
    ):
        """Проверка выброса исключений при невалидных входных данных."""
        with pytest.raises(expected_error, match=expected_message):
            task_service.create_task(description, priority)

    @pytest.mark.parametrize(
        "priority",
        [1, 2, 3, 4, 5],
    )
    def test_create_task_valid_priorities(self, task_service, priority):
        """Проверка успешного создания задачи при валидных приоритетах."""
        description = "Test Task"
        with patch.object(task_service.manager, "add_task") as mock_add_task:
            result = task_service.create_task(description, priority)
            mock_add_task.assert_called_once_with(description, priority)
            assert result == f"Task '{description}' created with priority {priority}"

    def test_create_task_calls_internal_task_operations(self, task_service):
        """Проверка вызова внутренних методов Task внутри create_task."""
        description = "Internal Check Task"
        priority = 3
        with patch.object(task_service.manager, "add_task"):
            with patch.object(Task, "mark_completed") as mock_mark_completed:
                task_service.create_task(description, priority)
                mock_mark_completed.assert_called_once()
