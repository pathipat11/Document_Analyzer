(function () {
    const state = {
        isSending: false,
        controller: null,
        requestId: null,
        thinkingId: null,
        assistantText: "",
        editingMessageId: null,
        originalTailHtml: null,
        isEditing: false,
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

    function nl2br(s) {
        return escapeHtml(s).replace(/\n/g, "<br>");
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
        btn.type = sending ? "button" : "submit";
        btn.textContent = sending ? "Cancel" : "Send";
        btn.classList.toggle("btn-outline", sending);
        btn.classList.toggle("btn", !sending);
    }

    function buildUserRowHtml({ messageId = "", text = "", createdAt = "Now" }) {
        return `
            <div class="flex justify-end message-row user-row" data-message-id="${messageId}" data-role="user">
                <div class="max-w-[85%] sm:max-w-[70%] flex flex-col items-end user-message">
                    <div class="flex items-center justify-end gap-2 mb-1">
                        <span class="text-xs text-slate-400">You</span>
                    </div>

                    <div class="inline-block wrap-break-word rounded-2xl rounded-tr-sm bg-blue-500 px-4 py-2.5 text-sm leading-relaxed text-white shadow-sm dark:bg-blue-900 dark:text-slate-100 dark:ring-1 dark:ring-white/10">
                        ${nl2br(text)}
                    </div>

                    <div class="mt-1 flex justify-end gap-3 user-actions">
                        <button type="button"
                            class="editMsgBtn text-[11px] text-blue-600 hover:underline dark:text-blue-300"
                            data-message-id="${messageId}"
                            data-message="${escapeHtml(text)}">
                            Edit
                        </button>
                    </div>

                    <div class="mt-1 text-right text-[11px] text-slate-400 message-time">
                        ${createdAt}
                    </div>
                </div>
            </div>
        `;
    }

    function buildAssistantRowHtml({ messageId = "", userMessageId = "", text = "", createdAt = "Now", thinking = false }) {
        return `
            <div class="flex justify-start gap-3 message-row assistant-row" data-message-id="${messageId}" data-role="assistant">
                <div class="mt-0.5 hidden sm:flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-600 ring-1 ring-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700">
                    AI
                </div>

                <div class="max-w-[90%] sm:max-w-[75%] flex flex-col items-start">
                    <div class="flex items-center gap-2 mb-1">
                        <span class="text-xs text-slate-400">Assistant</span>
                    </div>

                    <div class="assistant-bubble inline-block wrap-break-word rounded-2xl rounded-tl-sm bg-slate-100 px-4 py-2.5 text-sm leading-relaxed text-slate-900 shadow-sm dark:bg-slate-900 dark:text-slate-100 dark:ring-1 dark:ring-white/10">
                        ${thinking ? `<span class="opacity-80">Thinking…</span>` : nl2br(text)}
                    </div>

                    <div class="mt-1 flex justify-start gap-3 assistant-actions">
                        ${!thinking && userMessageId ? `
                            <button type="button"
                                class="regenMsgBtn text-[11px] text-slate-500 hover:underline dark:text-slate-300"
                                data-message-id="${userMessageId}">
                                Regenerate
                            </button>
                        ` : ""}
                    </div>

                    <div class="assistant-time mt-1 text-[11px] text-slate-400">
                        ${createdAt}
                    </div>
                </div>
            </div>
        `;
    }

    function appendUser(chatScroll, text) {
        chatScroll.insertAdjacentHTML("beforeend", buildUserRowHtml({ text, createdAt: "Now" }));
        return chatScroll.lastElementChild;
    }

    function appendThinking(chatScroll) {
        const id = "thinking-" + Date.now();
        state.thinkingId = id;
        state.assistantText = "";

        chatScroll.insertAdjacentHTML("beforeend", `
            <div id="${id}">
                ${buildAssistantRowHtml({ thinking: true, createdAt: "Now" })}
            </div>
        `);

        return id;
    }

    function setAssistantHtml(id, html, createdAt) {
        const wrapper = document.getElementById(id);
        if (!wrapper) return;
        const bubble = wrapper.querySelector(".assistant-bubble");
        const time = wrapper.querySelector(".assistant-time");
        if (bubble) bubble.innerHTML = html;
        if (time && createdAt) time.textContent = createdAt;
    }

    function setAssistantMeta(id, assistantMessageId, userMessageId) {
        const wrapper = document.getElementById(id);
        if (!wrapper) return;

        const row = wrapper.querySelector(".assistant-row");
        const actions = wrapper.querySelector(".assistant-actions");

        if (row && assistantMessageId) {
            row.setAttribute("data-message-id", assistantMessageId);
        }

        if (actions && userMessageId) {
            actions.innerHTML = `
                <button type="button"
                    class="regenMsgBtn text-[11px] text-slate-500 hover:underline dark:text-slate-300"
                    data-message-id="${userMessageId}">
                    Regenerate
                </button>
            `;
        }
    }

    function replaceAssistantMessage(oldAssistantId, payload) {
        const oldNode = document.querySelector(`.assistant-row[data-message-id="${oldAssistantId}"]`);
        if (!oldNode) return false;

        oldNode.outerHTML = buildAssistantRowHtml({
            messageId: payload.assistant_message_id,
            userMessageId: payload.parent_user_message_id,
            text: payload.assistant,
            createdAt: payload.created_at,
        });

        return true;
    }

    function replaceUserMessage(userMessageId, newText) {
        const node = document.querySelector(`.user-row[data-message-id="${userMessageId}"]`);
        if (!node) return false;

        const bubble = node.querySelector(".user-message > .inline-block");
        const editBtn = node.querySelector(".editMsgBtn");

        if (bubble) bubble.innerHTML = nl2br(newText);
        if (editBtn) editBtn.dataset.message = newText;

        return true;
    }

    function snapshotMessagesAfter(messageId) {
        if (!messageId) return "";

        const rows = Array.from(document.querySelectorAll(".message-row"));
        let found = false;
        const htmlParts = [];

        for (const row of rows) {
            const rowId = row.getAttribute("data-message-id");

            if (String(rowId) === String(messageId)) {
                found = true;
                continue;
            }

            if (found) {
                htmlParts.push(row.outerHTML);
            }
        }

        return htmlParts.join("");
    }

    function restoreMessagesAfter(messageId, html) {
        if (!messageId || !html) return;

        const row = document.querySelector(`.message-row[data-message-id="${messageId}"]`);
        if (!row) return;

        row.insertAdjacentHTML("afterend", html);
    }

    function removeMessagesAfter(messageId) {
        if (!messageId) return;

        const rows = Array.from(document.querySelectorAll(".message-row"));
        let found = false;

        for (const row of rows) {
            const rowId = row.getAttribute("data-message-id");

            if (String(rowId) === String(messageId)) {
                found = true;
                continue;
            }

            if (found) {
                row.remove();
            }
        }
    }

    function replaceUserRowMessageId(oldId, newId, newText, createdAt = "Now") {
        const row = document.querySelector(`.user-row[data-message-id="${oldId}"]`);
        if (!row) return false;

        row.setAttribute("data-message-id", newId);

        const bubble = row.querySelector(".user-message > .inline-block");
        const time = row.querySelector(".message-time");
        const editBtn = row.querySelector(".editMsgBtn");

        if (bubble) bubble.innerHTML = nl2br(newText);
        if (time) time.textContent = createdAt;
        if (editBtn) {
            editBtn.dataset.messageId = newId;
            editBtn.dataset.message = newText;
        }

        return true;
    }

    function syncEditUI() {
        const cancelBtn = document.getElementById("cancelEditBtn");
        const ta = document.getElementById("chatMessage");
        if (!cancelBtn || !ta) return;

        if (state.isEditing) {
            cancelBtn.classList.remove("hidden");
            ta.placeholder = "Edit your message…";
        } else {
            cancelBtn.classList.add("hidden");
            ta.placeholder = "Ask a question…";
        }
    }

    async function readSSE(resp, handlers) {
        const reader = resp.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buf = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buf += decoder.decode(value, { stream: true });

            const parts = buf.split("\n\n");
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
                try {
                    data = JSON.parse(dataLine);
                } catch {
                    data = { raw: dataLine };
                }

                if (handlers[eventName]) handlers[eventName](data);
            }
        }
    }

    document.addEventListener("click", (e) => {
        const btn = e.target.closest(".editMsgBtn");
        if (!btn) return;

        const ta = document.getElementById("chatMessage");
        if (!ta) return;

        state.editingMessageId = btn.dataset.messageId || null;
        state.originalTailHtml = snapshotMessagesAfter(state.editingMessageId);
        state.isEditing = true;
        syncEditUI();

        ta.value = btn.dataset.message || "";
        removeMessagesAfter(state.editingMessageId);

        ta.focus();
        ta.style.height = "auto";
        ta.style.height = Math.min(140, ta.scrollHeight) + "px";
    });

    document.addEventListener("DOMContentLoaded", () => {
        const root = document.getElementById("chatRoot");
        const form = document.getElementById("chatForm");
        const ta = document.getElementById("chatMessage");
        const chatScroll = document.getElementById("chatScroll");
        const btn = document.getElementById("sendBtn");
        const cancelEditBtn = document.getElementById("cancelEditBtn");

        if (!root || !form || !ta || !chatScroll || !btn) return;

        const streamUrl = root.getAttribute("data-chat-stream-url") || "";
        const cancelUrl = root.getAttribute("data-chat-cancel-url") || "";
        const resetUrl = root.getAttribute("data-chat-reset-url") || "";
        const regenerateUrl = root.getAttribute("data-chat-regenerate-url") || "";
        const resetBtn = document.getElementById("resetChatBtn");
        const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value || "";

        if (cancelEditBtn) {
            cancelEditBtn.addEventListener("click", () => {
                if (!state.isEditing || !state.editingMessageId) return;

                restoreMessagesAfter(state.editingMessageId, state.originalTailHtml);

                state.editingMessageId = null;
                state.originalTailHtml = null;
                state.isEditing = false;

                ta.value = "";
                ta.style.height = "auto";
                ta.style.height = Math.min(140, ta.scrollHeight) + "px";

                syncEditUI();
                scrollToBottom();
            });
        }

        if (resetBtn) {
            resetBtn.addEventListener("click", async () => {
                const ok = confirm("Reset this chat? All messages in this conversation will be removed.");
                if (!ok) return;

                try {
                    const res = await fetch(resetUrl, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/x-www-form-urlencoded",
                            "X-CSRFToken": csrf,
                        },
                        body: "",
                    });

                    const data = await res.json();
                    if (!res.ok || !data.ok) throw new Error(data?.error || "Reset failed");

                    chatScroll.innerHTML = `
                        <div id="chatEmptyState" class="grid place-items-center h-full">
                            <div class="text-center">
                                <div class="mx-auto mb-2 h-10 w-10 rounded-2xl bg-slate-100 dark:bg-slate-800"></div>
                                <div class="text-sm font-medium text-slate-700 dark:text-slate-200">Start a conversation</div>
                                <div class="mt-1 text-sm text-slate-500 dark:text-slate-400">
                                    Ask a question about your document / notebook.
                                </div>
                                <div class="mt-3 text-xs text-slate-400">
                                    Tip: Enter = send • Shift+Enter = new line
                                </div>
                            </div>
                        </div>
                    `;

                    state.editingMessageId = null;
                    state.originalTailHtml = null;
                    state.isEditing = false;
                    syncEditUI();
                    if (window.showToast) window.showToast("Chat reset.", "success");
                } catch (_) {
                    if (window.showToast) window.showToast("Reset failed.", "error");
                }
            });
        }

        document.addEventListener("click", async (e) => {
            const regenBtn = e.target.closest(".regenMsgBtn");
            if (!regenBtn) return;

            const userMessageId = regenBtn.dataset.messageId;
            if (!userMessageId || !regenerateUrl || state.isSending) return;

            removeMessagesAfter(userMessageId);

            const thinkingId = appendThinking(chatScroll);
            scrollToBottom();

            regenBtn.disabled = true;
            regenBtn.classList.add("opacity-50", "cursor-not-allowed");

            try {
                const body = new URLSearchParams();
                body.set("user_message_id", userMessageId);

                const res = await fetch(regenerateUrl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-CSRFToken": csrf,
                    },
                    body: body.toString(),
                });

                const data = await res.json();
                if (!res.ok || !data.ok) throw new Error(data?.error || "Regenerate failed");

                setAssistantHtml(
                    thinkingId,
                    nl2br(data.assistant || ""),
                    data.created_at || ""
                );

                setAssistantMeta(
                    thinkingId,
                    data.assistant_message_id,
                    data.parent_user_message_id
                );

                scrollToBottom();

                if (window.showToast) window.showToast("Regenerated.", "success");
            } catch (_) {
                const wrapper = document.getElementById(thinkingId);
                if (wrapper) wrapper.remove();
                if (window.showToast) window.showToast("Regenerate failed.", "error");
            } finally {
                regenBtn.disabled = false;
                regenBtn.classList.remove("opacity-50", "cursor-not-allowed");
            }
        });

        const autoGrow = () => {
            ta.style.height = "auto";
            ta.style.height = Math.min(140, ta.scrollHeight) + "px";
        };
        ta.addEventListener("input", autoGrow);
        autoGrow();

        ta.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (state.isSending) return;
                if (ta.value.trim().length === 0) return;
                form.requestSubmit
                    ? form.requestSubmit()
                    : form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
            }
        });

        btn.addEventListener("click", async () => {
            if (!state.isSending) return;

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

            try {
                state.controller?.abort();
            } catch (_) { }
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

            state.requestId = genRequestId();

            const editingMessageId = state.editingMessageId;
            state.editingMessageId = null;
            state.isEditing = false;
            syncEditUI();

            ta.value = "";
            autoGrow();
            removeEmptyState();

            let thinkingId;
            if (editingMessageId) {
                thinkingId = appendThinking(chatScroll);
            } else {
                appendUser(chatScroll, text);
                thinkingId = appendThinking(chatScroll);
            }

            scrollToBottom();

            state.controller = new AbortController();
            ta.disabled = true;
            ta.placeholder = "Thinking…";
            setButton(btn, true);

            try {
                const body = new URLSearchParams();
                body.set("message", text);
                body.set("request_id", state.requestId);

                if (editingMessageId) {
                    body.set("edit_message_id", editingMessageId);
                }

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

                    if (resp.status === 429) {
                        throw new Error(msg || "Daily limit reached. Please try again tomorrow.");
                    }
                    throw new Error(msg);
                }

                let started = false;

                await readSSE(resp, {
                    token: (d) => {
                        const t = d?.t || "";
                        if (!t) return;

                        if (!started) {
                            started = true;
                            state.assistantText = "";
                        }

                        state.assistantText += t;
                        setAssistantHtml(
                            thinkingId,
                            nl2br(state.assistantText),
                            ""
                        );
                        scrollToBottom();
                    },

                    done: (d) => {
                        state.originalTailHtml = null;
                        state.isEditing = false;
                        syncEditUI();
                        setAssistantHtml(
                            thinkingId,
                            nl2br(state.assistantText || "") || `<span class="opacity-80">No response.</span>`,
                            d?.created_at || ""
                        );

                        setAssistantMeta(
                            thinkingId,
                            d?.assistant_message_id,
                            d?.user_message_id
                        );

                        if (editingMessageId) {
                            replaceUserRowMessageId(
                                editingMessageId,
                                d?.user_message_id,
                                text,
                                d?.created_at || "Now"
                            );
                        } else {
                            const userRows = document.querySelectorAll(".user-row");
                            const lastUser = userRows[userRows.length - 1];
                            if (lastUser && d?.user_message_id) {
                                lastUser.setAttribute("data-message-id", d.user_message_id);
                                const editBtn = lastUser.querySelector(".editMsgBtn");
                                if (editBtn) {
                                    editBtn.dataset.messageId = d.user_message_id;
                                    editBtn.dataset.message = text;
                                }
                            }
                        }

                        if (window.Usage && typeof window.Usage.refresh === "function") {
                            window.Usage.refresh({ reason: "chat_done" });
                        }
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

                if (editingMessageId && state.originalTailHtml) {
                    restoreMessagesAfter(editingMessageId, state.originalTailHtml);
                    state.originalTailHtml = null;
                    state.editingMessageId = null;
                    state.isEditing = false;
                    syncEditUI();
                }
            } finally {
                state.controller = null;
                state.requestId = null;
                ta.disabled = false;
                setButton(btn, false);
                syncEditUI();
                ta.focus();
                scrollToBottom();
            }
        });

        setButton(btn, false);
        scrollToBottom();
        ta.focus();
    });
})();