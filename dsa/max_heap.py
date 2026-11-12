
class MaxHeap:
    """
    Custom Max Heap implementation for TaskPilot.

    The task with the highest scheduling score stays
    at the root of the heap.
    """

    def __init__(self):
        self.items = []

    def is_empty(self):
        """Check whether the heap contains any elements."""
        return len(self.items) == 0

    def size(self):
        """Return the number of elements in the heap."""
        return len(self.items)

    def peek(self):
        """
        Return the highest-priority element
        without removing it.
        """
        if self.is_empty():
            return None

        return self.items[0]

    def insert(self, item):
        """Insert a new element into the heap."""

        self.items.append(item)

        # Restore the Max Heap property.
        self._heapify_up(len(self.items) - 1)

    def extract_max(self):
        """Remove and return the root element."""

        if self.is_empty():
            return None

        if len(self.items) == 1:
            return self.items.pop()

        maximum = self.items[0]

        # Move the last element to the root.
        self.items[0] = self.items.pop()

        # Restore the Max Heap property.
        self._heapify_down(0)

        return maximum

    def build_heap(self, values):
        """
        Build a Max Heap from a list of elements.

        Bottom-up heap construction takes O(n) time.
        """

        self.items = list(values)

        last_parent = (len(self.items) // 2) - 1

        for index in range(last_parent, -1, -1):
            self._heapify_down(index)

    def _heapify_up(self, index):
        """
        Move an inserted element upward
        until the Max Heap property is restored.
        """

        while index > 0:

            parent = (index - 1) // 2

            if self._higher_priority(
                self.items[index],
                self.items[parent]
            ):

                self.items[index], self.items[parent] = (
                    self.items[parent],
                    self.items[index]
                )

                index = parent

            else:
                break

    def _heapify_down(self, index):
        """
        Move an element downward when necessary
        to restore the Max Heap property.
        """

        heap_size = len(self.items)

        while True:

            left_child = (2 * index) + 1
            right_child = (2 * index) + 2

            highest = index

            # Compare with the left child.
            if (
                left_child < heap_size
                and self._higher_priority(
                    self.items[left_child],
                    self.items[highest]
                )
            ):
                highest = left_child

            # Compare with the right child.
            if (
                right_child < heap_size
                and self._higher_priority(
                    self.items[right_child],
                    self.items[highest]
                )
            ):
                highest = right_child

            # Stop if the parent is already highest.
            if highest == index:
                break

            self.items[index], self.items[highest] = (
                self.items[highest],
                self.items[index]
            )

            index = highest

    @staticmethod
    def _higher_priority(first, second):
        """
        Compare two task records.

        Rules:
        1. Higher scheduling score wins.
        2. Earlier deadline wins in a tie.
        3. Earlier creation time wins in a further tie.
        4. Lower task ID wins if everything else is equal.
        """

        first_key = (
            first["score"],
            first["deadline"],
            first["created_at"],
            -first["id"]
        )

        second_key = (
            second["score"],
            second["deadline"],
            second["created_at"],
            -second["id"]
        )

        if first_key[0] != second_key[0]:
            return first_key[0] > second_key[0]

        return first_key[1:] < second_key[1:]
