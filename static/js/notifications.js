// Automated notification polling: runs on every authenticated page.
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


function showToast(message) {
    const toast = document.createElement("div");
    toast.className = "alert alert-warning position-fixed top-0 end-0 m-3 shadow small";
    toast.style.zIndex = 2000;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
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

                const msg = document.createElement("div");
                msg.textContent = n.message;
                const time = document.createElement("div");
                time.className = "text-muted";
                time.style.fontSize = "0.75rem";
                time.textContent = n.created_at;
                item.append(msg, time);
                item.addEventListener("click", async (event) => {
                    event.preventDefault();
                    const result = await markAsRead(n.id);

                    if (result.notFound) {
                       
                        showToast("This notification was removed.");
                        return;
                    }
                    if (n.link) {
                        window.location.href = n.link;
                    }
                });
                list.appendChild(item);
            });
        })
        .catch((err) => console.error("Notification fetch failed:", err));
}

async function markAsRead(id) {
    try {
        const res = await fetch(`/api/notifications/${id}/read/`, {
            method: "POST",
            headers: { "X-CSRFToken": getCookie("csrftoken") },
        });
        fetchNotifications(); 
        return { notFound: res.status === 404 };
    } catch (err) {
        console.error("Mark as read failed:", err);
        return { notFound: false }; 
    }
}

document.addEventListener("DOMContentLoaded", () => {
    fetchNotifications();
    setInterval(fetchNotifications, 15000);
});