document.addEventListener("DOMContentLoaded", () => {
    const wrappers = document.querySelectorAll("[data-password-toggle]");

    wrappers.forEach((wrap) => {
        const input = wrap.querySelector("input");
        const btn = wrap.querySelector("button");
        const iconShow = wrap.querySelector("[data-icon='show']");
        const iconHide = wrap.querySelector("[data-icon='hide']");

        if (!input || !btn) return;

        function setState(isShown) {
            input.type = isShown ? "text" : "password";
            btn.setAttribute("aria-pressed", String(isShown));
            btn.setAttribute("aria-label", isShown ? "Hide password" : "Show password");

            if (iconShow && iconHide) {
                iconShow.classList.toggle("hidden", isShown);
                iconHide.classList.toggle("hidden", !isShown);
            }
        }

        setState(false);

        btn.addEventListener("click", (e) => {
            e.preventDefault();
            const isShown = input.type === "password";
            setState(isShown);

            input.focus({ preventScroll: true });
            try {
                const len = input.value?.length ?? 0;
                input.setSelectionRange(len, len);
            } catch (_) { }
        });
    });
});
