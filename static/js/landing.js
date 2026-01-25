(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", () => {
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
    });
})();
