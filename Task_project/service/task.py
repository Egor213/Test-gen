from managers.task import TaskManager
from entity.entity import Task

class TaskService:
    field: str
    def __init__(self):
        self.manager = TaskManager()

    def create_task(self, description: str, priority: int, task: Task | None = None):
        if not description:
            raise ValueError("Description cannot be empty")

        if priority < 1 or priority > 5:
            raise ValueError("Priority must be between 1 and 5")
        
        a = Task("descr", 1)
        a.mark_completed()
        self.manager.add_task(description, priority)
        a.test_method()
        return f"Task '{description}' created with priority {priority}"

    def complete_task(self, description: str):
        '''
        HELLO WORLD!
        '''
        task = self.manager.get_task(description)
        if not task:
            return f"Task '{description}' not found"

        self.manager.mark_task_completed(description)
        return f"Task '{description}' marked as completed"

    def show_all(self):
        return self.manager.tasks

    def pending_count(self):
        return self.manager.count_pending_tasks()

    def completed_count(self):
        return self.manager.count_completed_tasks()

    def save(self, filename="tasks.txt"):
        self.manager.save_tasks_to_file(filename)
        return f"Tasks saved to {filename}"

    def load(self, filename="tasks.txt"):
        self.manager.load_tasks_from_file(filename)
        return f"Tasks loaded from {filename}"
