(function () {
    const state = {
        isSending: false,
        controller: null,
        thinkingId: null,
        requestId: null,
    };

    function escapeHtml(s) {
        return (s || "").replace(/[&<>"']/g, (c) => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
        }[c]));
    }

    function scrollToBottom() {
        const el = document.getElementById("chatScroll");
        if (!el) return;
        el.scrollTop = el.scrollHeight;
    }

    function setSendingUI({ sending, sendBtn, cancelBtn, ta }) {
        state.isSending = sending;

        if (sendBtn) {
            sendBtn.disabled = sending;
            sendBtn.textContent = sending ? "Sending…" : "Send";
        }
        if (cancelBtn) {
            cancelBtn.classList.toggle("hidden", !sending);
            cancelBtn.disabled = !sending;
        }
        if (ta) {
            ta.disabled = sending;
            ta.placeholder = sending ? "Thinking…" : "Ask a question…";
        }
    }

    function nowLabel() {
        return "Now";
    }

    function appendUser(chatScroll, text) {
        chatScroll.insertAdjacentHTML("beforeend", `
      <div class="flex justify-end">
        <div class="max-w-[85%] sm:max-w-[70%]">
          <div class="flex items-center justify-end gap-2 mb-1">
            <span class="text-xs text-slate-400">You</span>
          </div>
          <div class="rounded-2xl rounded-tr-sm bg-blue-600 px-4 py-2.5 text-sm leading-relaxed text-white shadow-sm">
            ${escapeHtml(text).replace(/\n/g, "<br>")}
          </div>
          <div class="mt-1 text-right text-[11px] text-slate-400">${nowLabel()}</div>
        </div>
      </div>
    `);
    }

    function appendThinking(chatScroll) {
        const id = "thinking-" + Date.now();
        state.thinkingId = id;

        chatScroll.insertAdjacentHTML("beforeend", `
      <div id="${id}" class="flex justify-start gap-3">
        <div class="mt-0.5 hidden sm:flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-600 ring-1 ring-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700">
          AI
        </div>
        <div class="max-w-[90%] sm:max-w-[75%]">
          <div class="flex items-center gap-2 mb-1">
            <span class="text-xs text-slate-400">Assistant</span>
          </div>
          <div class="assistant-bubble rounded-2xl rounded-tl-sm bg-slate-100 px-4 py-2.5 text-sm leading-relaxed text-slate-900 shadow-sm dark:bg-slate-900 dark:text-slate-100 dark:ring-1 dark:ring-white/10">
            <span class="opacity-80">Thinking…</span>
          </div>
          <div class="assistant-time mt-1 text-[11px] text-slate-400">${nowLabel()}</div>
        </div>
      </div>
    `);

        return id;
    }

    function updateThinkingContent(id, htmlText, createdAt) {
        const node = document.getElementById(id);
        if (!node) return;

        const bubble = node.querySelector(".assistant-bubble");
        const time = node.querySelector(".assistant-time");

        if (bubble) bubble.innerHTML = htmlText;
        if (time && createdAt) time.textContent = createdAt;
    }

    function genRequestId() {
        try {
            if (crypto && typeof crypto.randomUUID === "function") return crypto.randomUUID();
        } catch (_) { }
        return "rid-" + Date.now() + "-" + Math.random().toString(16).slice(2);
    }

    document.addEventListener("DOMContentLoaded", () => {
        const root = document.getElementById("chatRoot");
        const form = document.getElementById("chatForm");
        const ta = document.getElementById("chatMessage");
        const chatScroll = document.getElementById("chatScroll");
        const sendBtn = form?.querySelector('button[type="submit"]');
        const cancelBtn = document.getElementById("cancelBtn");

        if (!root || !form || !ta || !chatScroll) return;

        const chatApiUrl = root.getAttribute("data-chat-api-url") || "";
        const cancelUrl = root.getAttribute("data-chat-cancel-url") || "";
        const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value || "";

        // auto-grow textarea
        const autoGrow = () => {
            ta.style.height = "auto";
            ta.style.height = Math.min(140, ta.scrollHeight) + "px";
        };
        ta.addEventListener("input", autoGrow);
        autoGrow();

        // Enter = send, Shift+Enter = newline (กันส่งซ้ำ)
        ta.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (state.isSending) return;
                if (ta.value.trim().length === 0) return;

                if (form.requestSubmit) form.requestSubmit();
                else form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
            }
        });

        // Cancel: best-effort server + abort fetch
        cancelBtn?.addEventListener("click", async () => {
            if (!state.isSending) return;

            // 1) tell server to ignore saving assistant (best-effort)
            try {
                if (cancelUrl && state.requestId) {
                    const b = new URLSearchParams();
                    b.set("request_id", state.requestId);

                    await fetch(cancelUrl, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/x-www-form-urlencoded",
                            "X-CSRFToken": csrf,
                        },
                        body: b.toString(),
                    });
                }
            } catch (_) {
                // ignore
            }

            // 2) abort client fetch immediately
            try {
                state.controller?.abort();
            } catch (_) { }
        });

        // Submit (AJAX)
        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            if (state.isSending) return;

            const text = ta.value.trim();
            if (!text) return;

            if (!chatApiUrl) {
                alert("Missing chat api url");
                return;
            }

            // ✅ สร้าง request_id ใหม่ “ต่อข้อความ”
            state.requestId = genRequestId();

            // clear input + append UI
            ta.value = "";
            autoGrow();
            appendUser(chatScroll, text);

            const thinkingId = appendThinking(chatScroll);
            scrollToBottom();

            // setup controller
            state.controller = new AbortController();
            setSendingUI({ sending: true, sendBtn, cancelBtn, ta });

            try {
                const body = new URLSearchParams();
                body.set("message", text);
                body.set("request_id", state.requestId);

                const resp = await fetch(chatApiUrl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-CSRFToken": csrf,
                    },
                    body: body.toString(),
                    signal: state.controller.signal,
                });

                const ct = resp.headers.get("content-type") || "";
                const raw = await resp.text();

                // ถ้าไม่ใช่ JSON (เช่นโดน redirect ไป login -> HTML) ให้ขึ้น error readable
                if (!ct.includes("application/json")) {
                    throw new Error("Server did not return JSON (status " + resp.status + ")");
                }

                let data;
                try {
                    data = JSON.parse(raw);
                } catch (_) {
                    throw new Error("Invalid JSON response (status " + resp.status + ")");
                }

                // ✅ canceled by server
                if (resp.status === 409 && data && data.canceled) {
                    updateThinkingContent(thinkingId, `<span class="opacity-80">Canceled.</span>`, "");
                    return;
                }

                if (!resp.ok || !data.ok) {
                    throw new Error((data && data.error) ? data.error : "Request failed");
                }

                updateThinkingContent(
                    thinkingId,
                    escapeHtml(data.assistant || "").replace(/\n/g, "<br>"),
                    data.created_at || ""
                );
            } catch (err) {
                if (err && err.name === "AbortError") {
                    // client aborted (Cancel)
                    updateThinkingContent(thinkingId, `<span class="opacity-80">Canceled.</span>`, "");
                } else {
                    updateThinkingContent(
                        thinkingId,
                        `<span class="text-red-600 dark:text-red-300">Error: ${escapeHtml(String(err?.message || err))}</span>`,
                        ""
                    );
                }
            } finally {
                state.controller = null;
                state.requestId = null;
                setSendingUI({ sending: false, sendBtn, cancelBtn, ta });
                ta.focus();
                scrollToBottom();
            }
        });

        // initial state
        setSendingUI({ sending: false, sendBtn, cancelBtn, ta });
        scrollToBottom();
        ta.focus();
    });
})();