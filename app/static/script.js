document.addEventListener('DOMContentLoaded', () => {
    // Navigation
    const navItems = document.querySelectorAll('.nav-item');
    const views = document.querySelectorAll('.view');

    navItems.forEach(item => {
        item.addEventListener('click', () => {
            navItems.forEach(n => n.classList.remove('active'));
            views.forEach(v => v.classList.add('hidden'));
            
            item.classList.add('active');
            document.getElementById(`${item.dataset.tab}-view`).classList.remove('hidden');
            
            if (item.dataset.tab === 'workers') fetchWorkers();
            if (item.dataset.tab === 'metrics') fetchMetrics();
        });
    });

    // Chat Logic
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const messagesArea = document.getElementById('chat-messages');
    const clearBtn = document.getElementById('clear-btn');
    const modelSelect = document.getElementById('model-select');
    
    let messages = [];

    function appendMessage(role, content) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;
        msgDiv.innerHTML = `
            <div class="avatar">${role === 'user' ? 'U' : 'AI'}</div>
            <div class="content">${marked.parse(content || '')}</div>
        `;
        messagesArea.appendChild(msgDiv);
        messagesArea.scrollTop = messagesArea.scrollHeight;
        return msgDiv;
    }

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const text = chatInput.value.trim();
        if (!text) return;

        chatInput.value = '';
        appendMessage('user', text);
        messages.push({ role: 'user', content: text });

        const aiMsgDiv = appendMessage('assistant', '');
        const contentDiv = aiMsgDiv.querySelector('.content');
        
        document.getElementById('debug-req-id').textContent = 'Routing...';
        document.getElementById('debug-latency').textContent = '...';
        
        try {
            const startTime = Date.now();
            const response = await fetch('/v1/chat/completions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: modelSelect.value,
                    messages: messages,
                    stream: true
                })
            });

            if (!response.ok) throw new Error(`Gateway Error: ${response.status}`);
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let aiText = '';
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, {stream: true});
                const lines = buffer.split('\n');
                
                // Keep the last partial line in the buffer
                buffer = lines.pop();
                
                for (const line of lines) {
                    if (line.trim().startsWith('data: ')) {
                        const dataStr = line.trim().slice(6);
                        if (dataStr === '[DONE]') continue;
                        try {
                            const data = JSON.parse(dataStr);
                            if (data.error) throw new Error(data.error);
                            if (data.choices && data.choices[0].delta && data.choices[0].delta.content) {
                                aiText += data.choices[0].delta.content;
                                contentDiv.innerHTML = marked.parse(aiText);
                                messagesArea.scrollTop = messagesArea.scrollHeight;
                            }
                            
                            document.getElementById('debug-req-id').textContent = `Req: ${data.id || '-'}`;
                            document.getElementById('debug-latency').textContent = `${Date.now() - startTime}ms`;
                        } catch (e) {
                            if (e.message !== "Unexpected end of JSON input" && !e.message.includes("JSON")) {
                                throw e; // Rethrow if it's our own Gateway error
                            }
                        }
                    }
                }
            }
            messages.push({ role: 'assistant', content: aiText });
        } catch (error) {
            contentDiv.innerHTML = `<span style="color:var(--error)">${error.message}</span>`;
            document.getElementById('debug-req-id').textContent = 'Failed';
        }
    });

    clearBtn.addEventListener('click', () => {
        messages = [];
        messagesArea.innerHTML = '';
        appendMessage('assistant', 'Conversation cleared.');
    });

    // Workers Dashboard
    async function fetchWorkers() {
        try {
            const res = await fetch('/workers');
            const data = await res.json();
            const tbody = document.getElementById('workers-tbody');
            tbody.innerHTML = '';
            
            Object.entries(data.workers).forEach(([name, w]) => {
                const isReady = w.status === 'ready';
                const statusClass = isReady ? 'status-ready' : 'status-offline';
                const uptime = w.uptime ? `${(w.uptime / 60).toFixed(1)}m` : '-';
                
                tbody.innerHTML += `
                    <tr>
                        <td>${name}</td>
                        <td>${w.host}:${w.port}</td>
                        <td>${w.model_name || 'N/A'}</td>
                        <td><span class="status-badge ${statusClass}">${w.status.toUpperCase()}</span></td>
                        <td>${w.active_requests}</td>
                        <td>${uptime}</td>
                    </tr>
                `;
            });
        } catch (e) {
            console.error('Failed to fetch workers', e);
        }
    }
    document.getElementById('refresh-workers').addEventListener('click', fetchWorkers);

    // Metrics Dashboard
    async function fetchMetrics() {
        try {
            const res = await fetch('/metrics');
            const data = await res.json();
            document.getElementById('metric-total').textContent = data.total_requests;
            document.getElementById('metric-success').textContent = data.successful_requests;
            document.getElementById('metric-failed').textContent = data.failed_requests;
            document.getElementById('metric-latency').textContent = Math.round(data.avg_latency_ms);
            document.getElementById('metric-active').textContent = data.active_requests;
        } catch (e) {
            console.error('Failed to fetch metrics', e);
        }
    }
    document.getElementById('refresh-metrics').addEventListener('click', fetchMetrics);
    
    // Auto-refresh stats occasionally if tabs are open
    setInterval(() => {
        if (!document.getElementById('workers-view').classList.contains('hidden')) fetchWorkers();
        if (!document.getElementById('metrics-view').classList.contains('hidden')) fetchMetrics();
    }, 2000);
});
