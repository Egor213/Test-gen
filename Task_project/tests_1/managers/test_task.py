from unittest.mock import MagicMock, Mock, call, mock_open, patch

from entity.entity import Task
from managers.task import TaskManager
import pytest


class TestTaskManager:
    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    @pytest.mark.parametrize("description, priority", [
        ("Test task", 2),
        ("Another task", 5),
        ("", 1),
        ("Task with special chars !@#", 3),
        ("Long description " + "x" * 1000, 4)
    ])
    def test_add_task(self, task_manager, description, priority):
        """Тест добавления задачи с различными описаниями и приоритетами"""
        task_manager.add_task(description, priority)
        assert len(task_manager.tasks) == 1
        assert task_manager.tasks[0].description == description
        assert task_manager.tasks[0].priority == priority

    @pytest.mark.parametrize("description, priority, expected_exception", [
        ("Valid task", 2, None),
        ("", 1, None),  # Пустое описание допустимо
        ("Task", 0, None),  # Приоритет 0 допустим
        ("Task", 6, None)  # Приоритет 6 допустим
    ])
    def test_add_task_no_exceptions(self, task_manager, description, priority, expected_exception):
        """Тест, что метод add_task не вызывает исключений для различных входных данных"""
        try:
            task_manager.add_task(description, priority)
        except Exception as e:
            if expected_exception is not None:
                assert isinstance(e, expected_exception)
            else:
                pytest.fail(f"Unexpected exception: {e}")

    def test_add_task_multiple_tasks(self, task_manager):
        """Тест добавления нескольких задач"""
        task_manager.add_task("Task 1", 1)
        task_manager.add_task("Task 2", 3)
        task_manager.add_task("Task 3", 5)

        assert len(task_manager.tasks) == 3
        assert task_manager.tasks[0].description == "Task 1"
        assert task_manager.tasks[1].description == "Task 2"
        assert task_manager.tasks[2].description == "Task 3"

    @patch('managers.task.Task')
    def test_add_task_calls_task_constructor(self, mock_task, task_manager):
        """Тест, что add_task создает экземпляр Task с правильными параметрами"""
        task_manager.add_task("Test task", 2)
        mock_task.assert_called_once_with("Test task", 2)

    def test_add_task_task_added_to_list(self, task_manager):
        """Тест, что созданная задача добавляется в список задач"""
        task_manager.add_task("Test task", 2)
        assert len(task_manager.tasks) == 1
        assert isinstance(task_manager.tasks[0], Task)


class TestTaskManager:
    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    @pytest.fixture
    def task(self):
        task = MagicMock()
        task.description = "Test Task"
        task.priority = 1
        return task

    @pytest.fixture
    def populated_task_manager(self, task):
        manager = TaskManager()
        manager.tasks = [task]
        return manager

    @pytest.mark.parametrize("description, expected", [
        ("Test Task", "Test Task"),
        ("Non-existent", None),
    ])
    def test_get_task(self, populated_task_manager, description, expected):
        """Тест получения задачи по описанию"""
        result = populated_task_manager.get_task(description)
        if expected is None:
            assert result is None
        else:
            assert result.description == expected

    def test_get_task_multiple_tasks(self, task_manager):
        """Тест получения задачи из списка задач"""
        task1 = MagicMock()
        task1.description = "Task 1"
        task2 = MagicMock()
        task2.description = "Task 2"
        task_manager.tasks = [task1, task2]

        result = task_manager.get_task("Task 1")
        assert result == task1

        result = task_manager.get_task("Task 2")
        assert result == task2

        result = task_manager.get_task("Non-existent")
        assert result is None

    def test_get_task_empty_list(self, task_manager):
        """Тест получения задачи из пустого списка"""
        result = task_manager.get_task("Any task")
        assert result is None


class TestTaskManagerMarkTaskCompleted:
    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    @pytest.fixture
    def sample_task(self):
        return Task(description="Test task", priority=1)

    def test_marks_existing_task_as_completed(self, task_manager, sample_task):
        """Тест отметки существующей задачи как выполненной"""
        task_manager.tasks.append(sample_task)
        task_manager.mark_task_completed("Test task")
        assert sample_task.completed is True

    def test_does_nothing_for_non_existent_task(self, task_manager, sample_task):
        """Тест попытки отметить несуществующую задачу"""
        task_manager.tasks.append(sample_task)
        task_manager.mark_task_completed("Non-existent task")
        assert sample_task.completed is False

    def test_marks_first_matching_task(self, task_manager):
        """Тест отметки первой найденной задачи при дублировании описаний"""
        task1 = Task(description="Duplicate", priority=1)
        task2 = Task(description="Duplicate", priority=2)
        task_manager.tasks.extend([task1, task2])
        task_manager.mark_task_completed("Duplicate")
        assert task1.completed is True
        assert task2.completed is False

    def test_breaks_after_first_match(self, task_manager):
        """Тест выхода из цикла после первого совпадения"""
        task1 = Task(description="Test", priority=1)
        task2 = Task(description="Test", priority=2)
        task_manager.tasks.extend([task1, task2])
        task_manager.mark_task_completed("Test")
        assert task1.completed is True
        assert task2.completed is False

    def test_handles_empty_task_list(self, task_manager):
        """Тест работы с пустым списком задач"""
        task_manager.mark_task_completed("Any task")
        assert len(task_manager.tasks) == 0

    def test_case_sensitive_matching(self, task_manager, sample_task):
        """Тест чувствительности к регистру в описании задачи"""
        task_manager.tasks.append(sample_task)
        task_manager.mark_task_completed("test task")
        assert sample_task.completed is False


class TestTaskManager:

    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    @pytest.mark.parametrize('tasks, expected_output', [([], ''), (['Task 1'], 'Task 1\n'), (['Task 1', 'Task 2'], 'Task 1\nTask 2\n')])
    def test_list_tasks(self, task_manager, tasks, expected_output, capsys):
        """Тест метода list_tasks для различных наборов задач"""
        task_manager.tasks = tasks
        task_manager.list_tasks()
        captured = capsys.readouterr()
        assert captured.out == expected_output

    def test_list_tasks_with_empty_tasks(self, task_manager, capsys):
        """Тест метода list_tasks с пустым списком задач"""
        task_manager.tasks = []
        task_manager.list_tasks()
        captured = capsys.readouterr()
        assert captured.out == ''

    def test_list_tasks_with_single_task(self, task_manager, capsys):
        """Тест метода list_tasks с одной задачей"""
        task_manager.tasks = ['Single Task']
        task_manager.list_tasks()
        captured = capsys.readouterr()
        assert captured.out == 'Single Task\n'


class TestTaskManagerListPendingTasks:
    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    @pytest.fixture
    def task_with_mock(self):
        task = MagicMock()
        task.completed = False
        return task

    @pytest.fixture
    def completed_task_with_mock(self):
        task = MagicMock()
        task.completed = True
        return task

    @pytest.fixture
    def task_with_mock_2(self):
        task = MagicMock()
        task.completed = False
        return task

    def test_list_pending_tasks_prints_only_uncompleted_tasks(self, task_manager, task_with_mock, completed_task_with_mock, capsys):
        """Тест, что метод list_pending_tasks выводит только незавершенные задачи"""
        task_manager.tasks = [task_with_mock, completed_task_with_mock]
        task_manager.list_pending_tasks()
        captured = capsys.readouterr()
        assert captured.out.strip() == str(task_with_mock)

    def test_list_pending_tasks_prints_nothing_when_no_pending_tasks(self, task_manager, completed_task_with_mock, capsys):
        """Тест, что метод list_pending_tasks ничего не выводит, если нет незавершенных задач"""
        task_manager.tasks = [completed_task_with_mock]
        task_manager.list_pending_tasks()
        captured = capsys.readouterr()
        assert captured.out.strip() == ""

    def test_list_pending_tasks_prints_all_pending_tasks(self, task_manager, task_with_mock, task_with_mock_2, capsys):
        """Тест, что метод list_pending_tasks выводит все незавершенные задачи"""
        task_manager.tasks = [task_with_mock, task_with_mock_2]
        task_manager.list_pending_tasks()
        captured = capsys.readouterr()
        assert captured.out.strip() == f"{str(task_with_mock)}\n{str(task_with_mock_2)}"

    def test_list_pending_tasks_handles_empty_task_list(self, task_manager, capsys):
        """Тест, что метод list_pending_tasks корректно работает с пустым списком задач"""
        task_manager.tasks = []
        task_manager.list_pending_tasks()
        captured = capsys.readouterr()
        assert captured.out.strip() == ""

    def test_list_pending_tasks_prints_tasks_in_order(self, task_manager, task_with_mock, task_with_mock_2, capsys):
        """Тест, что метод list_pending_tasks выводит задачи в порядке добавления"""
        task_manager.tasks = [task_with_mock, task_with_mock_2]
        task_manager.list_pending_tasks()
        captured = capsys.readouterr()
        assert captured.out.strip() == f"{str(task_with_mock)}\n{str(task_with_mock_2)}"


class TestTaskManager:
    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    @pytest.fixture
    def task_with_completed(self):
        class Task:
            def __init__(self, description, completed):
                self.description = description
                self.completed = completed
            def __str__(self):
                return f"Task(description={self.description}, completed={self.completed})"
        return Task

    @pytest.mark.parametrize("tasks,expected_output", [
        ([], ""),
        ([{"description": "Task 1", "completed": True}], "Task(description=Task 1, completed=True)\n"),
        ([{"description": "Task 1", "completed": False}], ""),
        ([{"description": "Task 1", "completed": True}, {"description": "Task 2", "completed": False}], "Task(description=Task 1, completed=True)\n"),
        ([{"description": "Task 1", "completed": False}, {"description": "Task 2", "completed": True}], "Task(description=Task 2, completed=True)\n"),
        ([{"description": "Task 1", "completed": True}, {"description": "Task 2", "completed": True}], "Task(description=Task 1, completed=True)\nTask(description=Task 2, completed=True)\n"),
    ])
    def test_list_completed_tasks(self, task_manager, task_with_completed, tasks, expected_output):
        """Тест метода list_completed_tasks для различных комбинаций задач"""
        for task_data in tasks:
            task = task_with_completed(task_data["description"], task_data["completed"])
            task_manager.tasks.append(task)

        with patch('builtins.print') as mocked_print:
            task_manager.list_completed_tasks()
            assert mocked_print.call_count == sum(1 for t in tasks if t["completed"])

    def test_list_completed_tasks_no_completed_tasks(self, task_manager, task_with_completed):
        """Тест метода list_completed_tasks когда нет завершенных задач"""
        task_manager.tasks.append(task_with_completed("Task 1", False))
        task_manager.tasks.append(task_with_completed("Task 2", False))

        with patch('builtins.print') as mocked_print:
            task_manager.list_completed_tasks()
            assert mocked_print.call_count == 0

    def test_list_completed_tasks_all_tasks_completed(self, task_manager, task_with_completed):
        """Тест метода list_completed_tasks когда все задачи завершены"""
        task_manager.tasks.append(task_with_completed("Task 1", True))
        task_manager.tasks.append(task_with_completed("Task 2", True))

        with patch('builtins.print') as mocked_print:
            task_manager.list_completed_tasks()
            assert mocked_print.call_count == 2


class TestTaskManagerRemoveTask:
    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    def test_remove_task_existing_task(self, task_manager):
        """Тест удаления существующей задачи"""
        # Создаем тестовые задачи
        task_manager.tasks = [
            Mock(description="Task 1"),
            Mock(description="Task 2"),
            Mock(description="Task 3")
        ]

        # Удаляем одну задачу
        task_manager.remove_task("Task 2")

        # Проверяем результат
        assert len(task_manager.tasks) == 2
        descriptions = [task.description for task in task_manager.tasks]
        assert "Task 2" not in descriptions
        assert "Task 1" in descriptions
        assert "Task 3" in descriptions

    def test_remove_task_non_existent(self, task_manager):
        """Тест удаления несуществующей задачи"""
        # Создаем тестовые задачи
        task_manager.tasks = [
            Mock(description="Task 1"),
            Mock(description="Task 2")
        ]

        # Пытаемся удалить несуществующую задачу
        task_manager.remove_task("Non-existent")

        # Список задач должен остаться без изменений
        assert len(task_manager.tasks) == 2
        descriptions = [task.description for task in task_manager.tasks]
        assert "Task 1" in descriptions
        assert "Task 2" in descriptions

    def test_remove_task_empty_list(self, task_manager):
        """Тест удаления задачи из пустого списка"""
        # Список задач изначально пуст
        task_manager.tasks = []

        # Пытаемся удалить задачу
        task_manager.remove_task("Any task")

        # Список должен остаться пустым
        assert len(task_manager.tasks) == 0

    def test_remove_task_multiple_occurrences(self, task_manager):
        """Тест удаления задачи при наличии нескольких одинаковых задач"""
        # Создаем несколько задач с одинаковым описанием
        task_manager.tasks = [
            Mock(description="Task 1"),
            Mock(description="Task 2"),
            Mock(description="Task 2"),
            Mock(description="Task 3")
        ]

        # Удаляем задачу с описанием "Task 2"
        task_manager.remove_task("Task 2")

        # Должны удалиться все задачи с этим описанием
        assert len(task_manager.tasks) == 2
        descriptions = [task.description for task in task_manager.tasks]
        assert "Task 2" not in descriptions
        assert "Task 1" in descriptions
        assert "Task 3" in descriptions

    def test_remove_task_case_sensitivity(self, task_manager):
        """Тест удаления задачи с учетом регистра"""
        # Создаем задачи с разным регистром
        task_manager.tasks = [
            Mock(description="Task 1"),
            Mock(description="task 1"),
            Mock(description="TASK 1")
        ]

        # Удаляем задачу с определенным регистром
        task_manager.remove_task("task 1")

        # Должна удалиться только задача с точным совпадением регистра
        assert len(task_manager.tasks) == 2
        descriptions = [task.description for task in task_manager.tasks]
        assert "task 1" not in descriptions
        assert "Task 1" in descriptions
        assert "TASK 1" in descriptions


class TestTaskManagerUpdateTaskPriority:
    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    @pytest.fixture
    def task(self):
        task = Mock()
        task.description = "Test Task"
        task.priority = 1
        return task

    def test_update_existing_task_priority(self, task_manager, task):
        """Тест обновления приоритета существующей задачи"""
        task_manager.tasks = [task]
        task_manager.update_task_priority("Test Task", 5)
        assert task.priority == 5

    def test_update_non_existing_task_priority(self, task_manager, task):
        """Тест обновления приоритета несуществующей задачи"""
        task_manager.tasks = [task]
        task_manager.update_task_priority("Non-existent Task", 5)
        assert task.priority == 1

    def test_update_priority_with_multiple_tasks(self, task_manager):
        """Тест обновления приоритета при наличии нескольких задач"""
        task1 = Mock()
        task1.description = "Task 1"
        task1.priority = 1

        task2 = Mock()
        task2.description = "Task 2"
        task2.priority = 2

        task_manager.tasks = [task1, task2]
        task_manager.update_task_priority("Task 1", 5)

        assert task1.priority == 5
        assert task2.priority == 2

    def test_update_priority_with_same_priority(self, task_manager, task):
        """Тест обновления приоритета на тот же самый приоритет"""
        task_manager.tasks = [task]
        task_manager.update_task_priority("Test Task", 1)
        assert task.priority == 1

    def test_update_priority_with_negative_value(self, task_manager, task):
        """Тест обновления приоритета на отрицательное значение"""
        task_manager.tasks = [task]
        task_manager.update_task_priority("Test Task", -5)
        assert task.priority == -5

    def test_update_priority_with_zero(self, task_manager, task):
        """Тест обновления приоритета на ноль"""
        task_manager.tasks = [task]
        task_manager.update_task_priority("Test Task", 0)
        assert task.priority == 0

    def test_update_priority_with_large_value(self, task_manager, task):
        """Тест обновления приоритета на большое значение"""
        task_manager.tasks = [task]
        task_manager.update_task_priority("Test Task", 999999)
        assert task.priority == 999999


class TestTaskManagerSortTasksByPriority:
    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    def test_sort_tasks_by_priority_empty_list(self, task_manager):
        """Тест сортировки пустого списка задач"""
        task_manager.sort_tasks_by_priority()
        assert task_manager.tasks == []

    def test_sort_tasks_by_priority_single_task(self, task_manager):
        """Тест сортировки списка с одной задачей"""
        task_manager.add_task("Single task", 1)
        task_manager.sort_tasks_by_priority()
        assert len(task_manager.tasks) == 1
        assert task_manager.tasks[0].priority == 1

    def test_sort_tasks_by_priority_multiple_tasks(self, task_manager):
        """Тест сортировки списка с несколькими задачами"""
        task_manager.add_task("Task 3", 3)
        task_manager.add_task("Task 1", 1)
        task_manager.add_task("Task 2", 2)

        task_manager.sort_tasks_by_priority()

        assert task_manager.tasks[0].priority == 1
        assert task_manager.tasks[1].priority == 2
        assert task_manager.tasks[2].priority == 3

    def test_sort_tasks_by_priority_already_sorted(self, task_manager):
        """Тест сортировки уже отсортированного списка"""
        task_manager.add_task("Task 1", 1)
        task_manager.add_task("Task 2", 2)
        task_manager.add_task("Task 3", 3)

        task_manager.sort_tasks_by_priority()

        assert task_manager.tasks[0].priority == 1
        assert task_manager.tasks[1].priority == 2
        assert task_manager.tasks[2].priority == 3

    def test_sort_tasks_by_priority_reverse_order(self, task_manager):
        """Тест сортировки списка в обратном порядке"""
        task_manager.add_task("Task 3", 3)
        task_manager.add_task("Task 2", 2)
        task_manager.add_task("Task 1", 1)

        task_manager.sort_tasks_by_priority()

        assert task_manager.tasks[0].priority == 1
        assert task_manager.tasks[1].priority == 2
        assert task_manager.tasks[2].priority == 3

    def test_sort_tasks_by_priority_same_priority(self, task_manager):
        """Тест сортировки задач с одинаковым приоритетом"""
        task_manager.add_task("Task A", 1)
        task_manager.add_task("Task B", 1)
        task_manager.add_task("Task C", 1)

        task_manager.sort_tasks_by_priority()

        assert task_manager.tasks[0].priority == 1
        assert task_manager.tasks[1].priority == 1
        assert task_manager.tasks[2].priority == 1

    def test_sort_tasks_by_priority_mixed_priorities(self, task_manager):
        """Тест сортировки задач с разными приоритетами"""
        task_manager.add_task("High", 3)
        task_manager.add_task("Low", 1)
        task_manager.add_task("Medium", 2)
        task_manager.add_task("Lowest", 1)
        task_manager.add_task("Highest", 3)

        task_manager.sort_tasks_by_priority()

        assert task_manager.tasks[0].priority == 1
        assert task_manager.tasks[1].priority == 1
        assert task_manager.tasks[2].priority == 2
        assert task_manager.tasks[3].priority == 3
        assert task_manager.tasks[4].priority == 3


class TestTaskManager:
    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    @pytest.mark.parametrize("priority, expected_count", [
        (1, 0),
        (2, 0),
        (3, 0),
        (5, 0),
        (-1, 0),
    ])
    def test_filter_tasks_by_priority_empty_manager(self, task_manager, priority, expected_count):
        """Тест фильтрации задач по приоритету в пустом менеджере"""
        result = task_manager.filter_tasks_by_priority(priority)
        assert len(result) == expected_count

    @pytest.mark.parametrize("priority, expected_count", [
        (1, 1),
        (2, 2),
        (3, 1),
        (4, 0),
        (0, 0),
    ])
    def test_filter_tasks_by_priority_with_tasks(self, task_manager, priority, expected_count):
        """Тест фильтрации задач по приоритету с существующими задачами"""
        # Добавляем задачи
        task_manager.tasks = [
            type('', (), {'priority': 1})(),
            type('', (), {'priority': 2})(),
            type('', (), {'priority': 2})(),
            type('', (), {'priority': 3})(),
        ]

        result = task_manager.filter_tasks_by_priority(priority)

        assert len(result) == expected_count
        assert all(task.priority == priority for task in result)

    def test_filter_tasks_by_priority_all_priorities(self, task_manager):
        """Тест фильтрации задач по всем возможным приоритетам"""
        # Добавляем задачи с разными приоритетами
        task_manager.tasks = [
            type('', (), {'priority': 1})(),
            type('', (), {'priority': 2})(),
            type('', (), {'priority': 2})(),
            type('', (), {'priority': 3})(),
        ]

        # Проверяем каждый приоритет
        for priority in [1, 2, 3]:
            result = task_manager.filter_tasks_by_priority(priority)
            assert all(task.priority == priority for task in result)

    def test_filter_tasks_by_priority_no_matching_priority(self, task_manager):
        """Тест фильтрации задач когда нет задач с указанным приоритетом"""
        # Добавляем задачи только с приоритетом 1 и 2
        task_manager.tasks = [
            type('', (), {'priority': 1})(),
            type('', (), {'priority': 2})(),
            type('', (), {'priority': 2})(),
        ]

        # Проверяем приоритет 3 (которого нет)
        result = task_manager.filter_tasks_by_priority(3)
        assert len(result) == 0

    def test_filter_tasks_by_priority_negative_priority(self, task_manager):
        """Тест фильтрации задач с отрицательным приоритетом"""
        # Добавляем задачи с отрицательным приоритетом
        task_manager.tasks = [
            type('', (), {'priority': -1})(),
            type('', (), {'priority': 2})(),
            type('', (), {'priority': -1})(),
        ]

        result = task_manager.filter_tasks_by_priority(-1)
        assert len(result) == 2
        assert all(task.priority == -1 for task in result)


class TestTaskManager:
    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    @pytest.fixture
    def task_manager_with_tasks(self):
        manager = TaskManager()
        manager.tasks = [
            MagicMock(completed=False),
            MagicMock(completed=True),
            MagicMock(completed=False),
            MagicMock(completed=False),
            MagicMock(completed=True)
        ]
        return manager

    @pytest.mark.parametrize("tasks, expected_count", [
        ([], 0),
        ([MagicMock(completed=True)], 0),
        ([MagicMock(completed=False)], 1),
        ([MagicMock(completed=False), MagicMock(completed=True), MagicMock(completed=False)], 2),
        ([MagicMock(completed=True), MagicMock(completed=True), MagicMock(completed=True)], 0),
        ([MagicMock(completed=False), MagicMock(completed=False), MagicMock(completed=False)], 3),
    ])
    def test_count_pending_tasks(self, task_manager, tasks, expected_count):
        """Тест подсчета незавершенных задач с различными комбинациями"""
        task_manager.tasks = tasks
        result = task_manager.count_pending_tasks()
        assert result == expected_count

    def test_count_pending_tasks_empty_manager(self, task_manager):
        """Тест подсчета незавершенных задач в пустом менеджере"""
        result = task_manager.count_pending_tasks()
        assert result == 0

    def test_count_pending_tasks_all_completed(self, task_manager):
        """Тест подсчета незавершенных задач когда все задачи завершены"""
        task_manager.tasks = [
            MagicMock(completed=True),
            MagicMock(completed=True),
            MagicMock(completed=True)
        ]
        result = task_manager.count_pending_tasks()
        assert result == 0

    def test_count_pending_tasks_all_pending(self, task_manager):
        """Тест подсчета незавершенных задач когда все задачи незавершены"""
        task_manager.tasks = [
            MagicMock(completed=False),
            MagicMock(completed=False),
            MagicMock(completed=False)
        ]
        result = task_manager.count_pending_tasks()
        assert result == 3

    def test_count_pending_tasks_mixed_tasks(self, task_manager_with_tasks):
        """Тест подсчета незавершенных задач с разными статусами"""
        result = task_manager_with_tasks.count_pending_tasks()
        assert result == 3


class TestTaskManager:
    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    @pytest.fixture
    def populated_task_manager(self):
        manager = TaskManager()
        manager.tasks = [
            type('Task', (), {'completed': True})(),
            type('Task', (), {'completed': False})(),
            type('Task', (), {'completed': True})(),
            type('Task', (), {'completed': False})()
        ]
        return manager

    @pytest.mark.parametrize("tasks, expected_count", [
        ([], 0),
        ([type('Task', (), {'completed': True})()], 1),
        ([type('Task', (), {'completed': False})()], 0),
        ([type('Task', (), {'completed': True})(), type('Task', (), {'completed': False})()], 1),
        ([type('Task', (), {'completed': True})(), type('Task', (), {'completed': True})()], 2),
        ([type('Task', (), {'completed': False})(), type('Task', (), {'completed': False})()], 0),
    ])
    def test_count_completed_tasks(self, task_manager, tasks, expected_count):
        """Тест подсчета завершенных задач"""
        task_manager.tasks = tasks
        assert task_manager.count_completed_tasks() == expected_count

    def test_count_completed_tasks_with_populated_manager(self, populated_task_manager):
        """Тест подсчета завершенных задач в предзаполненном менеджере"""
        assert populated_task_manager.count_completed_tasks() == 2


class TestTaskManagerClearAllTasks:
    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    def test_clear_all_tasks_empty_list(self, task_manager):
        """Тест очистки списка задач, когда он уже пуст"""
        task_manager.clear_all_tasks()
        assert len(task_manager.tasks) == 0

    def test_clear_all_tasks_with_tasks(self, task_manager):
        """Тест очистки списка задач, когда в нем есть элементы"""
        # Добавляем несколько задач
        task_manager.tasks.append({"description": "Task 1", "priority": 1})
        task_manager.tasks.append({"description": "Task 2", "priority": 2})
        task_manager.tasks.append({"description": "Task 3", "priority": 3})

        # Очищаем все задачи
        task_manager.clear_all_tasks()

        # Проверяем, что список задач пуст
        assert len(task_manager.tasks) == 0

    def test_clear_all_tasks_with_one_task(self, task_manager):
        """Тест очистки списка задач, когда в нем только одна задача"""
        task_manager.tasks.append({"description": "Single task", "priority": 1})

        task_manager.clear_all_tasks()

        assert len(task_manager.tasks) == 0

    def test_clear_all_tasks_preserves_task_manager_instance(self, task_manager):
        """Тест, что clear_all_tasks не заменяет объект TaskManager"""
        original_id = id(task_manager)
        task_manager.tasks.append({"description": "Task", "priority": 1})

        task_manager.clear_all_tasks()

        assert id(task_manager) == original_id
        assert len(task_manager.tasks) == 0


class TestTaskManager:
    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    @pytest.fixture
    def mock_tasks(self):
        class MockTask:
            def __init__(self, description, priority, completed):
                self.description = description
                self.priority = priority
                self.completed = completed

        return [
            MockTask("Task 1", 1, True),
            MockTask("Task 2", 2, False),
            MockTask("Task 3", 3, True)
        ]

    @pytest.mark.parametrize("filename, expected_calls", [
        ("tasks.txt", ["Task 1,1,True\n", "Task 2,2,False\n", "Task 3,3,True\n"]),
        ("test_tasks.txt", ["Task 1,1,True\n", "Task 2,2,False\n", "Task 3,3,True\n"]),
        ("", ["Task 1,1,True\n", "Task 2,2,False\n", "Task 3,3,True\n"]),
    ])
    def test_save_tasks_to_file(self, task_manager, mock_tasks, filename, expected_calls):
        """Тест сохранения задач в файл"""
        task_manager.tasks = mock_tasks

        with patch("builtins.open", mock_open()) as mock_file:
            task_manager.save_tasks_to_file(filename)

            mock_file.assert_called_once_with(filename, 'w')
            mock_file().write.assert_has_calls([call(expected_call) for expected_call in expected_calls])

    @pytest.mark.parametrize("filename", [
        "tasks.txt",
        "test_tasks.txt",
        "path/to/tasks.txt",
        "tasks_with_long_name.txt",
        "tasks_with_special_chars!@#.txt"
    ])
    def test_save_tasks_to_file_different_filenames(self, task_manager, mock_tasks, filename):
        """Тест сохранения задач в файл с разными именами файлов"""
        task_manager.tasks = mock_tasks

        with patch("builtins.open", mock_open()) as mock_file:
            task_manager.save_tasks_to_file(filename)

            mock_file.assert_called_once_with(filename, 'w')
            mock_file().write.assert_has_calls([
                call("Task 1,1,True\n"),
                call("Task 2,2,False\n"),
                call("Task 3,3,True\n")
            ])

    def test_save_tasks_to_file_empty_tasks(self, task_manager):
        """Тест сохранения пустого списка задач в файл"""
        task_manager.tasks = []

        with patch("builtins.open", mock_open()) as mock_file:
            task_manager.save_tasks_to_file("tasks.txt")

            mock_file.assert_called_once_with("tasks.txt", 'w')
            mock_file().write.assert_not_called()

    def test_save_tasks_to_file_single_task(self, task_manager):
        """Тест сохранения одной задачи в файл"""
        class MockTask:
            def __init__(self, description, priority, completed):
                self.description = description
                self.priority = priority
                self.completed = completed

        task_manager.tasks = [MockTask("Single Task", 1, False)]

        with patch("builtins.open", mock_open()) as mock_file:
            task_manager.save_tasks_to_file("tasks.txt")

            mock_file.assert_called_once_with("tasks.txt", 'w')
            mock_file().write.assert_called_once_with("Single Task,1,False\n")

    def test_save_tasks_to_file_task_with_special_characters(self, task_manager):
        """Тест сохранения задач с особыми символами в описание"""
        class MockTask:
            def __init__(self, description, priority, completed):
                self.description = description
                self.priority = priority
                self.completed = completed

        task_manager.tasks = [
            MockTask("Task, with, commas", 1, True),
            MockTask("Task; with; semicolons", 2, False),
            MockTask("Task\nwith\nnewlines", 3, True)
        ]

        with patch("builtins.open", mock_open()) as mock_file:
            task_manager.save_tasks_to_file("tasks.txt")

            mock_file.assert_called_once_with("tasks.txt", 'w')
            mock_file().write.assert_has_calls([
                call("Task, with, commas,1,True\n"),
                call("Task; with; semicolons,2,False\n"),
                call("Task\nwith\nnewlines,3,True\n")
            ])


class TestTaskManagerLoadTasksFromFile:
    @pytest.fixture
    def task_manager(self):
        return TaskManager()

    @pytest.mark.parametrize("file_content,expected_tasks", [
        ("Task 1,1,False\nTask 2,2,True\n", [
            {"description": "Task 1", "priority": 1, "completed": False},
            {"description": "Task 2", "priority": 2, "completed": True}
        ]),
        ("", []),
        ("Task 1,1,False", [
            {"description": "Task 1", "priority": 1, "completed": False}
        ]),
        ("Task 1,1,False\nTask 2,2,True\nTask 3,3,False", [
            {"description": "Task 1", "priority": 1, "completed": False},
            {"description": "Task 2", "priority": 2, "completed": True},
            {"description": "Task 3", "priority": 3, "completed": False}
        ]),
    ])
    def test_load_tasks_from_file(self, task_manager, file_content, expected_tasks):
        """Тест загрузки задач из файла с различным содержимым"""
        mock_file = mock_open(read_data=file_content)
        with patch("builtins.open", mock_file):
            task_manager.load_tasks_from_file("dummy_filename.txt")

        assert len(task_manager.tasks) == len(expected_tasks)
        for i, expected_task in enumerate(expected_tasks):
            task = task_manager.tasks[i]
            assert task.description == expected_task["description"]
            assert task.priority == expected_task["priority"]
            assert task.completed == expected_task["completed"]

    @pytest.mark.parametrize("file_content,exception", [
        ("Task 1,1,False\nTask 2,2\n", ValueError),
        ("Task 1,1,False\nTask 2,two,True", ValueError),
        ("Task 1,1,False\nTask 2,2,True,Extra", ValueError),
    ])
    def test_load_tasks_from_file_invalid_format(self, task_manager, file_content, exception):
        """Тест загрузки задач из файла с некорректным форматом"""
        mock_file = mock_open(read_data=file_content)
        with patch("builtins.open", mock_file):
            with pytest.raises(exception):
                task_manager.load_tasks_from_file("dummy_filename.txt")

    def test_load_tasks_from_file_file_not_found(self, task_manager):
        """Тест загрузки задач из несуществующего файла"""
        with pytest.raises(FileNotFoundError):
            task_manager.load_tasks_from_file("non_existent_file.txt")

    def test_load_tasks_from_file_clears_existing_tasks(self, task_manager):
        """Тест очистки существующих задач перед загрузкой"""
        # Добавляем начальные задачи
        task_manager.tasks = [
            Task("Initial Task", 1),
            Task("Another Task", 2)
        ]

        # Загружаем из файла
        mock_file = mock_open(read_data="Task 1,1,False")
        with patch("builtins.open", mock_file):
            task_manager.load_tasks_from_file("dummy_filename.txt")

        # Проверяем, что старые задачи удалены и загружена только одна новая
        assert len(task_manager.tasks) == 1
        assert task_manager.tasks[0].description == "Task 1"
