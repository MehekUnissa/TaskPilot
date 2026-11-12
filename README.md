# TaskPilot – Smart Assignment Manager

**A priority-based assignment and task scheduling system for students.**

TaskPilot is a student-focused assignment management application developed using Python and Flask. It helps students organize academic tasks, manage deadlines, track assignment progress, and identify the next task that needs attention.

The project applies **Data Structures and Algorithms (DSA)** concepts, particularly **Heaps and Priority Queues**, to schedule assignments based on priority and deadlines.

## Features

- **Student Registration and Login** – Individual student accounts with secure password hashing.
- **Dashboard** – Overview of total, pending, in-progress, completed, and overdue assignments.
- **Assignment Management** – Add, edit, view, and delete assignments.
- **Priority Management** – Set High, Medium, or Low priority, with automatic priority calculation where enabled.
- **Smart Task Scheduling** – Uses a priority-based scheduling mechanism to identify the next assignment.
- **Deadline Tracking** – View upcoming deadlines and remaining time.
- **Calendar** – View assignments according to their deadlines.
- **Search and Filters** – Find assignments using relevant task details and status.
- **Analytics** – Review assignment progress and completion statistics.
- **Focus Timer** – Support focused study sessions.
- **Notifications** – Deadline reminders through supported browser notification features.
- **Responsive Interface** – Designed to work across desktop and mobile-sized screens.

## Technologies Used

| Component | Technology |
|---|---|
| Programming Language | Python |
| Backend Framework | Flask |
| Database | SQLite |
| Frontend | HTML, CSS, JavaScript |
| Data Structures | Heap, Priority Queue |
| Authentication | Flask sessions and password hashing |
| Notifications | Web Push API |
| Version Control | Git and GitHub |

## DSA Concepts Used

### Heap
A heap is used to organize assignments according to their scheduling priority. It helps retrieve the most important task efficiently.

### Priority Queue
The priority queue determines which assignment should be handled next based on priority and deadline.

**Scheduling objective:** Assignments with greater urgency and higher priority should receive attention before less urgent tasks.

## Project Structure

```text
TaskPilot/
│
├── app.py
├── database.py
├── requirements.txt
├── README.md
│
├── database/
│
├── dsa/
│
├── static/
│   ├── css/
│   ├── js/
│   └── images/
│
└── templates/
```

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/MehekUnissa/TaskPilot.git
cd TaskPilot
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

### 3. Activate the virtual environment

**Windows PowerShell:**

```powershell
.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the application

```bash
python app.py
```

Open the local address displayed in the terminal in your browser.

## Database

TaskPilot uses SQLite to store student accounts and assignment information. The database is initialized by the application. Local database files are excluded from the Git repository.

## Future Enhancements

- Dedicated Android and iOS mobile application.
- AI-powered assignment assistance.
- Voice-based assignment entry.
- Improved personalized study recommendations.
- Additional notification and calendar integrations.

## Academic Project

**Institution:** Lords Institute of Engineering & Technology  
**Department:** Computer Science and Engineering – Artificial Intelligence and Machine Learning  
**Project:** DSA Micro-Project  
**Project Title:** Priority-Based Assignment and Task Scheduler  
**Application Name:** TaskPilot

---

*TaskPilot – Plan smarter. Prioritize better. Stay ahead.*
