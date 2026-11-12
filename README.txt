TASKPILOT — PROJECT 49
Priority-Based Assignment and Task Scheduler

REQUIREMENTS
- Python 3.10 or newer
- VS Code
- A modern browser

RUN ON WINDOWS (VS CODE TERMINAL)
1. Open the TaskPilot folder in VS Code.
2. Open Terminal > New Terminal.
3. Create a virtual environment:
   python -m venv venv
4. Activate it:
   venv\Scripts\activate
5. Install dependencies:
   pip install -r requirements.txt
6. Start the application:
   python app.py
7. Open this address in Chrome:
   http://127.0.0.1:5000

The SQLite database is created automatically at database/tasks.db.

DSA NOTE
The project uses a custom MaxHeap implemented in dsa/max_heap.py.
The scheduler uses the heap to keep the highest-ranked pending task at the root.
No Python heapq or sorting function is used for the core scheduling decision.

CURRENT SCHEDULING RULES
Manual priority: High=3, Medium=2, Low=1.
Urgency: Overdue=4, Today=3, Tomorrow=2, within 2–3 days=1, later=0.
Final score = manual priority + urgency.
Tie-breaks: earlier deadline, then earlier creation time, then lower task ID.

This is the first working version. The edit-task workflow and more detailed heap-operation demonstration can be added in the next development step.
