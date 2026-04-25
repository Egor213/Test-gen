from unittest.mock import MagicMock, patch

from service.task import TaskService
import pytest


class TestTaskServiceCreateTask:

    @pytest.fixture
    def task_service(self):
        return TaskService()

    @pytest.mark.parametrize('description, priority', [('Buy milk', 1), ('Write report', 3), ('Deploy service', 5), ('A', 2), ('Task with spaces', 4)])
    def test_create_task_valid_inputs_returns_expected_message(self, task_service, description, priority):
        """Проверяет, что create_task возвращает корректное сообщение при валидных входных данных."""
        with patch.object(task_service.manager, 'add_task') as mock_add:
            result = task_service.create_task(description, priority)
            assert result == f"Task '{description}' created with priority {priority}"
            mock_add.assert_called_once_with(description, priority)

    @pytest.mark.parametrize('invalid_description', [''])
    def test_create_task_empty_description_raises_value_error(self, task_service, invalid_description):
        """Проверяет, что create_task выбрасывает ValueError при пустом описании."""
        with pytest.raises(ValueError, match='Description cannot be empty'):
            task_service.create_task(invalid_description, 1)

    @pytest.mark.parametrize('invalid_priority', [0, -1, 6, 10])
    def test_create_task_invalid_priority_raises_value_error(self, task_service, invalid_priority):
        """Проверяет, что create_task выбрасывает ValueError при недопустимом приоритете."""
        with pytest.raises(ValueError, match='Priority must be between 1 and 5'):
            task_service.create_task('Valid task', invalid_priority)

    def test_create_task_creates_and_marks_internal_task(self, task_service):
        """Проверяет, что create_task создаёт внутренний Task и вызывает его mark_completed."""
        with patch('service.task.Task') as MockTask:
            mock_instance = MagicMock()
            MockTask.return_value = mock_instance
            task_service.create_task('Test', 2)
            MockTask.assert_called_once_with('descr', 1)
            mock_instance.mark_completed.assert_called_once()

    def test_create_task_with_explicit_none_task_ignores_task_param(self, task_service):
        """Проверяет, что при передаче task=None логика остаётся корректной и не ломается."""
        with patch.object(task_service.manager, 'add_task') as mock_add:
            result = task_service.create_task('Test', 1, task=None)
            assert result == "Task 'Test' created with priority 1"
            mock_add.assert_called_once_with('Test', 1)

    def test_create_task_side_effect_on_manager_tasks(self, task_service):
        """Проверяет побочный эффект: после create_task в менеджере появляется задача."""
        task_service.create_task('Side effect task', 4)
        assert len(task_service.manager.tasks) == 1
        added = task_service.manager.tasks[0]
        assert added.description == 'Side effect task'
        assert added.priority == 4
