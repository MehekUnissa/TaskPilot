
/* =========================================
   TASKPILOT - JAVASCRIPT
========================================= */

document.addEventListener("DOMContentLoaded", function () {

    /* ---------- THEME MANAGEMENT ---------- */

    const themeToggle = document.getElementById("themeToggle");
    const themeIcon = document.getElementById("themeIcon");
    const themeText = document.getElementById("themeText");

    const savedTheme = localStorage.getItem("taskpilot-theme");

    if (savedTheme === "dark") {
        document.documentElement.classList.add("dark-theme");
    }

    function updateThemeButton() {
        const isDark = document.documentElement.classList.contains("dark-theme");

        if (themeIcon) {
            themeIcon.textContent = isDark ? "☀️" : "🌙";
        }

        if (themeText) {
            themeText.textContent = isDark ? "Light Mode" : "Dark Mode";
        }
    }

    updateThemeButton();

    if (themeToggle) {
        themeToggle.addEventListener("click", function () {

            document.documentElement.classList.toggle("dark-theme");

            const isDark = document.documentElement.classList.contains("dark-theme");

            localStorage.setItem(
                "taskpilot-theme",
                isDark ? "dark" : "light"
            );

            updateThemeButton();
        });
    }


    /* ---------- CURRENT DATE ---------- */

    const currentDate = document.getElementById("currentDate");

    if (currentDate) {
        currentDate.textContent = new Date().toLocaleDateString("en-IN", {
            weekday: "long",
            day: "numeric",
            month: "long",
            year: "numeric"
        });
    }


    /* ---------- FLASH MESSAGE DISMISSAL ---------- */

    document.querySelectorAll(".flash-message").forEach(function (message) {

        setTimeout(function () {
            message.style.transition = "opacity 0.4s ease";
            message.style.opacity = "0";

            setTimeout(function () {
                message.remove();
            }, 450);

        }, 4000);
    });


    /* ---------- DELETE CONFIRMATION ---------- */

    document.querySelectorAll(".delete-form").forEach(function (form) {

        form.addEventListener("submit", function (event) {

            const confirmed = confirm(
                "Are you sure you want to delete this assignment?"
            );

            if (!confirmed) {
                event.preventDefault();
            }
        });
    });


    /* ---------- SEARCH INPUT ---------- */

    const searchInput = document.getElementById("searchInput");

    if (searchInput) {

        searchInput.addEventListener("input", function () {

            const searchValue = searchInput.value.toLowerCase();

            const rows = document.querySelectorAll(
                ".data-table tbody tr"
            );

            rows.forEach(function (row) {

                const rowText = row.textContent.toLowerCase();

                row.style.display = rowText.includes(searchValue)
                    ? ""
                    : "none";
            });
        });
    }


    /* ---------- SMART DEADLINE NOTIFICATIONS ---------- */

    const alertData = document.querySelectorAll(
        ".deadline-alert-item"
    );

    const notificationContainer = document.getElementById(
        "deadlineNotificationContainer"
    );

    function showDeadlineNotification(task) {

        if (!notificationContainer) {
            return;
        }

        const alertKey =
            "taskpilot-alert-" + task.id + "-" + task.label;

        // Prevent showing the same reminder repeatedly
        if (localStorage.getItem(alertKey)) {
            return;
        }

        localStorage.setItem(alertKey, "shown");

        // Create notification popup
        const notification = document.createElement("div");

        notification.className = "deadline-toast";

        const heading = document.createElement("strong");
        heading.textContent = "Deadline Reminder";

        const title = document.createElement("p");
        title.textContent = task.title;

        const message = document.createElement("span");
        message.textContent = task.label;

        const closeButton = document.createElement("button");
        closeButton.textContent = "×";
        closeButton.setAttribute("aria-label", "Close notification");

        closeButton.addEventListener("click", function () {
            notification.remove();
        });

        notification.appendChild(heading);
        notification.appendChild(closeButton);
        notification.appendChild(title);
        notification.appendChild(message);

        notificationContainer.appendChild(notification);

        // Browser notification if permission is granted
        if (
            "Notification" in window &&
            Notification.permission === "granted"
        ) {
            new Notification("TaskPilot Deadline Reminder", {
                body: task.title + " - " + task.label
            });
        }

        // Automatically close popup
        setTimeout(function () {
            notification.remove();
        }, 8000);
    }


    // Read deadline reminders sent by Flask
    alertData.forEach(function (item) {

        const task = {
            id: item.dataset.id,
            title: item.dataset.title,
            label: item.dataset.label,
            days: Number(item.dataset.days),
            withinHour: item.dataset.hour === "true"
        };

        showDeadlineNotification(task);
    });


    /* ---------- BROWSER NOTIFICATION PERMISSION ---------- */

    if (
        notificationContainer &&
        "Notification" in window &&
        Notification.permission === "default"
    ) {

        const enableButton = document.createElement("button");

        enableButton.textContent = "Enable Browser Alerts";
        enableButton.className = "notification-permission-button";

        notificationContainer.appendChild(enableButton);

        enableButton.addEventListener("click", function () {

            Notification.requestPermission().then(function (permission) {

                enableButton.remove();

                if (permission === "granted") {
                    alert("Browser notifications enabled!");
                }
            });
        });
    }

});
