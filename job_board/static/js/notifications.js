// Automated notification polling — runs on every authenticated page.
// Checks for new job/candidate matches every 15 seconds without page reload.

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + "=")) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function fetchNotifications() {
    fetch("/api/notifications/")
        .then((res) => res.json())
        .then((data) => {
            const badge = document.getElementById("notif-count");
            const list = document.getElementById("notif-list");
            if (!badge || !list) return;

            badge.textContent = data.count;
            badge.style.display = data.count > 0 ? "inline-block" : "none";

            list.innerHTML = "";
            if (data.notifications.length === 0) {
                list.innerHTML = '<p class="text-muted small px-2 mb-0">No notifications yet</p>';
                return;
            }

            data.notifications.forEach((n) => {
                const item = document.createElement("a");
                item.href = n.link || "#";
                item.className = "dropdown-item small border-bottom py-2";
                item.innerHTML = `<div>${n.message}</div><div class="text-muted" style="font-size:0.75rem;">${n.created_at}</div>`;
                // Without preventDefault, the browser navigates to
                // item.href immediately, which cancels the markAsRead
                // fetch below before it completes — the notification
                // never actually gets marked read and reappears every
                // time. So: stop the default navigation, wait for the
                // read-status update to finish, then navigate manually.
                item.addEventListener("click", (event) => {
                    event.preventDefault();
                    markAsRead(n.id).finally(() => {
                        if (n.link) {
                            window.location.href = n.link;
                        }
                    });
                });
                list.appendChild(item);
            });
        })
        .catch((err) => console.error("Notification fetch failed:", err));
}

function markAsRead(id) {
    // Returns the fetch promise so callers (like the click handler
    // above) can wait for it to finish before doing anything else.
    return fetch(`/api/notifications/${id}/read/`, {
        method: "POST",
        headers: { "X-CSRFToken": getCookie("csrftoken") },
    }).then(() => fetchNotifications());
}

// Initial load, then poll every 15 seconds
document.addEventListener("DOMContentLoaded", () => {
    fetchNotifications();
    setInterval(fetchNotifications, 15000);
});
