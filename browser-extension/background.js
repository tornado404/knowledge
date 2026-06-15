// background.js - PKOS Clip Service Worker

// Initialize default settings on install
chrome.runtime.onInstalled.addListener(async () => {
  const defaults = {
    apiEndpoint: 'http://localhost:8000',
    defaultIdentities: [],
    autoExtract: true,
    aiTags: true,
    saveImages: false,
    identities: ['程序员', '好爸爸', '学生', '研究者', '创作者'],
  };

  const existing = await chrome.storage.local.get(Object.keys(defaults));
  const toSet = {};
  for (const [key, value] of Object.entries(defaults)) {
    if (existing[key] === undefined) {
      toSet[key] = value;
    }
  }
  if (Object.keys(toSet).length > 0) {
    await chrome.storage.local.set(toSet);
  }

  // Create context menu
  chrome.contextMenus.create({
    id: 'pkos-save-selection',
    title: '保存到 PKOS',
    contexts: ['selection'],
  });

  console.log('[PKOS Clip] Service worker initialized');
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'pkos-save-selection') {
    // Send message to content script to get selection with context
    chrome.tabs.sendMessage(tab.id, { type: 'GET_SELECTION' }, (response) => {
      if (chrome.runtime.lastError) {
        console.error('[PKOS Clip] Failed to get selection:', chrome.runtime.lastError);
        return;
      }
      if (response && response.selection) {
        // Store selection for popup to retrieve
        chrome.storage.local.set({
          pendingSelection: {
            text: response.selection,
            html: response.html || '',
            url: tab.url,
            title: tab.title,
            timestamp: Date.now(),
          },
        });
        // Open popup programmatically (Chrome 99+)
        chrome.action.openPopup().catch(() => {
          // Fallback: show notification that user should open popup
          console.log('[PKOS Clip] Please click the extension icon to save selection');
        });
      }
    });
  }
});

// Relay messages between content script and popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'GET_PAGE_INFO') {
    // Forward to active tab's content script
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, { type: 'GET_PAGE_INFO' }, sendResponse);
      } else {
        sendResponse({ error: 'No active tab' });
      }
    });
    return true; // Keep channel open for async response
  }

  if (message.type === 'GET_SELECTION_FROM_PAGE') {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, { type: 'GET_SELECTION' }, sendResponse);
      } else {
        sendResponse({ error: 'No active tab' });
      }
    });
    return true;
  }

  if (message.type === 'GET_FULLPAGE_CONTENT') {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, { type: 'GET_FULLPAGE' }, sendResponse);
      } else {
        sendResponse({ error: 'No active tab' });
      }
    });
    return true;
  }
});
