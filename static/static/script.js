const chatContainer = document.getElementById("chat-container");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");

sendBtn.onclick = sendMessage;
userInput.onkeydown = (e) => { if (e.key === "Enter") sendMessage(); };

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    addMessage(text, 'user');
    userInput.value = "";
    
    // Yükleniyor mesajı
    const loading = addMessage("Analiz yapılıyor...", 'bot', true);

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });
        
        const data = await response.json();
        chatContainer.removeChild(loading); // Yükleniyor yazısını sil
        
        if (data.reply) {
            addMessage(data.reply, 'bot');
        } else {
            addMessage("Hata oluştu.", 'bot');
        }
    } catch (error) {
        chatContainer.removeChild(loading);
        addMessage("Sunucu hatası.", 'bot');
    }
}

function addMessage(text, sender, isItalic=false) {
    const div = document.createElement("div");
    div.className = sender === 'user' ? "user-message" : "bot-message";
    const box = document.createElement("div");
    box.className = "message-box";
    box.innerText = text;
    if(isItalic) box.style.fontStyle = "italic";
    div.appendChild(box);
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return div;
}