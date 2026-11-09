import pytest
from calculator import add, divide, calculate_discount, find_median

def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0

def test_divide_zero_raises_value_error():
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(10, 0)

def test_calculate_discount():
    assert calculate_discount(100.0, 20.0) == 80.0
    assert calculate_discount(50.0, 10.0) == 45.0
    assert calculate_discount(200.0, 0.0) == 200.0

def test_find_median_unsorted():
    assert find_median([5, 1, 3]) == 3.0
    assert find_median([7, 2, 9, 4]) == 5.5

def test_find_median_empty():
    with pytest.raises(ValueError):
        find_median([])
