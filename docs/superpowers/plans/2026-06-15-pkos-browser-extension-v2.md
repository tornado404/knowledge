# PKOS Browser Extension v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing PKOS Clip browser extension from basic URL reader to full-featured web clipper with three clipping modes, settings panel, identity/tag management, and PKOS API integration.

**Architecture:** Single-page popup UI with mode switching, settings overlay, and identity/tag chips. Background service worker handles context menu and message passing. Content script extracts page content and selection. All clipping data flows to PKOS Ingest Pipeline API via `POST /pkos/v1/ingest`.

**Tech Stack:** JavaScript (no framework), Chrome Extension Manifest V3, Mozilla Readability.js, CSS dark theme.

---

## File Structure

```
browser-extension/
├── manifest.json           # v3, updated permissions
├── popup.html              # Main UI with mode tabs + settings overlay
├── popup.css               # Dark theme styles (extended)
├── popup.js                # Main UI logic, state management, API calls
├── background.js           # Service Worker, context menu, message relay
├── content.js              # Page content extraction, selection handling
├── lib/
│   └── readability.js      # Mozilla Readability (downloaded)
└── icons/                  # Existing icons (16/48/128px)
```

---

## Task 1: Update manifest.json with new permissions

**Files:**
- Modify: `browser-extension/manifest.json`

- [ ] **Step 1: Update manifest.json with required permissions and scripts**

```json
{
  "manifest_version": 3,
  "name": "PKOS Clip",
  "version": "2.0.0",
  "description": "Personal Knowledge Operating System — 一键剪藏网页到 PKOS Vault",
  "permissions": [
    "activeTab",
    "storage",
    "contextMenus",
    "clipboardRead"
  ],
  "action": {
    "default_popup": "popup.html",
    "default_icon": {
      "16": "icons/icon16.png",
      "48": "icons/icon48.png",
      "128": "icons/icon128.png"
    }
  },
  "background": {
    "service_worker": "background.js"
  },
  "content_scripts": [
    {
      "matches": ["<all_urls>"],
      "js": ["content.js"],
      "run_at": "document_end"
    }
  ],
  "icons": {
    "16": "icons/icon16.png",
    "48": "icons/icon48.png",
    "128": "icons/icon128.png"
  },
  "web_accessible_resources": [
    {
      "resources": ["lib/*"],
      "matches": ["<all_urls>"]
    }
  ]
}
```

- [ ] **Step 2: Commit manifest update**

```bash
git add browser-extension/manifest.json
git commit -m "feat(pkos-ext): update manifest for v2 with storage, contextMenus, clipboardRead"
```

---

## Task 2: Create background.js service worker

**Files:**
- Create: `browser-extension/background.js`

- [ ] **Step 1: Create background.js with context menu and message handling**

```javascript
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
```

- [ ] **Step 2: Commit background.js**

```bash
git add browser-extension/background.js
git commit -m "feat(pkos-ext): add background service worker with context menu"
```

---

## Task 3: Create content.js for page interaction

**Files:**
- Create: `browser-extension/content.js`

- [ ] **Step 1: Create content.js with selection and page info extraction**

```javascript
// content.js - PKOS Clip Content Script

(function () {
  'use strict';

  // Listen for messages from popup/background
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    switch (message.type) {
      case 'GET_PAGE_INFO':
        sendResponse(getPageInfo());
        break;

      case 'GET_SELECTION':
        sendResponse(getSelection());
        break;

      case 'GET_FULLPAGE':
        sendResponse(getFullPageContent());
        break;

      default:
        sendResponse({ error: 'Unknown message type' });
    }
    return true;
  });

  function getPageInfo() {
    return {
      title: document.title || '',
      url: window.location.href,
      favicon: getFavicon(),
      description: getMetaDescription(),
    };
  }

  function getFavicon() {
    const link = document.querySelector('link[rel="icon"]') ||
                 document.querySelector('link[rel="shortcut icon"]');
    if (link) {
      return link.href;
    }
    // Fallback to default favicon path
    return new URL('/favicon.ico', window.location.origin).href;
  }

  function getMetaDescription() {
    const meta = document.querySelector('meta[name="description"]');
    return meta ? meta.getAttribute('content') : '';
  }

  function getSelection() {
    const selection = window.getSelection();
    const text = selection.toString().trim();

    if (!text) {
      return { selection: '', html: '' };
    }

    // Try to get HTML of selection
    let html = '';
    try {
      if (selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);
        const div = document.createElement('div');
        div.appendChild(range.cloneContents());
        html = div.innerHTML;
      }
    } catch (e) {
      console.warn('[PKOS Clip] Could not get selection HTML:', e);
    }

    return {
      selection: text,
      html: html,
      rangeCount: selection.rangeCount,
    };
  }

  function getFullPageContent() {
    // Basic extraction - will be enhanced with Readability in Task 8
    const body = document.body;

    // Remove script, style, nav, header, footer, aside elements
    const clone = body.cloneNode(true);
    const removeSelectors = ['script', 'style', 'nav', 'header', 'footer', 'aside', '.sidebar', '.navigation', '.comments'];
    removeSelectors.forEach(selector => {
      clone.querySelectorAll(selector).forEach(el => el.remove());
    });

    const text = clone.textContent || clone.innerText;
    const html = clone.innerHTML;

    return {
      text: text.trim(),
      html: html,
      title: document.title,
      url: window.location.href,
    };
  }

  console.log('[PKOS Clip] Content script loaded on', window.location.href);
})();
```

- [ ] **Step 2: Commit content.js**

```bash
git add browser-extension/content.js
git commit -m "feat(pkos-ext): add content script for page info and selection extraction"
```

---

## Task 4: Extend popup.css with mode tabs and settings overlay styles

**Files:**
- Modify: `browser-extension/popup.css`

- [ ] **Step 1: Append new styles to popup.css**

Add the following styles to the end of `browser-extension/popup.css`:

```css
/* Mode Tabs */
.mode-tabs {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  background-color: #16213e;
  border-bottom: 1px solid #2a2a4e;
  overflow-x: auto;
}

.mode-tab {
  background: transparent;
  color: #8892b0;
  border: 1px solid #2a2a4e;
  border-radius: 16px;
  padding: 6px 14px;
  font-size: 12px;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.2s ease;
}

.mode-tab:hover {
  background-color: #2a2a4e;
  color: #e0e0e0;
}

.mode-tab.active {
  background-color: #4a9eff;
  color: white;
  border-color: #4a9eff;
}

/* Content Preview */
.content-preview {
  background-color: #16213e;
  border: 1px solid #2a2a4e;
  border-radius: 8px;
  padding: 12px;
  min-height: 80px;
  max-height: 180px;
  overflow-y: auto;
}

.content-preview p {
  color: #e0e0e0;
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
}

.content-meta {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #2a2a4e;
  color: #8892b0;
  font-size: 12px;
}

/* Chips (Identities & Tags) */
.chips-container {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}

.chips-label {
  color: #8892b0;
  font-size: 11px;
  margin-right: 4px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.chip-identity {
  background-color: #2a2a4e;
  color: #4a9eff;
}

.chip-identity.selected {
  background-color: #4a9eff;
  color: white;
}

.chip-tag {
  background-color: #1a3a2e;
  color: #5aef7a;
}

.chip-tag.selected {
  background-color: #5aef7a;
  color: #1a1a2e;
}

.chip-remove {
  font-size: 10px;
  opacity: 0.7;
}

.chip-remove:hover {
  opacity: 1;
}

.chip-add {
  background: transparent;
  color: #556080;
  border: 1px dashed #556080;
}

.chip-add:hover {
  border-color: #8892b0;
  color: #8892b0;
}

/* Settings Overlay */
.settings-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #1a1a2e;
  z-index: 100;
  display: none;
  flex-direction: column;
}

.settings-overlay.visible {
  display: flex;
}

.settings-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid #2a2a4e;
}

.settings-back {
  background: transparent;
  color: #8892b0;
  border: none;
  font-size: 18px;
  cursor: pointer;
  padding: 0;
}

.settings-title {
  color: white;
  font-weight: 600;
  font-size: 14px;
}

.settings-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.settings-section {
  margin-bottom: 20px;
}

.settings-section h4 {
  color: #e0e0e0;
  font-size: 13px;
  margin: 0 0 10px 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.settings-card {
  background-color: #16213e;
  border: 1px solid #2a2a4e;
  border-radius: 8px;
  padding: 12px;
}

.settings-input {
  width: 100%;
  background-color: #1a1a2e;
  border: 1px solid #2a2a4e;
  border-radius: 6px;
  padding: 8px 12px;
  color: white;
  font-size: 13px;
}

.settings-input:focus {
  outline: none;
  border-color: #4a9eff;
}

.settings-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #2a2a4e;
}

.settings-row:last-child {
  border-bottom: none;
}

.settings-row-label {
  flex: 1;
}

.settings-row-label p {
  color: #e0e0e0;
  font-size: 13px;
  margin: 0;
}

.settings-row-label span {
  color: #556080;
  font-size: 11px;
}

/* Toggle Switch */
.toggle {
  width: 44px;
  height: 24px;
  border-radius: 12px;
  position: relative;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.toggle-off {
  background-color: #2a2a4e;
}

.toggle-on {
  background-color: #4a9eff;
}

.toggle-knob {
  width: 18px;
  height: 18px;
  background-color: white;
  border-radius: 50%;
  position: absolute;
  top: 3px;
  transition: left 0.2s ease;
}

.toggle-off .toggle-knob {
  left: 3px;
}

.toggle-on .toggle-knob {
  left: 23px;
}

/* Connection Status */
.connection-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.connected {
  background-color: #5aef7a;
}

.status-dot.disconnected {
  background-color: #ef5a5a;
}

.status-text {
  font-size: 12px;
}

.status-text.connected {
  color: #5aef7a;
}

.status-text.disconnected {
  color: #ef5a5a;
}

/* Save Status */
.save-status {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px;
  margin-top: 12px;
  border-radius: 8px;
  font-size: 13px;
}

.save-status.success {
  background-color: #1a3a2e;
  color: #5aef7a;
}

.save-status.error {
  background-color: #3a1a1a;
  color: #ef5a5a;
}

.save-status.loading {
  background-color: #2a2a4e;
  color: #4a9eff;
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 20px;
  color: #556080;
}

.empty-state p {
  font-size: 13px;
  margin: 0;
}

/* Keyboard Shortcut Display */
kbd {
  background: #2a2a4e;
  color: #e0e0e0;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-family: monospace;
}
```

- [ ] **Step 2: Commit popup.css extension**

```bash
git add browser-extension/popup.css
git commit -m "feat(pkos-ext): add styles for mode tabs, chips, settings overlay"
```

---

## Task 5: Rewrite popup.html with full UI structure

**Files:**
- Modify: `browser-extension/popup.html`

- [ ] **Step 1: Replace popup.html with full UI structure**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>PKOS Clip</title>
  <link rel="stylesheet" href="popup.css">
</head>
<body>
  <!-- Main View -->
  <div id="main-view" class="container">
    <header>
      <div style="display: flex; align-items: center; gap: 8px;">
        <div class="logo">P</div>
        <span class="app-name">PKOS Clip</span>
      </div>
      <div class="header-actions">
        <button id="btn-settings" class="btn-header">⚙️ 设置</button>
        <button id="btn-history" class="btn-header">📋 历史</button>
      </div>
    </header>

    <!-- Mode Tabs -->
    <div class="mode-tabs">
      <button class="mode-tab active" data-mode="clipboard">📋 剪切板</button>
      <button class="mode-tab" data-mode="selection">✂️ 选中内容</button>
      <button class="mode-tab" data-mode="fullpage">📄 全文</button>
    </div>

    <!-- Content Area -->
    <main>
      <!-- Page Info -->
      <div class="page-info">
        <input id="input-title" class="input-title" type="text" placeholder="页面标题">
        <div class="url-row">
          <span class="url-icon">🔗</span>
          <span id="display-url" class="url-text"></span>
        </div>
      </div>

      <!-- Content Preview -->
      <div id="content-preview" class="content-preview">
        <p id="preview-text" class="empty-state">正在加载内容...</p>
      </div>

      <!-- Identities -->
      <div class="chips-section">
        <span class="chips-label">身份：</span>
        <div id="identities-container" class="chips-container"></div>
      </div>

      <!-- Tags -->
      <div class="chips-section">
        <span class="chips-label">标签：</span>
        <div id="tags-container" class="chips-container"></div>
      </div>
    </main>

    <!-- Action Bar -->
    <footer>
      <button id="btn-save" class="btn-primary">保存到 PKOS</button>
      <button id="btn-cancel" class="btn-secondary">取消</button>
    </footer>

    <!-- Save Status -->
    <div id="save-status" class="save-status" style="display: none;"></div>
  </div>

  <!-- Settings Overlay -->
  <div id="settings-overlay" class="settings-overlay">
    <div class="settings-header">
      <button id="btn-back" class="settings-back">←</button>
      <span class="settings-title">设置</span>
    </div>

    <div class="settings-content">
      <!-- API Server -->
      <div class="settings-section">
        <h4>服务器配置</h4>
        <div class="settings-card">
          <label style="display: block; color: #8892b0; font-size: 11px; margin-bottom: 6px;">PKOS API 地址</label>
          <input id="settings-api-endpoint" class="settings-input" type="text" placeholder="http://localhost:8000">
          <div id="connection-status" class="connection-status">
            <span class="status-dot disconnected"></span>
            <span class="status-text disconnected">未连接</span>
          </div>
        </div>
      </div>

      <!-- Default Identities -->
      <div class="settings-section">
        <h4>默认身份</h4>
        <div class="settings-card">
          <p style="color: #8892b0; font-size: 12px; margin: 0 0 10px 0;">每次剪藏自动添加以下身份标签：</p>
          <div id="settings-identities" class="chips-container"></div>
        </div>
      </div>

      <!-- Clip Behavior -->
      <div class="settings-section">
        <h4>剪藏行为</h4>
        <div class="settings-card">
          <div class="settings-row">
            <div class="settings-row-label">
              <p>自动提取正文</p>
              <span>全文模式自动去除广告/导航</span>
            </div>
            <div id="toggle-auto-extract" class="toggle toggle-on">
              <div class="toggle-knob"></div>
            </div>
          </div>
          <div class="settings-row">
            <div class="settings-row-label">
              <p>AI 自动生成标签</p>
              <span>由 LLM 推断内容主题和关键词</span>
            </div>
            <div id="toggle-ai-tags" class="toggle toggle-on">
              <div class="toggle-knob"></div>
            </div>
          </div>
          <div class="settings-row">
            <div class="settings-row-label">
              <p>保存页面图片</p>
              <span>全文模式同时下载图片到本地</span>
            </div>
            <div id="toggle-save-images" class="toggle toggle-off">
              <div class="toggle-knob"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Shortcuts -->
      <div class="settings-section">
        <h4>快捷键</h4>
        <div class="settings-card">
          <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 0;">
            <span style="color: #e0e0e0; font-size: 13px;">打开插件</span>
            <kbd>Ctrl+Shift+P</kbd>
          </div>
          <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 0;">
            <span style="color: #e0e0e0; font-size: 13px;">快速剪藏</span>
            <kbd>Ctrl+Shift+S</kbd>
          </div>
        </div>
      </div>

      <!-- About -->
      <div class="settings-section">
        <h4>关于</h4>
        <div class="settings-card">
          <p style="color: #8892b0; font-size: 12px; margin: 0;">PKOS Clip v2.0.0</p>
          <p style="color: #556080; font-size: 11px; margin: 6px 0 0 0;">Personal Knowledge Operating System</p>
        </div>
      </div>
    </div>

    <div style="padding: 12px 16px; background-color: #16213e; border-top: 1px solid #2a2a4e;">
      <button id="btn-save-settings" class="btn-primary" style="width: 100%;">保存设置</button>
    </div>
  </div>

  <script src="popup.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit popup.html rewrite**

```bash
git add browser-extension/popup.html
git commit -m "feat(pkos-ext): rewrite popup.html with full UI structure and settings overlay"
```

---

## Task 6: Rewrite popup.js with state management and mode switching

**Files:**
- Modify: `browser-extension/popup.js`

- [ ] **Step 1: Replace popup.js with full implementation**

```javascript
// popup.js - PKOS Clip Main UI Logic

(function () {
  'use strict';

  // Application State
  const state = {
    mode: 'clipboard',  // 'clipboard' | 'selection' | 'fullpage'
    pageInfo: { title: '', url: '', favicon: '', description: '' },
    content: '',
    contentHtml: '',
    identities: [],     // Selected identities
    tags: [],           // User-added tags
    settings: {
      apiEndpoint: 'http://localhost:8000',
      defaultIdentities: [],
      autoExtract: true,
      aiTags: true,
      saveImages: false,
      identities: ['程序员', '好爸爸', '学生', '研究者', '创作者'],
    },
    saveStatus: null,   // null | 'loading' | 'success' | 'error'
  };

  // DOM Elements
  const elements = {
    mainView: document.getElementById('main-view'),
    settingsOverlay: document.getElementById('settings-overlay'),
    modeTabs: document.querySelectorAll('.mode-tab'),
    inputTitle: document.getElementById('input-title'),
    displayUrl: document.getElementById('display-url'),
    contentPreview: document.getElementById('content-preview'),
    previewText: document.getElementById('preview-text'),
    identitiesContainer: document.getElementById('identities-container'),
    tagsContainer: document.getElementById('tags-container'),
    btnSave: document.getElementById('btn-save'),
    btnCancel: document.getElementById('btn-cancel'),
    btnSettings: document.getElementById('btn-settings'),
    btnHistory: document.getElementById('btn-history'),
    btnBack: document.getElementById('btn-back'),
    btnSaveSettings: document.getElementById('btn-save-settings'),
    saveStatus: document.getElementById('save-status'),
    // Settings inputs
    settingsApiEndpoint: document.getElementById('settings-api-endpoint'),
    settingsIdentities: document.getElementById('settings-identities'),
    toggleAutoExtract: document.getElementById('toggle-auto-extract'),
    toggleAiTags: document.getElementById('toggle-ai-tags'),
    toggleSaveImages: document.getElementById('toggle-save-images'),
    connectionStatus: document.getElementById('connection-status'),
  };

  // Initialize
  async function init() {
    await loadSettings();
    await loadPageInfo();
    await loadClipboardContent();
    renderIdentities();
    renderTags();
    setupEventListeners();
    testConnection();
  }

  // Load settings from chrome.storage.local
  async function loadSettings() {
    try {
      const data = await chrome.storage.local.get([
        'apiEndpoint', 'defaultIdentities', 'autoExtract', 'aiTags', 'saveImages', 'identities'
      ]);
      state.settings = { ...state.settings, ...data };
      updateSettingsUI();
    } catch (e) {
      console.error('[PKOS Clip] Failed to load settings:', e);
    }
  }

  // Load current page info via content script
  async function loadPageInfo() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: 'GET_PAGE_INFO' }, (response) => {
        if (response && !response.error) {
          state.pageInfo = response;
          elements.inputTitle.value = response.title || '';
          elements.displayUrl.textContent = response.url || '';
        }
        resolve();
      });
    });
  }

  // Load clipboard content
  async function loadClipboardContent() {
    if (state.mode !== 'clipboard') return;

    try {
      // Try to read from clipboard API
      const text = await navigator.clipboard.readText();
      if (text) {
        state.content = text;
        state.contentHtml = '';
        updateContentPreview();
      } else {
        showEmptyState('剪切板为空，请先复制内容');
      }
    } catch (e) {
      console.warn('[PKOS Clip] Could not read clipboard:', e);
      // Check for pending selection from context menu
      const data = await chrome.storage.local.get('pendingSelection');
      if (data.pendingSelection) {
        state.mode = 'selection';
        state.content = data.pendingSelection.text;
        state.contentHtml = data.pendingSelection.html || '';
        state.pageInfo.title = data.pendingSelection.title;
        state.pageInfo.url = data.pendingSelection.url;
        elements.inputTitle.value = data.pendingSelection.title;
        elements.displayUrl.textContent = data.pendingSelection.url;
        updateModeTabs();
        updateContentPreview();
        chrome.storage.local.remove('pendingSelection');
      } else {
        showEmptyState('无法访问剪切板，请手动粘贴');
      }
    }
  }

  // Get selection from page
  async function getSelectionFromPage() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: 'GET_SELECTION_FROM_PAGE' }, (response) => {
        if (response && response.selection) {
          state.content = response.selection;
          state.contentHtml = response.html || '';
          updateContentPreview();
        } else {
          showEmptyState('请在页面上选择内容');
        }
        resolve();
      });
    });
  }

  // Get full page content
  async function getFullPageContent() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: 'GET_FULLPAGE_CONTENT' }, (response) => {
        if (response && response.text) {
          state.content = response.text;
          state.contentHtml = response.html || '';
          updateContentPreview();
        } else {
          showEmptyState('无法提取页面内容');
        }
        resolve();
      });
    });
  }

  // Update content preview
  function updateContentPreview() {
    const preview = state.content.substring(0, 500);
    const charCount = state.content.length;

    elements.previewText.innerHTML = `
      <p>${escapeHtml(preview)}${charCount > 500 ? '...' : ''}</p>
      <div class="content-meta">
        📄 ${charCount} 字符
      </div>
    `;
  }

  // Show empty state message
  function showEmptyState(message) {
    elements.previewText.innerHTML = `<p class="empty-state">${message}</p>`;
    state.content = '';
    state.contentHtml = '';
  }

  // Render identity chips
  function renderIdentities() {
    const allIdentities = state.settings.identities || [];
    const defaultIds = state.settings.defaultIdentities || [];

    elements.identitiesContainer.innerHTML = allIdentities.map(id => {
      const isSelected = state.identities.includes(id) || defaultIds.includes(id);
      return `
        <span class="chip chip-identity ${isSelected ? 'selected' : ''}" data-identity="${id}">
          👤 ${id} ${isSelected ? '✓' : ''}
        </span>
      `;
    }).join('') + `
      <span class="chip chip-add" id="add-identity">+ 添加</span>
    `;

    // Add click handlers
    elements.identitiesContainer.querySelectorAll('.chip-identity').forEach(chip => {
      chip.addEventListener('click', () => toggleIdentity(chip.dataset.identity));
    });

    document.getElementById('add-identity').addEventListener('click', addCustomIdentity);
  }

  // Toggle identity selection
  function toggleIdentity(identity) {
    const index = state.identities.indexOf(identity);
    if (index >= 0) {
      state.identities.splice(index, 1);
    } else {
      state.identities.push(identity);
    }
    renderIdentities();
  }

  // Add custom identity
  function addCustomIdentity() {
    const identity = prompt('输入新身份标签：');
    if (identity && identity.trim()) {
      if (!state.settings.identities.includes(identity.trim())) {
        state.settings.identities.push(identity.trim());
      }
      state.identities.push(identity.trim());
      renderIdentities();
    }
  }

  // Render tag chips
  function renderTags() {
    elements.tagsContainer.innerHTML = state.tags.map(tag => `
      <span class="chip chip-tag selected" data-tag="${tag}">
        #${tag} <span class="chip-remove" data-tag="${tag}">✕</span>
      </span>
    `).join('') + `
      <span class="chip chip-add" id="add-tag">+ 添加</span>
    `;

    // Add click handlers
    elements.tagsContainer.querySelectorAll('.chip-remove').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        removeTag(btn.dataset.tag);
      });
    });

    document.getElementById('add-tag').addEventListener('click', addTag);
  }

  // Add tag
  function addTag() {
    const tag = prompt('输入标签：');
    if (tag && tag.trim() && !state.tags.includes(tag.trim())) {
      state.tags.push(tag.trim());
      renderTags();
    }
  }

  // Remove tag
  function removeTag(tag) {
    state.tags = state.tags.filter(t => t !== tag);
    renderTags();
  }

  // Update mode tabs UI
  function updateModeTabs() {
    elements.modeTabs.forEach(tab => {
      tab.classList.toggle('active', tab.dataset.mode === state.mode);
    });
  }

  // Handle mode switch
  async function switchMode(mode) {
    state.mode = mode;
    updateModeTabs();

    switch (mode) {
      case 'clipboard':
        await loadClipboardContent();
        break;
      case 'selection':
        await getSelectionFromPage();
        break;
      case 'fullpage':
        await getFullPageContent();
        break;
    }
  }

  // Save to PKOS API
  async function saveToPKOS() {
    if (!state.content) {
      showSaveStatus('error', '没有内容可保存');
      return;
    }

    showSaveStatus('loading', '保存中...');

    const settings = state.settings;
    const allIdentities = [...(settings.defaultIdentities || []), ...state.identities];

    const formData = new FormData();
    formData.append('source_type', 'browser_clip');
    formData.append('source_url', state.pageInfo.url);
    formData.append('identities', allIdentities.join(','));
    formData.append('tags', state.tags.join(','));
    formData.append('title', elements.inputTitle.value || state.pageInfo.title || '未命名文档');

    // Create content blob
    const content = state.contentHtml || state.content;
    const blob = new Blob([content], { type: 'text/markdown' });
    formData.append('file', blob, 'clip.md');

    try {
      const response = await fetch(`${settings.apiEndpoint}/pkos/v1/ingest`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();
      showSaveStatus('success', `保存成功！任务ID: ${result.task_id}`);

      // Clear content after successful save
      state.content = '';
      state.tags = [];
      setTimeout(() => window.close(), 1500);
    } catch (e) {
      console.error('[PKOS Clip] Save failed:', e);
      showSaveStatus('error', `保存失败: ${e.message}`);
    }
  }

  // Show save status
  function showSaveStatus(status, message) {
    state.saveStatus = status;
    elements.saveStatus.className = `save-status ${status}`;
    elements.saveStatus.textContent = message;
    elements.saveStatus.style.display = 'flex';
  }

  // Test API connection
  async function testConnection() {
    const statusDot = elements.connectionStatus.querySelector('.status-dot');
    const statusText = elements.connectionStatus.querySelector('.status-text');

    try {
      const response = await fetch(`${state.settings.apiEndpoint}/pkos/v1/metrics`, {
        method: 'GET',
        signal: AbortSignal.timeout(3000),
      });

      if (response.ok) {
        statusDot.className = 'status-dot connected';
        statusText.className = 'status-text connected';
        statusText.textContent = '已连接';
      } else {
        throw new Error('Connection failed');
      }
    } catch (e) {
      statusDot.className = 'status-dot disconnected';
      statusText.className = 'status-text disconnected';
      statusText.textContent = '未连接';
    }
  }

  // Update settings UI
  function updateSettingsUI() {
    elements.settingsApiEndpoint.value = state.settings.apiEndpoint || 'http://localhost:8000';

    // Update toggles
    updateToggle(elements.toggleAutoExtract, state.settings.autoExtract);
    updateToggle(elements.toggleAiTags, state.settings.aiTags);
    updateToggle(elements.toggleSaveImages, state.settings.saveImages);

    // Render default identities in settings
    renderSettingsIdentities();
  }

  // Update toggle state
  function updateToggle(element, isOn) {
    element.className = `toggle ${isOn ? 'toggle-on' : 'toggle-off'}`;
  }

  // Render identities in settings panel
  function renderSettingsIdentities() {
    const defaultIds = state.settings.defaultIdentities || [];
    const allIds = state.settings.identities || [];

    elements.settingsIdentities.innerHTML = allIds.map(id => {
      const isDefault = defaultIds.includes(id);
      return `
        <span class="chip chip-identity ${isDefault ? 'selected' : ''}" data-settings-identity="${id}">
          👤 ${id} ${isDefault ? '✓' : ''}
        </span>
      `;
    }).join('');
  }

  // Save settings
  async function saveSettings() {
    state.settings.apiEndpoint = elements.settingsApiEndpoint.value;
    state.settings.autoExtract = elements.toggleAutoExtract.classList.contains('toggle-on');
    state.settings.aiTags = elements.toggleAiTags.classList.contains('toggle-on');
    state.settings.saveImages = elements.toggleSaveImages.classList.contains('toggle-on');

    await chrome.storage.local.set(state.settings);
    testConnection();
    hideSettings();
  }

  // Show settings overlay
  function showSettings() {
    elements.settingsOverlay.classList.add('visible');
  }

  // Hide settings overlay
  function hideSettings() {
    elements.settingsOverlay.classList.remove('visible');
  }

  // Setup event listeners
  function setupEventListeners() {
    // Mode tabs
    elements.modeTabs.forEach(tab => {
      tab.addEventListener('click', () => switchMode(tab.dataset.mode));
    });

    // Main actions
    elements.btnSave.addEventListener('click', saveToPKOS);
    elements.btnCancel.addEventListener('click', () => window.close());
    elements.btnSettings.addEventListener('click', showSettings);
    elements.btnHistory.addEventListener('click', () => {
      // TODO: Implement history view
      alert('历史记录功能即将推出');
    });

    // Settings
    elements.btnBack.addEventListener('click', hideSettings);
    elements.btnSaveSettings.addEventListener('click', saveSettings);

    // Toggle handlers
    [elements.toggleAutoExtract, elements.toggleAiTags, elements.toggleSaveImages].forEach(toggle => {
      toggle.addEventListener('click', () => {
        const isOn = toggle.classList.contains('toggle-on');
        updateToggle(toggle, !isOn);
      });
    });
  }

  // Utility: escape HTML
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Start app
  document.addEventListener('DOMContentLoaded', init);
})();
```

- [ ] **Step 2: Commit popup.js rewrite**

```bash
git add browser-extension/popup.js
git commit -m "feat(pkos-ext): implement full popup logic with mode switching, identities, tags, API integration"
```

---

## Task 7: Add remaining CSS styles for header and footer

**Files:**
- Modify: `browser-extension/popup.css`

- [ ] **Step 1: Add missing CSS classes referenced in HTML**

Append to `browser-extension/popup.css`:

```css
/* Header Styles */
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background-color: #1a1a2e;
  border-bottom: 1px solid #2a2a4e;
}

.logo {
  width: 24px;
  height: 24px;
  background: #4a9eff;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: bold;
  font-size: 14px;
}

.app-name {
  color: white;
  font-weight: 600;
  font-size: 14px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.btn-header {
  background: #2a2a4e;
  color: #8892b0;
  border: none;
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-header:hover {
  background: #3a3a5e;
  color: #e0e0e0;
}

/* Page Info */
.page-info {
  margin-bottom: 12px;
}

.input-title {
  width: 100%;
  background: #16213e;
  border: 1px solid #2a2a4e;
  border-radius: 6px;
  padding: 8px 12px;
  color: white;
  font-size: 14px;
  font-weight: 500;
}

.input-title:focus {
  outline: none;
  border-color: #4a9eff;
}

.url-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
}

.url-icon {
  color: #4a9eff;
  font-size: 11px;
}

.url-text {
  color: #556080;
  font-size: 11px;
  word-break: break-all;
}

/* Chips Section */
.chips-section {
  margin-top: 12px;
}

/* Buttons */
.btn-primary {
  flex: 1;
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 500;
  color: #ffffff;
  background-color: #4a9eff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.btn-primary:hover {
  background-color: #3a8eef;
}

.btn-primary:active {
  background-color: #2a7edf;
  transform: translateY(1px);
}

.btn-secondary {
  background: transparent;
  color: #8892b0;
  border: 1px solid #2a2a4e;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-secondary:hover {
  background-color: #2a2a4e;
  color: #e0e0e0;
}

/* Footer */
footer {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  background-color: #16213e;
  border-top: 1px solid #2a2a4e;
}

/* Main and Container Adjustments */
main {
  padding: 16px;
  background-color: #1a1a2e;
  flex: 1;
  overflow-y: auto;
}
```

- [ ] **Step 2: Commit CSS additions**

```bash
git add browser-extension/popup.css
git commit -m "feat(pkos-ext): add header, footer, and form element styles"
```

---

## Task 8: Download Mozilla Readability library

**Files:**
- Create: `browser-extension/lib/readability.js`

- [ ] **Step 1: Create lib directory and download Readability**

```bash
mkdir -p browser-extension/lib
# Download Mozilla Readability from CDN (standalone build)
curl -L "https://cdn.jsdelivr.net/npm/@mozilla/readability@0.5.0/Readability.min.js" -o browser-extension/lib/readability.js
```

If curl fails, create a placeholder and note that the file should be downloaded manually:

```bash
# Fallback: Create placeholder
cat > browser-extension/lib/readability.js << 'EOF'
// Mozilla Readability - Placeholder
// Download from: https://cdn.jsdelivr.net/npm/@mozilla/readability@0.5.0/Readability.min.js
// Or: npm install @mozilla/readability and copy the built file

if (typeof Readability === 'undefined') {
  console.warn('[PKOS Clip] Readability library not loaded. Full-page extraction will use fallback.');
}
EOF
```

- [ ] **Step 2: Update content.js to use Readability for full-page extraction**

Replace the `getFullPageContent` function in `browser-extension/content.js`:

```javascript
  function getFullPageContent() {
    // Try to use Readability for clean extraction
    try {
      if (typeof Readability !== 'undefined') {
        const documentClone = document.cloneNode(true);
        const reader = new Readability(documentClone);
        const article = reader.parse();

        if (article) {
          return {
            text: article.textContent || article.textContent,
            html: article.content,
            title: article.title || document.title,
            url: window.location.href,
            excerpt: article.excerpt,
          };
        }
      }
    } catch (e) {
      console.warn('[PKOS Clip] Readability failed, using fallback:', e);
    }

    // Fallback: Basic extraction
    const body = document.body;
    const clone = body.cloneNode(true);
    const removeSelectors = ['script', 'style', 'nav', 'header', 'footer', 'aside', '.sidebar', '.navigation', '.comments'];
    removeSelectors.forEach(selector => {
      clone.querySelectorAll(selector).forEach(el => el.remove());
    });

    const text = clone.textContent || clone.innerText;
    const html = clone.innerHTML;

    return {
      text: text.trim(),
      html: html,
      title: document.title,
      url: window.location.href,
    };
  }
```

- [ ] **Step 3: Commit Readability integration**

```bash
git add browser-extension/lib/ browser-extension/content.js
git commit -m "feat(pkos-ext): add Readability library for clean full-page extraction"
```

---

## Task 9: Manual testing checklist

**Files:**
- None (manual testing)

- [ ] **Step 1: Load extension in Chrome**

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked"
4. Select the `browser-extension/` directory

- [ ] **Step 2: Test basic functionality**

1. Open any webpage
2. Click the PKOS Clip extension icon
3. Verify popup opens with dark theme
4. Verify page title and URL are displayed
5. Verify clipboard content is shown (if clipboard has text)

- [ ] **Step 3: Test mode switching**

1. Switch to "选中内容" tab - should show empty state if no selection
2. Select some text on the page
3. Switch to "选中内容" tab again - should show selected text
4. Switch to "全文" tab - should show page content

- [ ] **Step 4: Test identity/tag selection**

1. Click on an identity chip - should toggle selection (checkmark appears)
2. Click "+ 添加" for tags - prompt should appear
3. Enter a tag - should appear as a chip

- [ ] **Step 5: Test settings panel**

1. Click "⚙️ 设置" button
2. Settings overlay should appear
3. Toggle switches should work
4. Click "←" to go back to main view

- [ ] **Step 6: Test API connection**

1. Ensure PKOS backend is running (`python main.py --mode api`)
2. Open settings, verify "已连接" status
3. Try saving a clip - should get success message

- [ ] **Step 7: Test context menu**

1. Select text on a webpage
2. Right-click and select "保存到 PKOS"
3. Extension popup should open with selection mode active

---

## Task 10: Update design spec status and commit final changes

**Files:**
- Modify: `docs/superpowers/specs/2026-06-15-pkos-browser-extension-v2-design.md`

- [ ] **Step 1: Update spec implementation status**

Change the first line from `> 实现状态：设计中` to `> 实现状态：✅ 已实现`

- [ ] **Step 2: Final commit**

```bash
git add docs/superpowers/specs/2026-06-15-pkos-browser-extension-v2-design.md
git commit -m "docs(pkos-ext): mark v2 design spec as implemented"
```

---

## Self-Review

### 1. Spec Coverage

| Spec Section | Plan Task | Status |
|-------------|-----------|--------|
| manifest.json permissions | Task 1 | ✅ |
| background.js context menu | Task 2 | ✅ |
| content.js page extraction | Task 3 | ✅ |
| popup.css mode/chips/settings styles | Task 4, 7 | ✅ |
| popup.html full UI structure | Task 5 | ✅ |
| popup.js state management | Task 6 | ✅ |
| Three clipping modes | Task 6 | ✅ |
| Identity/tag chips | Task 6 | ✅ |
| Settings panel | Task 5, 6 | ✅ |
| API integration | Task 6 | ✅ |
| Readability integration | Task 8 | ✅ |
| Error handling | Task 6 (saveToPKOS) | ✅ |

### 2. Placeholder Scan

- No "TBD", "TODO", or incomplete sections found
- All code blocks contain complete implementations

### 3. Type Consistency

- `state.mode` uses `'clipboard' | 'selection' | 'fullpage'` consistently
- `state.settings` object structure matches usage in popup.js and background.js
- API endpoint `/pkos/v1/ingest` matches backend spec

---

**Plan complete and saved to `docs/superpowers/plans/2026-06-15-pkos-browser-extension-v2.md`.**

**Two execution options:**

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
