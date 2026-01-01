(function () {
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

    document.addEventListener("DOMContentLoaded", () => {
        const root = document.getElementById("chatRoot");
        const form = document.getElementById("chatForm");
        const ta = document.getElementById("chatMessage");
        const chatScroll = document.getElementById("chatScroll");
        const sendBtn = form?.querySelector('button[type="submit"]');

        if (!root || !form || !ta || !chatScroll) return;

        // ✅ เอาจาก data attribute ที่ template render แล้ว
        const chatApiUrl = root.getAttribute("data-chat-api-url") || "";

        // ✅ เอา CSRF จาก hidden input ในฟอร์ม (ชัวร์สุด)
        const csrf = form.querySelector('input[name="csrfmiddlewaretoken"]')?.value || "";

        // auto-grow
        const autoGrow = () => {
            ta.style.height = "auto";
            ta.style.height = Math.min(140, ta.scrollHeight) + "px";
        };
        ta.addEventListener("input", autoGrow);
        autoGrow();

        // Enter send
        ta.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (ta.value.trim().length === 0) return;
                form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
            }
        });

        form.addEventListener("submit", async (e) => {
            e.preventDefault();

            const text = ta.value.trim();
            if (!text) return;
            if (!chatApiUrl) {
                alert("Missing chat api url (data-chat-api-url)");
                return;
            }

            // disable
            if (sendBtn) sendBtn.disabled = true;
            ta.value = "";
            autoGrow();

            // append user bubble
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

            // thinking bubble
            const thinkingId = "thinking-" + Date.now();
            chatScroll.insertAdjacentHTML("beforeend", `
        <div id="${thinkingId}" class="flex justify-start gap-3">
          <div class="mt-0.5 hidden sm:flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-600 ring-1 ring-slate-200 dark:bg-slate-800 dark:text-slate-200 dark:ring-slate-700">
            AI
          </div>
          <div class="max-w-[90%] sm:max-w-[75%]">
            <div class="flex items-center gap-2 mb-1">
              <span class="text-xs text-slate-400">Assistant</span>
            </div>
            <div class="rounded-2xl rounded-tl-sm bg-slate-100 px-4 py-2.5 text-sm leading-relaxed text-slate-900 shadow-sm dark:bg-slate-900 dark:text-slate-100 dark:ring-1 dark:ring-white/10">
              <span class="opacity-80">Thinking…</span>
            </div>
            <div class="mt-1 text-[11px] text-slate-400">Now</div>
          </div>
        </div>
      `);

            scrollToBottom();

            try {
                const body = new URLSearchParams();
                body.set("message", text);

                const resp = await fetch(chatApiUrl, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-CSRFToken": csrf,
                    },
                    body: body.toString(),
                });

                // ✅ กันกรณีได้ HTML กลับมา (404/500) จะได้อ่านข้อความได้
                const contentType = resp.headers.get("content-type") || "";
                const raw = await resp.text();

                if (!contentType.includes("application/json")) {
                    throw new Error("Server did not return JSON. Status " + resp.status);
                }

                const data = JSON.parse(raw);
                if (!resp.ok || !data.ok) throw new Error(data.error || "Request failed");

                const node = document.getElementById(thinkingId);
                if (node) {
                    node.querySelector(".rounded-2xl").innerHTML =
                        escapeHtml(data.assistant || "").replace(/\n/g, "<br>");
                    node.querySelector(".mt-1").textContent = data.created_at || "";
                }
            } catch (err) {
                const node = document.getElementById(thinkingId);
                if (node) {
                    node.querySelector(".rounded-2xl").innerHTML =
                        `<span class="text-red-600 dark:text-red-300">Error: ${escapeHtml(String(err?.message || err))}</span>`;
                }
            } finally {
                if (sendBtn) sendBtn.disabled = false;
                ta.focus();
                scrollToBottom();
            }
        });

        scrollToBottom();
        ta.focus();
    });
})();
