# Simple Python Project

import math
import random
import datetime

class Calculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

    def multiply(self, a, b):
        return a * b

    def divide(self, a, b):
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b

    def add_divide(self, a, b):
        return a + b

def generate_random_number():
    return random.randint(1, 100)

def calculate_factorial(n):
    if n < 0:
        raise ValueError("Factorial is not defined for negative numbers")
    return math.factorial(n)

def get_current_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def main():
    print("Welcome to the Simple Python Project!")
    print("Current time:", get_current_time())

    calc = Calculator()
    print("Calculator operations:")
    print("Addition: 5 + 3 =", calc.add(5, 3))
    print("Subtraction: 10 - 4 =", calc.subtract(10, 4))
    print("Multiplication: 6 * 7 =", calc.multiply(6, 7))
    print("Division: 20 / 4 =", calc.divide(20, 4))

    print("Random number between 1 and 100:", generate_random_number())

    try:
        print("Factorial of 5:", calculate_factorial(5))
        print("Factorial of -3:", calculate_factorial(-3))
    except ValueError as e:
        print("Error:", e)

    print("This script is part of a simple Python project.")
    print("It demonstrates basic Python functionality including classes, functions, and error handling.")
    print("The project is designed to be a starting point for further development and learning.")

if __name__ == "__main__":
    main()
