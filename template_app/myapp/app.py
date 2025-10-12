class Task:
    def __init__(self, description, priority):
        self.description = description
        self.priority = priority
        self.completed = False

    def mark_completed(self):
        self.completed = True

    def __str__(self):
        status = "Completed" if self.completed else "Pending"
        return f"Task: {self.description}, Priority: {self.priority}, Status: {status}"

class TaskManager:
    def __init__(self):
        self.tasks = []

    def add_task(self, description, priority):
        task = Task(description, priority)
        self.tasks.append(task)

    def mark_task_completed(self, description):
        for task in self.tasks:
            if task.description == description:
                task.mark_completed()
                break

    def list_tasks(self):
        for task in self.tasks:
            print(task)

    def list_pending_tasks(self):
        for task in self.tasks:
            if not task.completed:
                print(task)

    def list_completed_tasks(self):
        for task in self.tasks:
            if task.completed:
                print(task)

    def remove_task(self, description):
        self.tasks = [task for task in self.tasks if task.description != description]

    def update_task_priority(self, description, new_priority):
        for task in self.tasks:
            if task.description == description:
                task.priority = new_priority
                break

    def sort_tasks_by_priority(self):
        self.tasks.sort(key=lambda task: task.priority)

    def filter_tasks_by_priority(self, priority):
        return [task for task in self.tasks if task.priority == priority]

    def count_pending_tasks(self):
        return sum(1 for task in self.tasks if not task.completed)

    def count_completed_tasks(self):
        return sum(1 for task in self.tasks if task.completed)

    def clear_all_tasks(self):
        self.tasks.clear()

    def save_tasks_to_file(self, filename):
        with open(filename, 'w') as file:
            for task in self.tasks:
                file.write(f"{task.description},{task.priority},{task.completed}\n")

    def load_tasks_from_file(self, filename):
        self.tasks = []
        with open(filename, 'r') as file:
            for line in file:
                description, priority, completed = line.strip().split(',')
                task = Task(description, int(priority))
                task.completed = completed == 'True'
                self.tasks.append(task)
