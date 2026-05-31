/*
 * Document status polling.
 *
 * Polls /api/status/ for documents that are still "queued" or "processing".
 * Instead of showing an inline status badge, it notifies the user with a
 * toast in the top-right corner once a document finishes (or fails), and
 * quietly updates the type / word / char cells in place.
 *
 * Works on:
 *   - the document list (rows carry [data-doc-id] + [data-doc-status])
 *   - the document detail page ([data-detail-status]) which reloads when done
 */
(function () {
    const STATUS_URL = document.body?.dataset?.statusUrl || "/api/status/";
    const POLL_MS = 2500;
    const ACTIVE = new Set(["queued", "processing"]);

    function isActive(status) {
        return ACTIVE.has(status);
    }

    function toast(message, type) {
        if (typeof window.showToast === "function") {
            window.showToast(message, type);
        }
    }

    // ---- collect the ids we still need to watch ----
    function collectActiveRows() {
        const rows = [];
        document.querySelectorAll("[data-doc-id][data-doc-status]").forEach((el) => {
            if (isActive(el.dataset.docStatus || "")) {
                rows.push(el);
            }
        });
        return rows;
    }

    function collectActiveIds() {
        const ids = new Set();
        collectActiveRows().forEach((el) => ids.add(el.dataset.docId));

        const detail = document.querySelector("[data-detail-status]");
        if (detail && isActive(detail.dataset.detailStatus || "")) {
            ids.add(detail.dataset.docId);
        }
        return [...ids].filter(Boolean);
    }

    function updateCells(item) {
        const typeEl = document.querySelector(`[data-doc-type-for="${item.id}"]`);
        if (typeEl && item.document_type) typeEl.textContent = item.document_type;

        const wordsEl = document.querySelector(`[data-doc-words-for="${item.id}"]`);
        if (wordsEl && typeof item.word_count === "number") {
            wordsEl.textContent = String(item.word_count);
        }
        const charsEl = document.querySelector(`[data-doc-chars-for="${item.id}"]`);
        if (charsEl && typeof item.char_count === "number") {
            charsEl.textContent = String(item.char_count);
        }
    }

    function rowFor(id) {
        return document.querySelector(`[data-doc-id="${id}"][data-doc-status]`);
    }

    let timer = null;
    let stopped = false;

    async function poll() {
        const ids = collectActiveIds();
        if (ids.length === 0) {
            stopped = true;
            return;
        }

        try {
            const res = await fetch(`${STATUS_URL}?ids=${encodeURIComponent(ids.join(","))}`, {
                headers: { Accept: "application/json" },
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            if (!data.ok) throw new Error("Bad response");

            const detail = document.querySelector("[data-detail-status]");

            for (const item of data.items || []) {
                const row = rowFor(item.id);
                const prev = row ? row.dataset.docStatus : null;

                // List rows: update marker + cells, and toast on transition.
                if (row) {
                    row.dataset.docStatus = item.status || "";
                    if (!isActive(item.status)) {
                        updateCells(item);
                        const name = row.dataset.docName || "Document";
                        if (item.error || item.status === "error" || item.status === "failed") {
                            toast(`Processing failed: ${name}`, "error");
                        } else if (item.status === "done" && isActive(prev || "")) {
                            toast(`Done: ${name}`, "success");
                        }
                    }
                }

                // Detail page: reload once processing finishes so the full
                // server-rendered view (summary, preview, error) is shown.
                if (
                    detail &&
                    String(detail.dataset.docId) === String(item.id) &&
                    !isActive(item.status)
                ) {
                    window.location.reload();
                    return;
                }
            }
        } catch (err) {
            console.error("status poll failed", err);
        } finally {
            if (!stopped) {
                timer = setTimeout(poll, POLL_MS);
            }
        }
    }

    function start() {
        if (collectActiveIds().length === 0) return;
        clearTimeout(timer);
        stopped = false;
        timer = setTimeout(poll, POLL_MS);
    }

    // Expose a restart hook so AJAX-rendered lists (search.js) can re-arm polling.
    window.__restartStatusPoll = start;

    document.addEventListener("DOMContentLoaded", start);
})();
