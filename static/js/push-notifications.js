// =========================================
// TASKPILOT PUSH NOTIFICATIONS
// =========================================

function urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - base64String.length % 4) % 4);

    const base64 = (base64String + padding)
        .replace(/-/g, "+")
        .replace(/_/g, "/");

    const rawData = window.atob(base64);

    return Uint8Array.from(
        [...rawData].map(char => char.charCodeAt(0))
    );
}

document.addEventListener("DOMContentLoaded", async function () {

    const button = document.getElementById("enablePushNotifications");

    if (!button) return;

    if (!("serviceWorker" in navigator) ||
        !("PushManager" in window)) {
        button.disabled = true;
        button.textContent = "Notifications Not Supported";
        return;
    }

    button.addEventListener("click", async function () {

        try {
            const publicKey = button.dataset.publicKey;

            if (!publicKey) {
                throw new Error("VAPID public key is not configured.");
            }

            const permission = await Notification.requestPermission();

            if (permission !== "granted") {
                throw new Error("Please allow notifications in browser settings.");
            }

            // Reuse the service worker registered by base.html
            const registration = await navigator.serviceWorker.ready;

            let subscription =
                await registration.pushManager.getSubscription();

            if (!subscription) {
                subscription = await registration.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey:
                        urlBase64ToUint8Array(publicKey)
                });
            }

            const response = await fetch("/api/push/subscribe", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(subscription)
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(
                    result.message || "Subscription failed."
                );
            }

            button.textContent = "Notifications Enabled";
            button.disabled = true;

            alert("TaskPilot notifications enabled successfully!");

        } catch (error) {
            console.error("Push notification error:", error);
            alert("Could not enable notifications: " + error.message);
        }
    });
});