# Searching + filters (contains / starts with / ends with, AND / OR / NOT).

from config import NUMBER_COLUMNS
from sorting import run_sort, sort_key

STRING_OPS = ["contains", "starts with", "ends with", "equals"]
NUMBER_OPS = ["=", ">", "<", ">=", "<="]
SEARCH_ALGORITHMS = ["Linear Search", "Binary Search"]


def prepare_target(column, text):
    """Turn what the user typed into something we can compare."""
    text = text.strip()
    if column in NUMBER_COLUMNS:
        try:
            return float(text)
        except ValueError:
            raise ValueError("'" + text + "' is not a number")
    return text.lower()


def check(value, op, target):
    """Does one value pass the filter?"""
    if isinstance(value, str):
        value = value.lower()
    if op == "contains":
        return target in value
    if op == "starts with":
        return value.startswith(target)
    if op == "ends with":
        return value.endswith(target)
    if op in ("equals", "="):
        return value == target
    if op == ">":
        return value > target
    if op == "<":
        return value < target
    if op == ">=":
        return value >= target
    if op == "<=":
        return value <= target
    return False


def linear_search(rows, column, op, target):
    found = []
    for row in rows:                    # look at every row one by one
        if check(row[column], op, target):
            found.append(row)
    return found


def binary_search(rows, column, target):
    """Only works for exact matches. The column has to be sorted first."""
    sorted_rows = run_sort(rows, column, "Merge Sort")[0]
    keys = [sort_key(r, column) for r in sorted_rows]

    # find the first position where the key is >= target
    low, high = 0, len(keys)
    while low < high:
        mid = (low + high) // 2
        if keys[mid] < target:
            low = mid + 1
        else:
            high = mid

    found = []
    i = low
    while i < len(keys) and keys[i] == target:   # collect all the duplicates
        found.append(sorted_rows[i])
        i += 1
    return found


def search_rows(rows, conditions, algorithm):
    """conditions = [(connector, column, op, text), ...]

    Connector is "AND", "OR" or "NOT" (NOT means AND NOT). They are applied
    from left to right. Returns (matching_rows, note).
    """
    matched = None
    note = ""
    for connector, column, op, text in conditions:
        target = prepare_target(column, text)

        if algorithm == "Binary Search" and op in ("equals", "="):
            found = binary_search(rows, column, target)
        else:
            found = linear_search(rows, column, op, target)
            if algorithm == "Binary Search":
                note = " (binary search only does exact matches, used linear for the rest)"

        found_ids = {id(r) for r in found}
        if matched is None:
            matched = found_ids
        elif connector == "AND":
            matched = matched & found_ids
        elif connector == "OR":
            matched = matched | found_ids
        elif connector == "NOT":
            matched = matched - found_ids

    # keep the rows in their original order
    return [r for r in rows if id(r) in matched], note
