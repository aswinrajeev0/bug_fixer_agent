"""Buggy Calculator module for testing HealCode autonomous self-healing."""
from typing import List, Union

def add(a: float, b: float) -> float:
    return a + b

def divide(a: float, b: float) -> float:
    """Divides a by b. Raises ValueError if b is zero."""
    # BUG: Does not check for b == 0, causing ZeroDivisionError instead of raising ValueError
    return a / b

def calculate_discount(price: float, discount_percent: float) -> float:
    """Calculates final discounted price.
    
    Example:
        calculate_discount(100.0, 20.0) -> 80.0
    """
    # BUG: Calculates the discount amount rather than the final discounted price
    return price * (discount_percent / 100.0)

def find_median(numbers: List[Union[int, float]]) -> float:
    """Returns the median of a list of numbers. Raises ValueError for empty lists."""
    if not numbers:
        raise ValueError("Cannot calculate median of an empty list")
    
    # BUG: Forgets to sort the numbers before calculating median!
    n = len(numbers)
    mid = n // 2
    if n % 2 == 1:
        return float(numbers[mid])
    else:
        return float((numbers[mid - 1] + numbers[mid]) / 2.0)
