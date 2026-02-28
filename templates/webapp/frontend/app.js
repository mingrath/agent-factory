const messagesEl = document.getElementById("messages");
const form = document.getElementById("input-form");
const input = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");

let history = [];
let isLoading = false;

// Auto-resize textarea
input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 120) + "px";
});

// Submit on Enter (Shift+Enter for newline)
input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        form.dispatchEvent(new Event("submit"));
    }
});

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message || isLoading) return;

    addMessage("user", message);
    history.push({ role: "user", content: message });

    input.value = "";
    input.style.height = "auto";
    setLoading(true);

    const typingEl = addTypingIndicator();

    try {
        const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message, history: history.slice(0, -1) }),
        });

        if (!res.ok) throw new Error(`Server error: ${res.status}`);

        // Remove typing indicator, create streaming bubble
        typingEl.remove();
        const bubbleEl = addMessage("assistant", "");
        const bubble = bubbleEl.querySelector(".bubble");

        // Read SSE stream
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let fullText = "";
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                const data = line.slice(6);
                if (data === "[DONE]") continue;
                try {
                    fullText += JSON.parse(data);
                } catch {
                    fullText += data;
                }
                bubble.textContent = fullText;
                scrollToBottom();
            }
        }

        history.push({ role: "assistant", content: fullText });
    } catch (err) {
        typingEl.remove();
        addMessage("assistant", `Error: ${err.message}`);
    } finally {
        setLoading(false);
        input.focus();
    }
});

function addMessage(role, content) {
    const div = document.createElement("div");
    div.className = `message ${role}`;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = content;

    div.appendChild(bubble);
    messagesEl.appendChild(div);
    scrollToBottom();
    return div;
}

function addTypingIndicator() {
    const div = document.createElement("div");
    div.className = "message assistant";
    div.innerHTML = `<div class="typing-indicator">
        <span></span><span></span><span></span>
    </div>`;
    messagesEl.appendChild(div);
    scrollToBottom();
    return div;
}

function setLoading(loading) {
    isLoading = loading;
    sendBtn.disabled = loading;
}

function scrollToBottom() {
    const container = document.getElementById("chat-container");
    container.scrollTop = container.scrollHeight;
}
