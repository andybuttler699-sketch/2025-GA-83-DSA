# All the sorting algorithms live here.
#
# Every algorithm sorts a list of (key, row) tuples in place and uses
# st.less(a, b) to compare, so the comparisons and swaps get counted
# automatically. "Swaps" for Insertion / Shell / Merge sort means element
# moves (shifts / writes), because those algorithms don't really swap.

import time
from config import NUMBER_COLUMNS


class Stats:
    def __init__(self, descending=False):
        self.comparisons = 0
        self.swaps = 0
        self.descending = descending

    def less(self, a, b):
        """True if a should come before b."""
        self.comparisons += 1
        if self.descending:
            return a[0] > b[0]
        return a[0] < b[0]


def sort_key(row, column):
    value = row[column]
    if column in NUMBER_COLUMNS:
        return value
    return value.lower()        # so "apple" and "Banana" sort properly


# ---------------------------------------------------------------- algorithms

def bubble_sort(arr, st):
    n = len(arr)
    for i in range(n - 1):
        swapped = False
        for j in range(n - 1 - i):
            if st.less(arr[j + 1], arr[j]):
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                st.swaps += 1
                swapped = True
        if not swapped:         # already sorted, stop early
            break


def selection_sort(arr, st):
    n = len(arr)
    for i in range(n - 1):
        smallest = i
        for j in range(i + 1, n):
            if st.less(arr[j], arr[smallest]):
                smallest = j
        if smallest != i:
            arr[i], arr[smallest] = arr[smallest], arr[i]
            st.swaps += 1


def insertion_sort(arr, st):
    for i in range(1, len(arr)):
        current = arr[i]
        j = i - 1
        while j >= 0 and st.less(current, arr[j]):
            arr[j + 1] = arr[j]         # shift right
            st.swaps += 1
            j -= 1
        arr[j + 1] = current


def merge_sort(arr, st):
    if len(arr) > 1:
        helper = arr[:]
        _merge_sort(arr, helper, 0, len(arr) - 1, st)


def _merge_sort(arr, helper, low, high, st):
    if low >= high:
        return
    mid = (low + high) // 2
    _merge_sort(arr, helper, low, mid, st)
    _merge_sort(arr, helper, mid + 1, high, st)

    helper[low:high + 1] = arr[low:high + 1]
    i, j, k = low, mid + 1, low
    while i <= mid and j <= high:
        if st.less(helper[j], helper[i]):
            arr[k] = helper[j]
            j += 1
        else:                           # equal -> take the left one (keeps it stable)
            arr[k] = helper[i]
            i += 1
        k += 1
        st.swaps += 1
    while i <= mid:
        arr[k] = helper[i]
        i += 1
        k += 1
        st.swaps += 1
    while j <= high:
        arr[k] = helper[j]
        j += 1
        k += 1
        st.swaps += 1


def quick_sort(arr, st):
    # Hoare partition + a stack instead of recursion.
    # (Ratings are 0 for lots of books, so plain recursion would go very deep.)
    stack = [(0, len(arr) - 1)]
    while stack:
        low, high = stack.pop()
        if low >= high:
            continue
        pivot = arr[(low + high) // 2]
        i = low - 1
        j = high + 1
        while True:
            i += 1
            while st.less(arr[i], pivot):
                i += 1
            j -= 1
            while st.less(pivot, arr[j]):
                j -= 1
            if i >= j:
                break
            arr[i], arr[j] = arr[j], arr[i]
            st.swaps += 1
        stack.append((low, j))
        stack.append((j + 1, high))


def _heapify(arr, size, i, st):
    while True:
        biggest = i
        left = 2 * i + 1
        right = 2 * i + 2
        if left < size and st.less(arr[biggest], arr[left]):
            biggest = left
        if right < size and st.less(arr[biggest], arr[right]):
            biggest = right
        if biggest == i:
            break
        arr[i], arr[biggest] = arr[biggest], arr[i]
        st.swaps += 1
        i = biggest


def heap_sort(arr, st):
    n = len(arr)
    for i in range(n // 2 - 1, -1, -1):     # build the heap
        _heapify(arr, n, i, st)
    for end in range(n - 1, 0, -1):         # move the biggest to the back
        arr[0], arr[end] = arr[end], arr[0]
        st.swaps += 1
        _heapify(arr, end, 0, st)


# --- extra algorithms (the two+ "additional" ones the project asks for)

def shell_sort(arr, st):
    n = len(arr)
    gap = n // 2
    while gap > 0:
        for i in range(gap, n):
            current = arr[i]
            j = i
            while j >= gap and st.less(current, arr[j - gap]):
                arr[j] = arr[j - gap]
                st.swaps += 1
                j -= gap
            arr[j] = current
        gap //= 2


def cocktail_sort(arr, st):
    start = 0
    end = len(arr) - 1
    swapped = True
    while swapped:
        swapped = False
        for i in range(start, end):             # left -> right
            if st.less(arr[i + 1], arr[i]):
                arr[i], arr[i + 1] = arr[i + 1], arr[i]
                st.swaps += 1
                swapped = True
        if not swapped:
            break
        end -= 1
        swapped = False
        for i in range(end - 1, start - 1, -1):  # right -> left
            if st.less(arr[i + 1], arr[i]):
                arr[i], arr[i + 1] = arr[i + 1], arr[i]
                st.swaps += 1
                swapped = True
        start += 1


def comb_sort(arr, st):
    n = len(arr)
    gap = n
    done = False
    while not done:
        gap = int(gap / 1.3)
        if gap <= 1:
            gap = 1
            done = True
        i = 0
        while i + gap < n:
            if st.less(arr[i + gap], arr[i]):
                arr[i], arr[i + gap] = arr[i + gap], arr[i]
                st.swaps += 1
                done = False
            i += gap


# name -> (function, time complexity, stable?)
ALGORITHMS = {
    "Bubble Sort":         (bubble_sort,    "O(n²)",                         True),
    "Selection Sort":      (selection_sort, "O(n²)",                         False),
    "Insertion Sort":      (insertion_sort, "O(n²)",                         True),
    "Merge Sort":          (merge_sort,     "O(n log n)",                    True),
    "Quick Sort":          (quick_sort,     "O(n log n) avg, O(n²) worst",   False),
    "Heap Sort":           (heap_sort,      "O(n log n)",                    False),
    "Shell Sort":          (shell_sort,     "O(n²) worst",                   False),
    "Cocktail Shaker Sort": (cocktail_sort, "O(n²)",                         True),
    "Comb Sort":           (comb_sort,      "O(n²) worst, ~O(n log n) avg",  False),
}


# ------------------------------------------------------------- helper funcs

def run_sort(rows, column, algo_name, descending=False):
    """Sort rows by one column. Returns (sorted_rows, comparisons, swaps, time_ms)."""
    func = ALGORITHMS[algo_name][0]
    items = [(sort_key(r, column), r) for r in rows]
    st = Stats(descending)

    start = time.perf_counter()
    func(items, st)
    time_ms = (time.perf_counter() - start) * 1000

    return [item[1] for item in items], st.comparisons, st.swaps, time_ms


def multi_level_sort(rows, levels):
    """levels = [(column, descending), ...] with the main column first.

    Trick: sort by the LAST level first, then go backwards to the main
    column. This only works with a stable sort, so we use Merge Sort.
    """
    result = list(rows)
    total_comparisons = 0
    total_swaps = 0
    total_ms = 0
    for column, descending in reversed(levels):
        result, comparisons, swaps, ms = run_sort(result, column, "Merge Sort", descending)
        total_comparisons += comparisons
        total_swaps += swaps
        total_ms += ms
    return result, total_comparisons, total_swaps, total_ms
