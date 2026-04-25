from service import TaskService as test
from utils.decorators import deco as decoTest
import entity.entity as e
from entity import entity
from test import * 
import utils.decorators as t

@decoTest
def main():
    service = test()
    entity.Task("123", 1)
    e.Task("test", "test")
    service.create_task("Buy milk", 2)
    service.create_task("Write report", 1)
    print(service.pending_count())  # 2

    service.complete_task("Buy milk")

    service.save("tasks.txt")
    service.load("tasks.txt")
    for t in service.show_all():
        print(t)

if __name__ == '__main__':
    main()