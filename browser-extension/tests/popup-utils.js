/**
 * Popup Script - Testable Utility Functions
 * Extracted from popup.js for unit testing
 */

const PopupUtils = {
  /**
   * Escape HTML special characters
   */
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  },

  /**
   * Update toggle state
   */
  updateToggle(element, isOn) {
    element.className = `toggle ${isOn ? 'toggle-on' : 'toggle-off'}`;
  },

  /**
   * Check if toggle is on
   */
  isToggleOn(element) {
    return element.classList.contains('toggle-on');
  },

  /**
   * Generate identity chip HTML
   */
  renderIdentityChips(identities, selectedIdentities, defaultIdentities) {
    const allIdentities = identities || [];
    const selected = selectedIdentities || [];
    const defaults = defaultIdentities || [];

    return allIdentities.map(id => {
      const isSelected = selected.includes(id) || defaults.includes(id);
      return `<span class="chip chip-identity ${isSelected ? 'selected' : ''}" data-identity="${id}">👤 ${id} ${isSelected ? '✓' : ''}</span>`;
    }).join('') + '<span class="chip chip-add" id="add-identity">+ 添加</span>';
  },

  /**
   * Generate tag chip HTML
   */
  renderTagChips(tags) {
    return (tags || []).map(tag =>
      `<span class="chip chip-tag selected" data-tag="${tag}">#${tag} <span class="chip-remove" data-tag="${tag}">✕</span></span>`
    ).join('') + '<span class="chip chip-add" id="add-tag">+ 添加</span>';
  },

  /**
   * Generate content preview HTML
   */
  renderContentPreview(content, maxChars = 500) {
    const preview = content.substring(0, maxChars);
    const charCount = content.length;
    const escaped = this.escapeHtml(preview);

    return `<p>${escaped}${charCount > maxChars ? '...' : ''}</p><div class="content-meta">📄 ${charCount} 字符</div>`;
  },

  /**
   * Generate empty state HTML
   */
  renderEmptyState(message) {
    return `<p class="empty-state">${message}</p>`;
  },

  /**
   * Generate save status HTML
   */
  renderSaveStatus(status, message) {
    return { className: `save-status ${status}`, textContent: message };
  },

  /**
   * Toggle identity in array
   */
  toggleIdentity(identities, identity) {
    const index = identities.indexOf(identity);
    if (index >= 0) {
      identities.splice(index, 1);
    } else {
      identities.push(identity);
    }
    return identities;
  },

  /**
   * Add tag to array if not exists
   */
  addTag(tags, tag) {
    const trimmed = tag.trim();
    if (trimmed && !tags.includes(trimmed)) {
      tags.push(trimmed);
    }
    return tags;
  },

  /**
   * Remove tag from array
   */
  removeTag(tags, tag) {
    return tags.filter(t => t !== tag);
  },

  /**
   * Create FormData for API request
   */
  createIngestFormData(title, url, identities, tags, content) {
    const formData = new FormData();
    formData.append('source_type', 'browser_clip');
    formData.append('source_url', url);
    formData.append('identities', identities.join(','));
    formData.append('tags', tags.join(','));
    formData.append('title', title || '未命名文档');

    const blob = new Blob([content], { type: 'text/markdown' });
    formData.append('file', blob, 'clip.md');

    return formData;
  },

  /**
   * Validate API endpoint URL
   */
  isValidApiEndpoint(url) {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  },

  /**
   * Get default settings
   */
  getDefaultSettings() {
    return {
      apiEndpoint: 'http://localhost:8000',
      defaultIdentities: [],
      autoExtract: true,
      aiTags: true,
      saveImages: false,
      identities: ['程序员', '好爸爸', '学生', '研究者', '创作者'],
    };
  },

  /**
   * Merge settings with defaults
   */
  mergeSettings(stored) {
    const defaults = this.getDefaultSettings();
    return { ...defaults, ...stored };
  }
};

module.exports = PopupUtils;
