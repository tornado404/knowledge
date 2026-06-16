// popup.js - PKOS Clip Main UI Logic

(function () {
  'use strict';

  // Application State
  const state = {
    mode: 'selection',  // 'clipboard' | 'selection' | 'fullpage'
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
    await loadContentForMode();
    renderIdentities();
    renderTags();
    setupEventListeners();
    testConnection();
  }

  // Load content based on current mode
  async function loadContentForMode() {
    switch (state.mode) {
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
    elements.mainView.classList.add('main-view-hidden');
    elements.settingsOverlay.classList.add('visible');
  }

  // Hide settings overlay
  function hideSettings() {
    elements.settingsOverlay.classList.remove('visible');
    elements.mainView.classList.remove('main-view-hidden');
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
