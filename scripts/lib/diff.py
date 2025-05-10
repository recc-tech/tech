from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, List, TypeVar

B = TypeVar("B")
T = TypeVar("T")


class Edit(Generic[T]):
    """A change to one element of a sequence."""

    val: T
    """The value that was inserted, deleted, etc."""

    def map(self, f: Callable[[T], B]) -> Edit[B]:
        """Change the content of this edit without changing the edit type."""
        raise NotImplementedError()


@dataclass
class NoOp(Edit[T]):
    """The given element of the sequence is unchanged."""

    val: T
    """The unchanged value."""

    def map(self, f: Callable[[T], B]) -> Edit[B]:
        return NoOp(f(self.val))

    def __repr__(self):
        return f"NoOp({repr(self.val)})"


@dataclass
class Insertion(Edit[T]):
    """A new value was added to the sequence."""

    val: T
    """The value that was inserted."""

    def map(self, f: Callable[[T], B]) -> Edit[B]:
        return Insertion(f(self.val))

    def __repr__(self):
        return f"Insertion({repr(self.val)})"


@dataclass
class Deletion(Edit[T]):
    """An existing value was removed from the sequence."""

    val: T
    """The value that was deleted."""

    def map(self, f: Callable[[T], B]) -> Edit[B]:
        return Deletion(f(self.val))

    def __repr__(self):
        return f"Deletion({repr(self.val)})"


def diff_has_changes(edits: List[Edit[T]]) -> bool:
    """
    Check whether the given edit sequence includes any changes.

    >>> diff_has_changes([])
    False
    >>> diff_has_changes([NoOp("c"), NoOp("a"), NoOp("t")])
    False
    >>> diff_has_changes([NoOp("c"), Deletion("a"), Insertion("o"), NoOp("t")])
    True
    """
    return any(e for e in edits if not isinstance(e, NoOp))


def find_diff(old: List[T], new: List[T]) -> List[Edit[T]]:
    """
    Construct a sequence of edits to go from `old` to `new`.

    >>> find_diff(list("bat"), list("bot"))
    [NoOp('b'), Deletion('a'), Insertion('o'), NoOp('t')]
    """
    # (1) Construct matrix of edit distances.
    #     (similar to https://en.wikipedia.org/wiki/Longest_common_subsequence#Code_for_the_dynamic_programming_solution)
    #      edit_matrix[i][j] is the edit distance between old[i:] and new[j:].
    edit_matrix = [[-1 for _ in range(len(new) + 1)] for _ in range(len(old) + 1)]

    def compute_edit_dist(i: int, j: int) -> int:
        nonlocal edit_matrix
        if edit_matrix[i][j] >= 0:
            return edit_matrix[i][j]

        if i == len(old):
            dist = len(new[j:])
        elif j == len(new):
            dist = len(old[i:])
        elif old[i] == new[j]:
            dist = compute_edit_dist(i + 1, j + 1)
        else:
            dist = 1 + min(
                compute_edit_dist(i + 1, j),  # Delete
                compute_edit_dist(i, j + 1),  # Insert
            )

        assert dist >= 0
        edit_matrix[i][j] = dist
        return edit_matrix[i][j]

    dist = compute_edit_dist(0, 0)

    # (2) Navigate through the matrix and extract the best path.
    i = 0
    j = 0
    seq: List[Edit[T]] = []
    while True:
        if i == len(old):
            seq = seq + [Insertion(x) for x in new[j:]]
            break
        elif j == len(new):
            seq = seq + [Deletion(x) for x in old[i:]]
            break
        elif old[i] == new[j]:
            seq.append(NoOp(old[i]))
            i += 1
            j += 1
        else:
            # Is it better to insert or delete?
            # Check the edit matrix!
            # In case of a tie, delete first.
            del_cost = edit_matrix[i + 1][j]
            ins_cost = edit_matrix[i][j + 1]
            if del_cost <= ins_cost:
                # Delete
                seq.append(Deletion(old[i]))
                i += 1
            else:
                # Insert
                seq.append(Insertion(new[j]))
                j += 1

    assert len([x for x in seq if not isinstance(x, NoOp)]) == dist
    return seq
