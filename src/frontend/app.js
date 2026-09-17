/**
 * Groww Mutual Fund FAQ Assistant - Client Application Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  const fundsListEl = document.getElementById('funds-list');
  const historyListEl = document.getElementById('history-list');
  const messagesScrollEl = document.getElementById('messages-scroll');
  const chatFormEl = document.getElementById('chat-form');
  const queryInputEl = document.getElementById('query-input');
  const btnSendEl = document.getElementById('btn-send');
  const btnNewChatEl = document.getElementById('btn-new-chat');
  const quickPromptsContainer = document.getElementById('quick-prompts-container');

  let chatHistory = JSON.parse(localStorage.getItem('groww_rag_history') || '[]');
  let currentSession = [];

  function getApiBaseUrl() {
    if (window.MF_BACKEND_URL) return window.MF_BACKEND_URL.replace(/\/+$/, '');
    const saved = localStorage.getItem('mf_backend_url');
    if (saved) return saved.replace(/\/+$/, '');
    if (location.hostname === 'localhost' || location.hostname === '127.0.0.1') return '';
    return 'https://rag-chatbot-production-3ebb.up.railway.app';
  }

  // 1. Fetch Supported Funds from API
  async function loadSupportedFunds() {
    try {
      const resp = await fetch(`${getApiBaseUrl()}/api/funds`);
      const data = await resp.json();
      renderFunds(data.funds || []);
    } catch (err) {
      console.error('Failed to load supported funds:', err);
    }
  }

  function renderFunds(funds) {
    fundsListEl.innerHTML = '';
    funds.forEach(fund => {
      const item = document.createElement('div');
      item.className = 'fund-item';
      item.innerHTML = `
        <span class="fund-name">${fund.scheme_name}</span>
        <span class="fund-badge">${fund.category}</span>
      `;
      item.addEventListener('click', () => {
        document.querySelectorAll('.fund-item').forEach(el => el.classList.remove('active'));
        item.classList.add('active');
        queryInputEl.value = `What is the AUM and expense ratio for ${fund.scheme_name}?`;
        queryInputEl.focus();
      });
      fundsListEl.appendChild(item);
    });
  }

  // 2. Chat History Management
  function renderHistory() {
    historyListEl.innerHTML = '';
    if (chatHistory.length === 0) {
      historyListEl.innerHTML = '<div style="font-size: 12px; color: var(--color-text-dim); padding: 8px 12px;">No past conversations yet.</div>';
      return;
    }

    chatHistory.slice(0, 10).forEach((item, index) => {
      const historyItem = document.createElement('div');
      historyItem.className = `history-item ${index === 0 ? 'active' : ''}`;
      historyItem.innerHTML = `
        <svg class="history-icon" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
        <span class="history-title" title="${item.query}">${item.query}</span>
      `;
      historyItem.addEventListener('click', () => {
        document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
        historyItem.classList.add('active');
        loadSession(item);
      });
      historyListEl.appendChild(historyItem);
    });
  }

  function saveToHistory(query, answer) {
    chatHistory.unshift({ query, answer, timestamp: new Date().toISOString() });
    if (chatHistory.length > 25) chatHistory.pop();
    localStorage.setItem('groww_rag_history', JSON.stringify(chatHistory));
    renderHistory();
  }

  function loadSession(item) {
    messagesScrollEl.innerHTML = '';
    appendUserBubble(item.query);
    appendAssistantCard(item.answer);
  }

  // 3. Render Message Bubbles
  function appendUserBubble(text) {
    const row = document.createElement('div');
    row.className = 'message-row user';
    row.innerHTML = `<div class="user-bubble">${escapeHtml(text)}</div>`;
    messagesScrollEl.appendChild(row);
    scrollToBottom();
  }

  function appendTypingIndicator() {
    const row = document.createElement('div');
    row.className = 'message-row assistant';
    row.id = 'typing-indicator-row';
    row.innerHTML = `
      <div class="assistant-avatar" aria-hidden="true">
        <svg viewBox="0 0 24 24"><path d="M4 18h16c.6 0 1-.4 1-1V7c0-.6-.4-1-1-1H4c-.6 0-1 .4 1-1v10c0 .6.4 1 1 1zm8-9.5l4 4-1.4 1.4L12 11.3l-2.6 2.6L8 12.5l4-4z"/></svg>
      </div>
      <div class="assistant-card" style="padding: 12px 18px;">
        <div class="typing-indicator">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    `;
    messagesScrollEl.appendChild(row);
    scrollToBottom();
    return row;
  }

  function removeTypingIndicator() {
    const el = document.getElementById('typing-indicator-row');
    if (el) el.remove();
  }

  function appendAssistantCard(answerData) {
    const row = document.createElement('div');
    row.className = 'message-row assistant';

    let bodyText = answerData.answer_text || '';
    let citationUrl = answerData.citation_url || '';
    let footerText = answerData.footer_text || '';

    // Replace markdown link or 'directly on the [link].' with 'directly using the below link.'
    let cleanBody = bodyText
      .replace(/:\s*\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, '.')
      .replace(/directly on the\s*\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/gi, 'directly using the below link')
      .replace(/directly on the\s*\./gi, 'directly using the below link.')
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g, '')
      .replace(/\s+\./g, '.')
      .trim();

    // Strip mandatory footer prefix if already in body
    cleanBody = cleanBody.replace(/Last updated from sources:.*$/m, '').trim();

    // Bold monetary / percentage / ratio metrics for visual clarity
    cleanBody = cleanBody.replace(/(₹[\d,]+(?:\.\d+)?\s*(?:Cr|Lakh)?)/g, '<strong>$1</strong>');
    cleanBody = cleanBody.replace(/(\b\d+(?:\.\d+)?%)/g, '<strong>$1</strong>');

    let citationBadgeHtml = '';
    const isMissingInfo = cleanBody.includes("I do not have this factual information");
    if (citationUrl && citationUrl.trim() !== '' && !isMissingInfo) {
      citationBadgeHtml = `
        <a href="${citationUrl}" target="_blank" rel="noopener noreferrer" class="citation-badge">
          <svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
          Official Scheme Page on Groww
        </a>
      `;
    }

    row.innerHTML = `
      <div class="assistant-avatar" aria-hidden="true">
        <svg viewBox="0 0 24 24"><path d="M4 18h16c.6 0 1-.4 1-1V7c0-.6-.4-1-1-1H4c-.6 0-1 .4 1-1v10c0 .6.4 1 1 1zm8-9.5l4 4-1.4 1.4L12 11.3l-2.6 2.6L8 12.5l4-4z"/></svg>
      </div>
      <div class="assistant-card">
        <p>${cleanBody}</p>
        ${citationBadgeHtml}
        ${footerText ? `<div class="assistant-footer">
          <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>
          <span>${footerText}</span>
        </div>` : ''}
      </div>
    `;

    messagesScrollEl.appendChild(row);
    scrollToBottom();
  }

  function appendInitialGreeting() {
    messagesScrollEl.innerHTML = '';
    appendAssistantCard({
      answer_text: "Welcome to the Groww Mutual Fund FAQ Assistant. I provide strictly factual data for 5 select HDFC mutual fund schemes directly from Groww documentation. How can I help you today?",
      citation_url: "",
      footer_text: "Last updated from sources: 16-Sep-2026"
    });
  }

  function scrollToBottom() {
    messagesScrollEl.scrollTop = messagesScrollEl.scrollHeight;
  }

  function escapeHtml(str) {
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // 4. Send Message Handler
  async function submitQuery(queryText) {
    const text = queryText.trim();
    if (!text) return;

    queryInputEl.value = '';
    queryInputEl.disabled = true;
    btnSendEl.disabled = true;

    appendUserBubble(text);
    appendTypingIndicator();

    try {
      const resp = await fetch(`${getApiBaseUrl()}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text }),
      });

      const data = await resp.json();
      removeTypingIndicator();

      appendAssistantCard(data);
      saveToHistory(text, data);

    } catch (err) {
      removeTypingIndicator();
      appendAssistantCard({
        answer_text: "A connection error occurred while querying the factual assistant. Please try again.",
        citation_url: "https://groww.in/mutual-funds/hdfc-mid-cap-fund-direct-growth",
        footer_text: "Last updated from sources: 16-Sep-2026"
      });
    } finally {
      queryInputEl.disabled = false;
      btnSendEl.disabled = false;
      queryInputEl.focus();
    }
  }

  // Form event listeners
  chatFormEl.addEventListener('submit', (e) => {
    e.preventDefault();
    submitQuery(queryInputEl.value);
  });

  // Quick Prompt Chips
  quickPromptsContainer.addEventListener('click', (e) => {
    const chip = e.target.closest('.prompt-chip');
    if (chip) {
      const query = chip.getAttribute('data-query');
      if (query) submitQuery(query);
    }
  });

  // New Chat Button
  btnNewChatEl.addEventListener('click', () => {
    appendInitialGreeting();
    queryInputEl.focus();
  });

  // Initial Initialization
  loadSupportedFunds();
  renderHistory();
  appendInitialGreeting();
});
