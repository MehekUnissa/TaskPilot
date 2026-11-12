
// TASKPILOT SERVICE WORKER

// Display push notifications
self.addEventListener("push", function (event) {
    let data = {};

    if (event.data) {
        try {
            data = event.data.json();
        } catch (error) {
            data = {
                body: event.data.text()
            };
        }
    }

    const title = data.title || "TaskPilot Reminder";

    const options = {
        body: data.body || "You have an upcoming assignment deadline.",

        icon: "/static/images/icon.png",
        badge: "/static/images/icon.png",

        // Allow the browser to dismiss it automatically.
        requireInteraction: false,

        // Play the device's default notification sound.
        silent: false,

        tag: data.tag || "taskpilot-deadline-" + Date.now(),

        data: {
            url: data.url || "/"
        }
    };

    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});


// Handle notification clicks
self.addEventListener("notificationclick", function (event) {
    event.notification.close();

    const requestedUrl = event.notification.data?.url || "/";
    const url = new URL(requestedUrl, self.location.origin);

    // Only allow navigation within TaskPilot.
    const targetUrl = url.origin === self.location.origin
        ? url.href
        : self.location.origin + "/";

    event.waitUntil(
        clients.matchAll({
            type: "window",
            includeUncontrolled: true
        }).then(function (clientList) {

            for (const client of clientList) {
                if (new URL(client.url).origin === self.location.origin) {

                    if ("navigate" in client) {
                        return client.navigate(targetUrl).then(function (newClient) {
                            return (newClient || client).focus();
                        });
                    }

                    return client.focus();
                }
            }

            return clients.openWindow(targetUrl);
        })
    );
});


// Activate the new service worker
self.addEventListener("activate", function (event) {
    event.waitUntil(self.clients.claim());
});


// Install the service worker
self.addEventListener("install", function (event) {
    self.skipWaiting();
});
