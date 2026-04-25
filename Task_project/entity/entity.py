
class Base:
    haha: str
    trrrr: list = list()
    def __init__(self):
        self.test = 1

class BaseTask(Base):
    pass

from dataclasses import dataclass

@dataclass
class Task(BaseTask):
    field: str

    
    def __init__(self, description, priority):
        self.description = description
        self.priority = priority
        self.completed = False

    def mark_completed(self):
        self.completed = True

    def test_method(self, test):
        self.completed = True

    def __str__(self):
        status = "Completed" if self.completed else "Pending"
        return f"Task: {self.description}, Priority: {self.priority}, Status: {status}"
