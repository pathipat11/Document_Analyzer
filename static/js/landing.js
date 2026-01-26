(function () {
    "use strict";

    function prefersReducedMotion() {
        return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }

    function initReveal() {
        const els = Array.from(document.querySelectorAll(".reveal"));
        if (!els.length) return;

        const io = new IntersectionObserver(
            (entries) => {
                entries.forEach((e) => {
                    if (e.isIntersecting) {
                        e.target.classList.add("is-in");
                        io.unobserve(e.target);
                    }
                });
            },
            { threshold: 0.12 }
        );

        els.forEach((el) => io.observe(el));
    }

    function initSmoothScroll() {
        document.addEventListener("click", (e) => {
            const a = e.target.closest('a[href^="#"]');
            if (!a) return;

            const href = a.getAttribute("href");
            if (!href || href === "#") return;

            const target = document.querySelector(href);
            if (!target) return;

            e.preventDefault();
            target.scrollIntoView({
                behavior: prefersReducedMotion() ? "auto" : "smooth",
                block: "start",
            });
        });
    }

    function typeInto(el) {
        const full = (el.dataset.typing || "")
            .replace(/\\n/g, "\n")
            .replace(/\r\n/g, "\n");

        if (!full) return;

        const speed = Math.max(8, Number(el.dataset.speed || 18));
        const startDelay = Math.max(0, Number(el.dataset.startDelay || 0));
        const lineDelay = Math.max(0, Number(el.dataset.lineDelay || 0));

        if (prefersReducedMotion()) {
            el.textContent = full;
            el.classList.remove("typing-caret");
            return;
        }

        if (el.dataset.typed === "1") return;
        el.dataset.typed = "1";

        el.textContent = "";
        el.classList.add("typing-caret");

        let i = 0;
        function step() {
            if (i >= full.length) return;

            const ch = full[i++];
            el.textContent += ch;

            const delay = ch === "\n" ? (lineDelay || speed) : speed;
            setTimeout(step, delay);
        }

        setTimeout(step, startDelay);
    }

    function initTyping() {
        const el = document.getElementById("typingText");
        if (!el) return;

        const io = new IntersectionObserver(
            (entries) => {
                entries.forEach((e) => {
                    if (e.isIntersecting) {
                        typeInto(el);
                        io.disconnect();
                    }
                });
            },
            { threshold: 0.35 }
        );

        io.observe(el);
    }

    document.addEventListener("DOMContentLoaded", () => {
        initReveal();
        initSmoothScroll();
        initTyping();
    });
})();
