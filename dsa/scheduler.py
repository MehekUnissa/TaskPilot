
from datetime import date

from dsa.max_heap import MaxHeap


# Points assigned to each manual priority level.
PRIORITY_POINTS = {
    "High": 3,
    "Medium": 2,
    "Low": 1
}


def get_urgency_score(deadline):
    """
    Calculate urgency based on the assignment deadline.

    Overdue          = 4 points
    Due today        = 3 points
    Due tomorrow     = 2 points
    Within 2-3 days  = 1 point
    Later            = 0 points
    """

    deadline_date = date.fromisoformat(deadline)
    days_left = (deadline_date - date.today()).days

    if days_left < 0:
        return 4

    if days_left == 0:
        return 3

    if days_left == 1:
        return 2

    if days_left <= 3:
        return 1

    return 0


def get_task_score(task):
    """
    Calculate the final scheduling score.

    Final Score = Priority Points + Urgency Points
    """

    priority_score = PRIORITY_POINTS.get(
        task["priority"],
        2
    )

    urgency_score = get_urgency_score(
        task["deadline"]
    )

    return priority_score + urgency_score


def build_task_heap(tasks):
    """
    Create a Max Heap containing all pending assignments.

    Every task receives its scheduling score before
    the heap is constructed.
    """

    heap_records = []

    for task in tasks:

        task_record = dict(task)

        task_record["score"] = get_task_score(task)

        heap_records.append(task_record)

    task_heap = MaxHeap()

    task_heap.build_heap(heap_records)

    return task_heap


def get_next_assignment(tasks):
    """
    Return the assignment with the highest scheduling score.

    Returns None when there are no pending assignments.
    """

    task_heap = build_task_heap(tasks)

    return task_heap.peek()
