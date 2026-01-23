(function () {
    "use strict";

    // ---------------------------
    // Helpers
    // ---------------------------
    function qs(sel, root = document) { return root.querySelector(sel); }
    function qsa(sel, root = document) { return Array.from(root.querySelectorAll(sel)); }

    // ---------------------------
    // Toast helper (global)
    // ---------------------------
    window.showToast = function (text, type = "success") {
        let container = document.getElementById("toast-container");
        if (!container) {
            container = document.createElement("div");
            container.id = "toast-container";
            container.className = "fixed right-4 top-4 z-50 flex flex-col gap-3";
            document.body.appendChild(container);
        }

        const toast = document.createElement("div");
        toast.className = `toast animate-slide-in rounded-xl border p-3 text-sm ${type === "success"
            ? "border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200"
            : type === "error"
                ? "border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200"
                : type === "warning"
                    ? "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200"
                    : "border-blue-200 bg-blue-50 text-blue-800 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-200"
            }`;

        toast.textContent = text;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.transition = "opacity 0.4s ease, transform 0.4s ease";
            toast.style.opacity = "0";
            toast.style.transform = "translateY(-6px) scale(0.98)";
            setTimeout(() => toast.remove(), 400);
        }, 2500);
    };

    // ---------------------------
    // Global loader
    // ---------------------------
    function showGlobalLoader() {
        const el = document.getElementById("globalLoader");
        if (!el) return;
        el.style.display = "flex";
    }
    function hideGlobalLoader() {
        const el = document.getElementById("globalLoader");
        if (!el) return;
        el.style.display = "none";
    }

    // ---------------------------
    // DOM Ready init
    // ---------------------------
    document.addEventListener("DOMContentLoaded", () => {
        // ---- Theme toggle ----
        const toggle = document.getElementById("input");
        if (toggle) {
            toggle.checked = document.documentElement.classList.contains("dark");
            toggle.addEventListener("change", () => {
                const isDark = toggle.checked;
                document.documentElement.classList.toggle("dark", isDark);
                localStorage.setItem("theme", isDark ? "dark" : "light");
            });
        }

        // ---- Auto-dismiss Django messages toasts ----
        const toasts = qsa(".toast");
        toasts.forEach((toast, idx) => {
            setTimeout(() => {
                toast.style.transition = "opacity 0.4s ease, transform 0.4s ease";
                toast.style.opacity = "0";
                toast.style.transform = "translateY(-6px) scale(0.98)";
                setTimeout(() => toast.remove(), 400);
            }, 3000 + idx * 200);
        });

        // ---- Close <details> when clicking outside ----
        document.addEventListener("click", (e) => {
            qsa("details[open]").forEach((d) => {
                if (!d.contains(e.target)) d.removeAttribute("open");
            });
        });

        // ---- Global Loader on navigation ----
        document.addEventListener("click", (e) => {
            const a = e.target.closest("a");
            if (!a) return;

            if (a.dataset.noGlobalLoader === "1") return;

            const href = (a.getAttribute("href") || "").trim();
            if (!href) return;
            if (href === "#" || href.startsWith("#")) return;
            if (href.toLowerCase().startsWith("javascript:")) return;

            if (a.hasAttribute("download")) return;
            if (a.target === "_blank") return;
            if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

            showGlobalLoader();
        });

        document.addEventListener("submit", (e) => {
            const form = e.target;
            if (!(form instanceof HTMLFormElement)) return;
            if (form.dataset.noGlobalLoader === "1") return;
            showGlobalLoader();
        });

        window.addEventListener("pageshow", (evt) => {
            if (evt.persisted) hideGlobalLoader();
        });

        // ---- Mobile menu ----
        const btn = document.getElementById("mobileMenuBtn");
        const panel = document.getElementById("mobileMenuPanel");
        if (btn && panel) {
            btn.addEventListener("click", () => panel.classList.toggle("hidden"));
        }

        // ---- Avatar preview ----
        const input = qs('input[type="file"][name="avatar"], input[type="file"]#id_avatar');
        const preview = document.getElementById("avatarPreview");
        const previewText = document.getElementById("avatarPreviewText");
        if (input && preview) {
            input.addEventListener("change", () => {
                const file = input.files && input.files[0];
                if (!file) {
                    preview.classList.add("hidden");
                    if (previewText) previewText.classList.add("hidden");
                    preview.src = "";
                    return;
                }
                const url = URL.createObjectURL(file);
                preview.src = url;
                preview.classList.remove("hidden");
                if (previewText) previewText.classList.remove("hidden");
            });
        }
    });
})();