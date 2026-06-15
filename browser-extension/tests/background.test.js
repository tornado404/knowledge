/**
 * Background Script Tests
 * Tests for utility functions extracted from background.js
 */

const BackgroundUtils = require('./background-utils.js');

describe('Background Utils', () => {
  describe('getDefaultSettings', () => {
    test('should return default settings object', () => {
      const settings = BackgroundUtils.getDefaultSettings();

      expect(settings.apiEndpoint).toBe('http://localhost:8000');
      expect(settings.autoExtract).toBe(true);
      expect(settings.aiTags).toBe(true);
      expect(settings.saveImages).toBe(false);
      expect(settings.defaultIdentities).toContain('程序员');
      expect(settings.defaultIdentities).toContain('好爸爸');
    });
  });

  describe('createContextMenuConfig', () => {
    test('should create context menu config', () => {
      const config = BackgroundUtils.createContextMenuConfig();

      expect(config.id).toBe('pkos-save-selection');
      expect(config.title).toBe('保存到 PKOS');
      expect(config.contexts).toContain('selection');
    });
  });

  describe('createPendingSelection', () => {
    test('should create pending selection with all fields', () => {
      const pending = BackgroundUtils.createPendingSelection(
        'Selected text',
        '<p>Selected text</p>',
        'https://example.com',
        'Example Page'
      );

      expect(pending.text).toBe('Selected text');
      expect(pending.html).toBe('<p>Selected text</p>');
      expect(pending.url).toBe('https://example.com');
      expect(pending.title).toBe('Example Page');
      expect(pending.timestamp).toBeDefined();
    });

    test('should include timestamp', () => {
      const before = Date.now();
      const pending = BackgroundUtils.createPendingSelection('test', '', 'url', 'title');
      const after = Date.now();

      expect(pending.timestamp).toBeGreaterThanOrEqual(before);
      expect(pending.timestamp).toBeLessThanOrEqual(after);
    });
  });

  describe('isSaveSelectionMenu', () => {
    test('should return true for pkos-save-selection', () => {
      expect(BackgroundUtils.isSaveSelectionMenu('pkos-save-selection')).toBe(true);
    });

    test('should return false for other menu items', () => {
      expect(BackgroundUtils.isSaveSelectionMenu('other-menu')).toBe(false);
      expect(BackgroundUtils.isSaveSelectionMenu('')).toBe(false);
    });
  });

  describe('Message Creation', () => {
    test('should create page info request', () => {
      const msg = BackgroundUtils.createPageInfoRequest();
      expect(msg.type).toBe('GET_PAGE_INFO');
    });

    test('should create selection request', () => {
      const msg = BackgroundUtils.createSelectionRequest();
      expect(msg.type).toBe('GET_SELECTION_FROM_PAGE');
    });

    test('should create full page request', () => {
      const msg = BackgroundUtils.createFullPageRequest();
      expect(msg.type).toBe('GET_FULLPAGE_CONTENT');
    });
  });

  describe('handleIncomingMessage', () => {
    test('should recognize GET_PAGE_INFO', () => {
      expect(BackgroundUtils.handleIncomingMessage({ type: 'GET_PAGE_INFO' })).toBe(true);
    });

    test('should recognize GET_SELECTION_FROM_PAGE', () => {
      expect(BackgroundUtils.handleIncomingMessage({ type: 'GET_SELECTION_FROM_PAGE' })).toBe(true);
    });

    test('should recognize GET_FULLPAGE_CONTENT', () => {
      expect(BackgroundUtils.handleIncomingMessage({ type: 'GET_FULLPAGE_CONTENT' })).toBe(true);
    });

    test('should reject unknown message types', () => {
      expect(BackgroundUtils.handleIncomingMessage({ type: 'UNKNOWN' })).toBe(false);
      expect(BackgroundUtils.handleIncomingMessage({ type: '' })).toBe(false);
      expect(BackgroundUtils.handleIncomingMessage({})).toBe(false);
    });
  });

  describe('createNoTabError', () => {
    test('should create error response', () => {
      const error = BackgroundUtils.createNoTabError();
      expect(error.error).toBe('No active tab');
    });
  });

  describe('formatSettingsForStorage', () => {
    test('should use provided values', () => {
      const formatted = BackgroundUtils.formatSettingsForStorage({
        apiEndpoint: 'http://custom:9000',
        autoExtract: false,
        aiTags: false,
        saveImages: true,
        defaultIdentities: ['学生'],
      });

      expect(formatted.apiEndpoint).toBe('http://custom:9000');
      expect(formatted.autoExtract).toBe(false);
      expect(formatted.aiTags).toBe(false);
      expect(formatted.saveImages).toBe(true);
      expect(formatted.defaultIdentities).toContain('学生');
    });

    test('should use defaults for missing values', () => {
      const formatted = BackgroundUtils.formatSettingsForStorage({});

      expect(formatted.apiEndpoint).toBe('http://localhost:8000');
      expect(formatted.autoExtract).toBe(true);
      expect(formatted.aiTags).toBe(true);
      expect(formatted.saveImages).toBe(false);
      expect(formatted.defaultIdentities).toEqual([]);
    });

    test('should handle partial settings', () => {
      const formatted = BackgroundUtils.formatSettingsForStorage({
        apiEndpoint: 'http://test:3000',
      });

      expect(formatted.apiEndpoint).toBe('http://test:3000');
      expect(formatted.autoExtract).toBe(true);
    });
  });
});
