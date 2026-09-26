/**
 * STOCKSENSE - Smart Inventory Assistant Module (Rule-Based AI Engine)
 */

const assistant = {
  isOpen: false,

  toggle() {
    this.isOpen = !this.isOpen;
    const drawer = document.getElementById('chat-drawer');
    if (drawer) {
      drawer.classList.toggle('open', this.isOpen);
      if (this.isOpen) {
        document.getElementById('assistant-input').focus();
      }
    }
  },

  async sendQuery(queryText = null) {
    const input = document.getElementById('assistant-input');
    const text = queryText || (input ? input.value.trim() : '');
    if (!text) return;

    if (input) input.value = '';

    this.appendMessage(text, 'user');
    this.showTypingIndicator();

    try {
      const res = await api.post('/api/assistant/query', { query: text });
      this.removeTypingIndicator();
      this.appendMessage(res.answer, 'bot');
    } catch (e) {
      this.removeTypingIndicator();
      this.appendMessage('Sorry, I encountered an issue querying the inventory state. Please try again.', 'bot');
    }
  },

  appendMessage(text, sender = 'bot') {
    const container = document.getElementById('chat-messages');
    if (!container) return;

    const bubble = document.createElement('div');
    bubble.className = `chat-bubble chat-bubble-${sender}`;

    // Convert basic markdown like **bold**, *italic*, and `code`
    let formatted = text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');

    bubble.innerHTML = formatted;
    container.appendChild(bubble);
    container.scrollTop = container.scrollHeight;
  },

  showTypingIndicator() {
    const container = document.getElementById('chat-messages');
    if (!container) return;

    const indicator = document.createElement('div');
    indicator.id = 'typing-indicator';
    indicator.className = 'chat-bubble chat-bubble-bot';
    indicator.innerHTML = '<span style="opacity:0.7;">Thinking & checking database...</span>';
    container.appendChild(indicator);
    container.scrollTop = container.scrollHeight;
  },

  removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.remove();
  }
};
