from __future__ import print_function
# simple script to test debugger

def fact(n):
    res = n
    if n > 1:
        res *= fact(n-1)
    return res

def quicksort(lst):
    if len(lst) < 2:
        return lst
    pivot_index = len(lst)/2
    pivot = lst[pivot_index]
    lower = [ x for x in lst if x < pivot ]
    higher = [ x for x in lst if x > pivot ]
    sorted_lower = quicksort(lower)
    sorted_higher = quicksort(higher)
    return sorted_lower + [pivot] + sorted_higher

# fix_print_with_import
print("3!", fact(3))
# fix_print_with_import
print("4!", fact(4))
# fix_print_with_import

# fix_print_with_import
print(quicksort([5,6,2,8,1,3,7,4]))
