(function () {
    const state = {
        isSending: false,
        controller: null,
        requestId: null,
        thinkingId: null,
        assistantText: "",
    };

    function escapeHtml(s) {
        return (s || "").replace(/[&<>"']/g, (c) => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;",
            '"': "&quot;", "'": "&#39;",
        }[c]));
    }

    function genRequestId() {
        try {
            if (crypto && typeof crypto.randomUUID === "function") return crypto.randomUUID();
        } catch (_) { }
        return "rid-" + Date.now() + "-" + Math.random().toString(16).slice(2);
    }

    function removeEmptyState() {
        const empty = document.getElementById("chatEmptyState");
        if (empty) empty.remove();
    }

    function scrollToBottom() {
        const el = document.getElementById("chatScroll");
        if (!el) return;
        el.scrollTop = el.scrollHeight;
    }

    function setButton(btn, sending) {
        state.isSending = sending;
        if (!btn) return;

        // ปุ่มเดียว: ส่ง ↔ ยกเลิก
        btn.type = sending ? "button" : "submit";
        btn.textContent = sending ? "Cancel" : "Send";
        btn.classList.toggle("btn-outline", sending);
        btn.classList.toggle("btn", !sending);
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
            <div class="mt-1 text-right text-[11px] text-slate-400">Now</div>
            </div>
        </div>
        `);
    }

    function appendThinking(chatScroll) {
        const id = "thinking-" + Date.now();
        state.thinkingId = id;
        state.assistantText = "";

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
            <div class="assistant-time mt-1 text-[11px] text-slate-400">Now</div>
            </div>
        </div>
        `);

        return id;
    }

    function setAssistantHtml(id, html, createdAt) {
        const node = document.getElementById(id);
        if (!node) return;
        const bubble = node.querySelector(".assistant-bubble");
        const time = node.querySelector(".assistant-time");
        if (bubble) bubble.innerHTML = html;
        if (time && createdAt) time.textContent = createdAt;
    }

    // Parse SSE from fetch stream:
    // expects lines: "event: token" + "data: {...}" separated by blank line
    async function readSSE(resp, handlers) {
        const reader = resp.body.getReader();
        const decoder = new TextDecoder("utf-8");

        let buf = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buf += decoder.decode(value, { stream: true });

            // split by SSE event separator
            let parts = buf.split("\n\n");
            buf = parts.pop() || "";

            for (const chunk of parts) {
                const lines = chunk.split("\n");
                let eventName = "message";
                let dataLine = "";

                for (const line of lines) {
                    if (line.startsWith("event:")) eventName = line.slice(6).trim();
                    else if (line.startsWith("data:")) dataLine += line.slice(5).trim();
                }

                if (!dataLine) continue;

                let data;
                try { data = JSON.parse(dataLine); } catch { data = { raw: dataLine }; }

                if (handlers[eventName]) handlers[eventName](data);
            }
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        const root = document.getElementById("chatRoot");
        const form = document.getElementById("chatForm");
        const ta = document.getElementById("chatMessage");
        const chatScroll = document.getElementById("chatScroll");
        const btn = document.getElementById("sendBtn");

        if (!root || !form || !ta || !chatScroll || !btn) return;

        const streamUrl = root.getAttribute("data-chat-stream-url") || "";
        const cancelUrl = root.getAttribute("data-chat-cancel-url") || "";
        const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value || "";

        const autoGrow = () => {
            ta.style.height = "auto";
            ta.style.height = Math.min(140, ta.scrollHeight) + "px";
        };
        ta.addEventListener("input", autoGrow);
        autoGrow();

        // Enter = submit (เฉพาะตอนยังไม่ sending)
        ta.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (state.isSending) return;
                if (ta.value.trim().length === 0) return;
                form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
            }
        });

        // ปุ่มเดียว: ถ้ากำลังส่ง → Cancel
        btn.addEventListener("click", async () => {
            if (!state.isSending) return; // ตอนปกติให้ submit ตาม form

            // cancel server best-effort
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
            } catch (_) { }

            // abort client
            try { state.controller?.abort(); } catch (_) { }
        });

        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            if (state.isSending) return;

            const text = ta.value.trim();
            if (!text) return;
            if (!streamUrl) {
                alert("Missing stream url");
                return;
            }

            // new request id per message
            state.requestId = genRequestId();

            // UI
            ta.value = "";
            autoGrow();
            removeEmptyState();
            appendUser(chatScroll, text);
            const thinkingId = appendThinking(chatScroll);
            scrollToBottom();

            // lock UI
            state.controller = new AbortController();
            ta.disabled = true;
            ta.placeholder = "Thinking…";
            setButton(btn, true);

            try {
                const body = new URLSearchParams();
                body.set("message", text);
                body.set("request_id", state.requestId);

                const resp = await fetch(streamUrl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-CSRFToken": csrf,
                        "Accept": "text/event-stream",
                    },
                    body: body.toString(),
                    signal: state.controller.signal,
                });

                if (!resp.ok) {
                    const ct = resp.headers.get("content-type") || "";
                    let msg = `HTTP ${resp.status}`;
                    try {
                        if (ct.includes("application/json")) {
                            const j = await resp.json();
                            msg = j?.error ? `${j.error}` : msg;
                        } else {
                            const raw = await resp.text().catch(() => "");
                            msg = raw ? raw.slice(0, 180) : msg;
                        }
                    } catch (_) { }

                    // แยกเคส 429 ให้ชัด
                    if (resp.status === 429) {
                        throw new Error(msg || "Daily limit reached. Please try again tomorrow.");
                    }
                    throw new Error(msg);
                }


                // update bubble as tokens arrive
                let started = false;

                await readSSE(resp, {
                    token: (d) => {
                        const t = d?.t || "";
                        if (!t) return;

                        // first token remove "Thinking…"
                        if (!started) {
                            started = true;
                            state.assistantText = "";
                        }

                        state.assistantText += t;
                        setAssistantHtml(
                            thinkingId,
                            escapeHtml(state.assistantText).replace(/\n/g, "<br>"),
                            "" // ยังไม่ต้องใส่เวลา
                        );
                        scrollToBottom();
                    },

                    done: (d) => {
                        // finalize time label
                        setAssistantHtml(
                            thinkingId,
                            escapeHtml(state.assistantText || "").replace(/\n/g, "<br>") || `<span class="opacity-80">No response.</span>`,
                            d?.created_at || ""
                        );
                    },

                    canceled: () => {
                        setAssistantHtml(thinkingId, `<span class="opacity-80">Canceled.</span>`, "");
                    },

                    error: (d) => {
                        setAssistantHtml(
                            thinkingId,
                            `<span class="text-red-600 dark:text-red-300">Error: ${escapeHtml(d?.error || "Unknown error")}</span>`,
                            ""
                        );
                    },
                });

            } catch (err) {
                if (err && err.name === "AbortError") {
                    setAssistantHtml(thinkingId, `<span class="opacity-80">Canceled.</span>`, "");
                } else {
                    const em = String(err?.message || err);

                    const isQuota = /daily|limit|quota|429/i.test(em);
                    const html = isQuota
                        ? `<span class="text-amber-700 dark:text-amber-300">Limit reached: ${escapeHtml(em)}<br><span class="opacity-80 text-[12px]">Tip: try again tomorrow or lower usage.</span></span>`
                        : `<span class="text-red-600 dark:text-red-300">Error: ${escapeHtml(em)}</span>`;

                    setAssistantHtml(thinkingId, html, "");
                }
            } finally {
                state.controller = null;
                state.requestId = null;

                ta.disabled = false;
                ta.placeholder = "Ask a question…";
                setButton(btn, false);
                ta.focus();
                scrollToBottom();
            }
        });

        setButton(btn, false);
        scrollToBottom();
        ta.focus();
    });
})();