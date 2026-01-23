(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", () => {
        const mobileBtn = document.getElementById("usageMobileBtn");
        const mobilePanel = document.getElementById("usageMobilePanel");
        const mobileDot = document.getElementById("usageMobileDot");

        // ไม่ login หรือไม่มี mobile menu ก็ข้าม
        if (!mobileBtn || !mobilePanel || !mobileDot) return;

        // toggle open/close
        mobileBtn.addEventListener("click", (e) => {
            e.preventDefault();
            mobilePanel.classList.toggle("hidden");
        });

        // ปิดเมื่อคลิกนอก panel
        document.addEventListener("click", (e) => {
            if (mobilePanel.classList.contains("hidden")) return;
            const t = e.target;
            if (!(t instanceof Node)) return;
            if (mobileBtn.contains(t) || mobilePanel.contains(t)) return;
            mobilePanel.classList.add("hidden");
        });

        function setMobileDot(state) {
            mobileDot.classList.remove("hidden", "bg-amber-500", "bg-red-500");
            if (state === "ok") {
                mobileDot.classList.add("hidden");
                return;
            }
            if (state === "low") {
                mobileDot.classList.add("bg-amber-500");
                return;
            }
            mobileDot.classList.add("bg-red-500");
        }

        // hook ให้ usage.js เรียก
        window.__setMobileUsageUI = function ({ chat, upload, resetText, tz }) {
            const pctOf = (remaining, budget) => {
                const b = Number(budget || 0);
                const r = Number(remaining || 0);
                return b > 0 ? Math.round((r / b) * 100) : 0;
            };

            // dot ใช้ chat เป็นหลัก (เหมือนเดิม)
            if (chat) {
                const pct = pctOf(chat.remaining, chat.budget);
                if (pct <= 0) setMobileDot("empty");
                else if (pct <= 10) setMobileDot("low");
                else setMobileDot("ok");
            } else {
                setMobileDot("ok");
            }

            const fmtNum = (n) => {
                try { return Number(n || 0).toLocaleString(); }
                catch { return String(n || 0); }
            };

            const row = (label, item) => {
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
            };

            mobilePanel.innerHTML = `
                <div class="p-3 border-b border-slate-200 dark:border-slate-800">
                <div class="text-xs text-slate-500 dark:text-slate-400">Daily token budgets</div>
                <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    Resets at <span class="font-medium text-slate-700 dark:text-slate-200">${resetText || ""}</span>
                    <span class="text-slate-400 dark:text-slate-500">${tz ? `(${tz})` : ""}</span>
                </div>
                </div>
                ${row("Chat", chat || { remaining: 0, budget: 0, spent: 0 })}
                <div class="h-px bg-slate-200 dark:bg-slate-800"></div>
                ${row("Upload", upload || { remaining: 0, budget: 0, spent: 0 })}
            `;
        };
    });
})();