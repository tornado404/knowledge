// content.js - PKOS Clip Content Script

(function () {
  'use strict';

  // Cache for selected text - memory only, sufficient since content script lives as long as the page
  let cachedSelection = { text: '', html: '' };

  // Helper function to get HTML from selection
  function getSelectionHtml(selection) {
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
    return html;
  }

  // Listen for selection changes and cache to memory
  // Chrome clears selection when popup opens, so we need this cache
  document.addEventListener('selectionchange', () => {
    const selection = window.getSelection();
    const text = selection.toString().trim();

    if (text) {
      cachedSelection = {
        text: text,
        html: getSelectionHtml(selection)
      };
    }
  });

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
    return new URL('/favicon.ico', window.location.origin).href;
  }

  function getMetaDescription() {
    const meta = document.querySelector('meta[name="description"]');
    return meta ? meta.getAttribute('content') : '';
  }

  function getSelection() {
    const selection = window.getSelection();
    const text = selection.toString().trim();

    // If there's current selection, return it
    if (text) {
      return {
        selection: text,
        html: getSelectionHtml(selection)
      };
    }

    // If no current selection but we have cached selection, return that
    // This handles the case where Chrome cleared selection when popup opened
    if (cachedSelection.text) {
      return {
        selection: cachedSelection.text,
        html: cachedSelection.html
      };
    }

    return { selection: '', html: '' };
  }

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
})();
