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
