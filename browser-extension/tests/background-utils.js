/**
 * Background Script - Testable Utility Functions
 * Extracted from background.js for unit testing
 */

const BackgroundUtils = {
  /**
   * Get default settings
   */
  getDefaultSettings() {
    return {
      apiEndpoint: 'http://localhost:8000',
      autoExtract: true,
      aiTags: true,
      saveImages: false,
      defaultIdentities: ['程序员', '好爸爸', '学生', '研究者', '创作者'],
    };
  },

  /**
   * Create context menu config
   */
  createContextMenuConfig() {
    return {
      id: 'pkos-save-selection',
      title: '保存到 PKOS',
      contexts: ['selection'],
    };
  },

  /**
   * Create pending selection object
   */
  createPendingSelection(text, html, url, title) {
    return {
      text,
      html,
      url,
      title,
      timestamp: Date.now(),
    };
  },

  /**
   * Check if menu item is our save selection
   */
  isSaveSelectionMenu(menuItemId) {
    return menuItemId === 'pkos-save-selection';
  },

  /**
   * Create page info request message
   */
  createPageInfoRequest() {
    return { type: 'GET_PAGE_INFO' };
  },

  /**
   * Create selection request message
   */
  createSelectionRequest() {
    return { type: 'GET_SELECTION_FROM_PAGE' };
  },

  /**
   * Create full page content request message
   */
  createFullPageRequest() {
    return { type: 'GET_FULLPAGE_CONTENT' };
  },

  /**
   * Handle message type routing
   */
  handleIncomingMessage(message) {
    const validTypes = ['GET_PAGE_INFO', 'GET_SELECTION_FROM_PAGE', 'GET_FULLPAGE_CONTENT'];
    return validTypes.includes(message.type);
  },

  /**
   * Create error response for no active tab
   */
  createNoTabError() {
    return { error: 'No active tab' };
  },

  /**
   * Format settings for storage
   */
  formatSettingsForStorage(settings) {
    return {
      apiEndpoint: settings.apiEndpoint || 'http://localhost:8000',
      autoExtract: settings.autoExtract !== undefined ? settings.autoExtract : true,
      aiTags: settings.aiTags !== undefined ? settings.aiTags : true,
      saveImages: settings.saveImages !== undefined ? settings.saveImages : false,
      defaultIdentities: settings.defaultIdentities || [],
    };
  },
};

module.exports = BackgroundUtils;
