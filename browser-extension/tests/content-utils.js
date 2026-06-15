/**
 * Content Script - Testable Version
 * This module exports functions for testing while maintaining the original IIFE structure
 */

// Extract functions for testing
const ContentScript = {
  getPageInfo() {
    return {
      title: document.title || '',
      url: window.location.href,
      favicon: this.getFavicon(),
      description: this.getMetaDescription(),
    };
  },

  getFavicon() {
    const link = document.querySelector('link[rel="icon"]') ||
                 document.querySelector('link[rel="shortcut icon"]');
    if (link) {
      return link.href;
    }
    return new URL('/favicon.ico', window.location.origin).href;
  },

  getMetaDescription() {
    const meta = document.querySelector('meta[name="description"]');
    return meta ? meta.getAttribute('content') : '';
  },

  getSelection() {
    const selection = window.getSelection();
    const text = selection.toString().trim();

    if (!text) {
      return { selection: '', html: '' };
    }

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
  },

  getFullPageContent() {
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
  },

  handleMessage(message, sender, sendResponse) {
    switch (message.type) {
      case 'GET_PAGE_INFO':
        sendResponse(this.getPageInfo());
        break;

      case 'GET_SELECTION':
        sendResponse(this.getSelection());
        break;

      case 'GET_FULLPAGE':
        sendResponse(this.getFullPageContent());
        break;

      default:
        sendResponse({ error: 'Unknown message type' });
    }
    return true;
  },

  init() {
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      return this.handleMessage(message, sender, sendResponse);
    });
    console.log('[PKOS Clip] Content script loaded on', window.location.href);
  }
};

// For testing
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ContentScript;
}
