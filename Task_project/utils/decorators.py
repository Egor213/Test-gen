def deco(func):
    def inner(*args, **kwargs):
        print("DECO!!")
        return func(*args, **kwargs)
    return inner


def utils_func():
    return "1"