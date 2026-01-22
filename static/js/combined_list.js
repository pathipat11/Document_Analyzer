(function () {
    const tbody = document.getElementById("combinedTbody");
    if (!tbody) return;

    const searchUrl = tbody.dataset.searchUrl || "";
    const qInput = document.getElementById("combinedQ");
    const sortSelect = document.getElementById("combinedSort");
    const clearBtn = document.getElementById("combinedClear");
    const countEl = document.getElementById("combinedCount");
    const statusEl = document.getElementById("combinedStatus");
    const pagerEl = document.getElementById("combinedPager");

    function getCookie(name) {
        const v = document.cookie.split(";").map(x => x.trim()).find(x => x.startsWith(name + "="));
        return v ? decodeURIComponent(v.split("=").slice(1).join("=")) : "";
    }
    const csrftoken = getCookie("csrftoken");

    let timer = null;
    let controller = null;
    let lastSig = "";
    let livePage = getPageFromUrl();

    function getPageFromUrl() {
        const u = new URL(window.location.href);
        const p = parseInt(u.searchParams.get("page") || "1", 10);
        return Number.isFinite(p) && p > 0 ? p : 1;
    }

    function setUrlParams(params) {
        const u = new URL(window.location.href);
        ["q", "sort", "page"].forEach(k => u.searchParams.delete(k));
        Object.entries(params).forEach(([k, v]) => {
            if (v !== undefined && v !== null && String(v).trim() !== "") u.searchParams.set(k, String(v));
        });
        window.history.replaceState({}, "", u.toString());
    }

    const esc = (s) => {
        const div = document.createElement("div");
        div.textContent = s ?? "";
        return div.innerHTML;
    };

    function buildRow(x) {
        const bubble = x.has_chat ? `<span class="mt-0.5 select-none text-xs">💬</span>` : "";
        const chatLabel = x.has_chat ? "Continue" : "Chat";

        const docPill = `
        <span class="inline-flex items-center rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700
                    dark:bg-slate-800 dark:text-slate-200 whitespace-nowrap">
            ${esc(String(x.doc_count ?? 0))} docs
        </span>
        `;

        return `
        <tr class="hover:bg-slate-50/70 dark:hover:bg-slate-900/30">
            <td class="px-4 py-3 min-w-60">
            <div class="flex items-center gap-2 min-w-0">
                ${bubble}
                <a class="font-medium text-blue-700 hover:underline dark:text-blue-300 truncate" href="${x.detail_url}">
                ${esc(x.title || "")}
                </a>
            </div>
            </td>

            <td class="px-4 py-3 whitespace-nowrap">${docPill}</td>

            <td class="px-4 py-3">${esc(String(x.total_words ?? 0))}</td>

            <td class="px-4 py-3 text-slate-600 dark:text-slate-300 whitespace-nowrap">
            ${esc(x.created_at || "")}
            </td>

            <td class="px-4 py-3">
            <a class="btn-outline" href="${x.chat_url}">${chatLabel}</a>
            </td>

            <td class="px-4 py-3">
            <button type="button"
                class="combinedDeleteBtn btn-outline text-red-400 dark:text-red-300"
                data-delete-url="${x.delete_url}"
                data-title="${esc(x.title || "combined")}">
                Delete
            </button>
            </td>
        </tr>
        `;
    }

    function buildPager(page, numPages) {
        if (!pagerEl) return;
        if (!numPages || numPages <= 1) {
            pagerEl.classList.add("hidden");
            pagerEl.innerHTML = "";
            return;
        }

        pagerEl.classList.remove("hidden");
        const prevDisabled = page <= 1;
        const nextDisabled = page >= numPages;

        pagerEl.innerHTML = `
      <div class="flex items-center justify-between">
        <div class="text-xs text-slate-500 dark:text-slate-400">
          Page ${page} of ${numPages}
        </div>
        <div class="flex items-center gap-2">
          <button type="button" class="btn-outline ${prevDisabled ? "opacity-50 cursor-not-allowed" : ""}"
            data-page="${page - 1}" ${prevDisabled ? "disabled" : ""}>Prev</button>
          <button type="button" class="btn-outline ${nextDisabled ? "opacity-50 cursor-not-allowed" : ""}"
            data-page="${page + 1}" ${nextDisabled ? "disabled" : ""}>Next</button>
        </div>
      </div>
    `;
    }

    function getParams() {
        return {
            q: (qInput?.value || "").trim(),
            sort: (sortSelect?.value || "newest").trim(),
            page: livePage,
        };
    }

    function signature(p) {
        return JSON.stringify(p);
    }

    async function runSearch() {
        const p = getParams();
        const sig = signature(p);
        if (sig === lastSig) return;
        lastSig = sig;

        if (clearBtn) clearBtn.classList.toggle("hidden", !p.q);

        if (controller) controller.abort();
        controller = new AbortController();

        const qs = new URLSearchParams();
        Object.entries(p).forEach(([k, v]) => {
            if (v !== undefined && v !== null && String(v).trim() !== "") qs.set(k, v);
        });

        if (statusEl) statusEl.classList.remove("hidden");

        try {
            const res = await fetch(`${searchUrl}?${qs.toString()}`, {
                headers: { "Accept": "application/json" },
                signal: controller.signal,
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);

            const data = await res.json();

            if ((data.page || 1) > (data.num_pages || 1)) {
                livePage = data.num_pages || 1;
                lastSig = "";
                return runSearch();
            }

            if (!data.ok) throw new Error("Bad response");

            const items = data.items || [];

            tbody.innerHTML = items.length
                ? items.map(buildRow).join("")
                : `
          <tr>
            <td class="px-4 py-8 text-center text-sm text-slate-500 dark:text-slate-400" colspan="6">
              No combined summaries found.
            </td>
          </tr>
        `;

            if (countEl) countEl.textContent = `${data.count ?? 0} items`;

            buildPager(data.page || 1, data.num_pages || 1);
            setUrlParams(p);

        } catch (err) {
            if (err.name === "AbortError") return;
            console.error(err);
            if (typeof window.showToast === "function") {
                window.showToast("Search failed. Please try again.", "error");
            }
        } finally {
            if (statusEl) statusEl.classList.add("hidden");
        }
    }

    function scheduleSearch({ resetPage = false } = {}) {
        if (resetPage) livePage = 1;
        clearTimeout(timer);
        timer = setTimeout(runSearch, 250);
    }

    if (qInput) qInput.addEventListener("input", () => scheduleSearch({ resetPage: true }));
    if (sortSelect) sortSelect.addEventListener("change", () => scheduleSearch({ resetPage: true }));
    if (clearBtn) clearBtn.addEventListener("click", () => { qInput.value = ""; scheduleSearch({ resetPage: true }); });

    document.addEventListener("click", async (e) => {
        const pgBtn = e.target.closest("#combinedPager button[data-page]");
        if (pgBtn) {
            const p = parseInt(pgBtn.dataset.page || "1", 10);
            if (Number.isFinite(p) && p > 0) {
                livePage = p;
                lastSig = "";
                runSearch();
            }
            return;
        }

        const delBtn = e.target.closest(".combinedDeleteBtn");
        if (!delBtn) return;

        e.preventDefault();

        const url = delBtn.dataset.deleteUrl;
        const title = delBtn.dataset.title || "combined summary";
        if (!url) return;

        const ok = confirm(`Delete "${title}" ? This cannot be undone.`);
        if (!ok) return;

        try {
            const res = await fetch(url, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrftoken,
                    "X-Requested-With": "XMLHttpRequest",
                },
            });

            let data = null;
            try { data = await res.json(); } catch { }

            if (!res.ok || !data?.ok) throw new Error(`HTTP ${res.status}`);

            if (typeof window.showToast === "function") {
                window.showToast(`Deleted: ${data.deleted_title || title}`, "success");
            }

            lastSig = "";
            runSearch();
        } catch (err) {
            console.error(err);
            if (typeof window.showToast === "function") {
                window.showToast("Delete failed. Please try again.", "error");
            }
        }
    });

    runSearch();
})();
