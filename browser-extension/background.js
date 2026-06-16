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
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'pkos-save-selection') {
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
            title: tab.title
          },
        });
        // Open popup programmatically (Chrome 99+)
        chrome.action.openPopup().catch(() => {});
      }
    });
  }
});

// Message relay mapping: popup message type -> content script message type
const MESSAGE_RELAY = {
  'GET_PAGE_INFO': 'GET_PAGE_INFO',
  'GET_SELECTION_FROM_PAGE': 'GET_SELECTION',
  'GET_FULLPAGE_CONTENT': 'GET_FULLPAGE'
};

// Generic relay to content script
function relayToContentScript(type, sendResponse) {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]) {
      chrome.tabs.sendMessage(tabs[0].id, { type }, sendResponse);
    } else {
      sendResponse({ error: 'No active tab' });
    }
  });
}

// Relay messages between content script and popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const targetType = MESSAGE_RELAY[message.type];
  if (targetType) {
    relayToContentScript(targetType, sendResponse);
    return true;
  }
});
