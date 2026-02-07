document.addEventListener("DOMContentLoaded", () => {
    const dd = document.getElementById("usageDropdown");
    const pill = document.getElementById("usagePill");
    const dotEl = document.getElementById("usageDot");
    const panel = document.getElementById("usagePanel");

    if (!dd || !pill || !dotEl || !panel) return;

    const usageUrl = document.body?.dataset?.usageUrl;
    if (!usageUrl) return;

    function fmtNum(n) {
        try { return Number(n || 0).toLocaleString(); } catch { return String(n || 0); }
    }
    function pctOf(remaining, budget) {
        const b = Number(budget || 0);
        const r = Number(remaining || 0);
        return b > 0 ? Math.round((r / b) * 100) : 0;
    }
    function fmtReset(resetAtIso) {
        if (!resetAtIso) return "";
        const d = new Date(resetAtIso);
        return d.toLocaleString(undefined, { hour: "2-digit", minute: "2-digit", month: "short", day: "2-digit" });
    }

    function rowHtml(label, item) {
        const remaining = item?.remaining ?? 0;
        const budget = item?.budget ?? 0;
        const spent = item?.spent ?? 0;
        const pct = pctOf(remaining, budget);
        const barW = Math.max(0, Math.min(100, pct));

        const barClass =
            pct <= 0 ? "bg-red-500" :
                pct <= 10 ? "bg-amber-500" :
                    "bg-slate-900 dark:bg-slate-200";

        return `
        <div class="px-3 py-3">
            <div class="flex items-center justify-between">
            <div class="text-sm font-semibold text-slate-800 dark:text-slate-100">${label}</div>
            <div class="text-xs text-slate-500 dark:text-slate-400">${fmtNum(remaining)} left (${pct}%)</div>
            </div>
            <div class="mt-2 h-2 w-full rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
            <div class="h-full ${barClass}" style="width:${barW}%"></div>
            </div>
            <div class="mt-2 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
            <div>Spent: ${fmtNum(spent)}</div>
            <div>Budget: ${fmtNum(budget)}</div>
            </div>
        </div>
        `;
    }

    function setDotState(state) {
        dotEl.className = "h-2 w-2 rounded-full";
        dotEl.classList.remove("hidden", "bg-amber-500", "bg-red-500");

        pill.classList.remove(
            "border-amber-300", "bg-amber-50", "text-amber-900", "dark:border-amber-800", "dark:bg-amber-950/40", "dark:text-amber-200",
            "border-red-300", "bg-red-50", "text-red-900", "dark:border-red-800", "dark:bg-red-950/40", "dark:text-red-200"
        );

        if (state === "ok") {
            dotEl.classList.add("hidden");
            return;
        }

        dotEl.classList.remove("hidden");

        if (state === "low") {
            dotEl.classList.add("bg-amber-500");
            pill.classList.add(
                "border-amber-300", "bg-amber-50", "text-amber-900",
                "dark:border-amber-800", "dark:bg-amber-950/40", "dark:text-amber-200"
            );
            return;
        }

        // empty
        dotEl.classList.add("bg-red-500");
        pill.classList.add(
            "border-red-300", "bg-red-50", "text-red-900",
            "dark:border-red-800", "dark:bg-red-950/40", "dark:text-red-200"
        );
    }

    // --------- anti-spam controls ----------
    const cooldownMs = 10_000; // 10s (ปรับได้)
    let lastFetchAt = 0;
    let inFlight = null;

    let resetTimer = null;
    function scheduleResetRefresh(resetAtIso) {
        try {
            if (resetTimer) clearTimeout(resetTimer);
            if (!resetAtIso) return;

            const t = new Date(resetAtIso).getTime() - Date.now();
            const ms = Math.max(2000, Math.min(t + 2000, 24 * 60 * 60 * 1000));
            resetTimer = setTimeout(() => refreshUsage({ reason: "reset_timer", force: true }), ms);
        } catch (_) { }
    }

    // --------- main refresh ----------
    async function refreshUsage(opts) {
        const { force = false } = (opts || {});
        const now = Date.now();

        if (!force && (now - lastFetchAt) < cooldownMs) return;
        if (inFlight) return inFlight; // กันยิงซ้อน

        lastFetchAt = now;

        inFlight = (async () => {
            try {
                const res = await fetch(usageUrl, {
                    credentials: "same-origin",
                    cache: "no-store",
                    headers: { "Accept": "application/json" }
                });

                if (!res.ok) return;
                const ct = res.headers.get("content-type") || "";
                if (!ct.includes("application/json")) return;

                const data = await res.json().catch(() => null);
                if (!data || !data.ok) return;

                const items = data.items || [];
                const chat = items.find(x => x.purpose === "chat");
                const upload = items.find(x => x.purpose === "upload");

                const stateFrom = (item) => {
                    if (!item) return "ok";
                    const pct = pctOf(item.remaining, item.budget);
                    if (pct <= 0) return "empty";
                    if (pct <= 10) return "low";
                    return "ok";
                };
                const worst = (a, b) => {
                    const rank = { ok: 0, low: 1, empty: 2 };
                    return rank[a] >= rank[b] ? a : b;
                };

                setDotState(worst(stateFrom(chat), stateFrom(upload)));

                const resetText = fmtReset(data.reset_at);
                const tz = data.timezone || "";
                scheduleResetRefresh(data.reset_at);

                if (typeof window.__setMobileUsageUI === "function") {
                    window.__setMobileUsageUI({ chat, upload, resetText, tz });
                }

                // desktop panel
                panel.innerHTML = `
                    <div class="p-3 border-b border-slate-200 dark:border-slate-800">
                        <div class="text-xs text-slate-500 dark:text-slate-400">Daily token budgets</div>
                        <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">
                        Resets at <span class="font-medium text-slate-700 dark:text-slate-200">${resetText}</span>
                        <span class="text-slate-400 dark:text-slate-500">${tz ? `(${tz})` : ""}</span>
                        </div>
                    </div>
                    ${rowHtml("Chat", chat || { remaining: 0, budget: 0, spent: 0 })}
                    <div class="h-px bg-slate-200 dark:bg-slate-800"></div>
                    ${rowHtml("Upload", upload || { remaining: 0, budget: 0, spent: 0 })}
                    `;
            } catch (_) {
                // เงียบไว้ ไม่ต้องพังหน้า
            } finally {
                inFlight = null;
            }
        })();

        return inFlight;
    }

    window.Usage = window.Usage || {};
    window.Usage.refresh = refreshUsage;

    refreshUsage({ reason: "init", force: true });

    dd.addEventListener("mouseenter", () => refreshUsage({ reason: "hover" }));
    
    pill.addEventListener("click", () => refreshUsage({ reason: "click" }));

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) refreshUsage({ reason: "visible" });
    });
    window.addEventListener("focus", () => refreshUsage({ reason: "focus" }));
});
