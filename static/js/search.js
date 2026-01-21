const tbody = document.getElementById("docsTbody");
const searchUrl = tbody?.dataset?.searchUrl || "";
const qInput = document.getElementById("qInput");
const typeSelect = document.getElementById("typeSelect");
const fromInput = document.getElementById("fromInput");
const toInput = document.getElementById("toInput");
const docsCount = document.getElementById("docsCount");
const searchStatus = document.getElementById("searchStatus");

if (qInput && typeSelect && fromInput && toInput && tbody) {
    let timer = null;
    let controller = null;
    let lastSig = "";
    let livePage = getPageFromUrl(); // ✅ ใช้ page จาก URL

    function getPageFromUrl() {
        const u = new URL(window.location.href);
        const p = parseInt(u.searchParams.get("page") || "1", 10);
        return Number.isFinite(p) && p > 0 ? p : 1;
    }

    function setUrlParams(params) {
        const u = new URL(window.location.href);

        // เคลียร์ก่อน แล้วค่อย set ใหม่ตาม params (กัน query เก่าค้าง)
        ["q", "type", "from", "to", "page"].forEach(k => u.searchParams.delete(k));

        Object.entries(params).forEach(([k, v]) => {
            if (v !== undefined && v !== null && String(v).trim() !== "") {
                u.searchParams.set(k, String(v));
            }
        });

        // ไม่ reload แค่เปลี่ยน URL
        window.history.replaceState({}, "", u.toString());
    }

    const esc = (s) => {
        const div = document.createElement("div");
        div.textContent = s ?? "";
        return div.innerHTML;
    };

    function buildRow(d) {
        const chip = `<span class="inline-flex rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-200">${esc(d.document_type || "")}</span>`;
        const chatLabel = d.has_chat ? "Continue" : "Chat";
        const bubble = d.has_chat ? `<span class="mt-0.5 select-none text-xs">💬</span>` : "";

        const snippet = d.snippet
            ? `<div class="mt-2 text-xs leading-relaxed text-slate-600 dark:text-slate-300">${esc(d.snippet)}</div>`
            : "";

        return `
      <tr class="hover:bg-slate-50/70 dark:hover:bg-slate-900/30">
        <td class="px-4 py-3">
          <input type="checkbox" name="doc_ids" value="${d.id}"
            class="docCheckbox h-4 w-4 rounded border-slate-300 dark:border-slate-700"
            data-doc-id="${d.id}">
        </td>

        <td class="px-4 py-3">
          ${bubble}
          <a class="font-medium text-blue-700 hover:underline dark:text-blue-300" href="${d.detail_url}">
            ${esc(d.file_name || "")}
          </a>
          <div class="mt-1 text-xs text-slate-500 dark:text-slate-400">
            ${esc(String(d.char_count ?? 0))} chars
          </div>
          ${snippet}
        </td>

        <td class="px-4 py-3">${chip}</td>
        <td class="px-4 py-3">${esc(String(d.word_count ?? 0))}</td>
        <td class="px-4 py-3 text-slate-600 dark:text-slate-300">${esc(d.uploaded_at || "")}</td>

        <td class="px-4 py-3">
          <div class="flex items-center gap-2">
            <a class="btn-outline" href="${d.chat_url}">${chatLabel}</a>
          </div>
        </td>

        <td class="px-4 py-3">
          <button type="button"
            class="deleteBtn btn-outline text-red-400 dark:text-red-300 opacity-50 cursor-not-allowed"
            title="Delete disabled in live-search view (reload page to delete)">
            Delete
          </button>
        </td>
      </tr>
    `;
    }

    function getParams() {
        return {
            q: qInput.value.trim(),
            type: typeSelect.value.trim(),
            from: fromInput.value,
            to: toInput.value,
            page: livePage, // ✅ ใช้หน้าจาก URL/สถานะ
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

        if (controller) controller.abort();
        controller = new AbortController();

        const qs = new URLSearchParams();
        Object.entries(p).forEach(([k, v]) => {
            if (v !== undefined && v !== null && String(v).trim() !== "") qs.set(k, v);
        });

        if (searchStatus) searchStatus.classList.remove("hidden");

        try {
            const res = await fetch(`${searchUrl}?${qs.toString()}`, {
                headers: { "Accept": "application/json" },
                signal: controller.signal,
            });

            if (!res.ok) throw new Error(`HTTP ${res.status}`);

            const data = await res.json();
            if (!data.ok) throw new Error("Bad response");

            const items = data.items || [];

            tbody.innerHTML = items.length
                ? items.map(buildRow).join("")
                : `
            <tr>
                <td class="px-4 py-8 text-center text-sm text-slate-500 dark:text-slate-400" colspan="7">
                No documents found. Try another keyword or clear filters.
                </td>
            </tr>
            `;

            if (typeof window.__refreshCombineState === "function") {
                window.__refreshCombineState();
            }

            if (docsCount) docsCount.textContent = `${data.count ?? 0} documents`;

            setUrlParams(p);

        } catch (err) {
            if (err.name === "AbortError") return;
            console.error(err);
        } finally {
            if (searchStatus) searchStatus.classList.add("hidden");
        }
    }

    function scheduleSearch({ resetPage = false } = {}) {
        if (resetPage) livePage = 1; // ✅ เปลี่ยน filter = กลับไปหน้า 1
        clearTimeout(timer);
        timer = setTimeout(runSearch, 250);
    }

    qInput.addEventListener("input", () => scheduleSearch({ resetPage: true }));
    typeSelect.addEventListener("change", () => scheduleSearch({ resetPage: true }));
    fromInput.addEventListener("change", () => scheduleSearch({ resetPage: true }));
    toInput.addEventListener("change", () => scheduleSearch({ resetPage: true }));

    qInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") e.preventDefault();
    });

    runSearch();
}
