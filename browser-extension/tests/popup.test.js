/**
 * Popup Script Tests
 * Tests for utility functions and UI logic
 */

const PopupUtils = require('./popup-utils.js');

describe('Popup Utils', () => {
  describe('escapeHtml', () => {
    test('should escape HTML special characters', () => {
      expect(PopupUtils.escapeHtml('<script>alert("xss")</script>'))
        .toBe('&lt;script&gt;alert("xss")&lt;/script&gt;');
    });

    test('should handle empty string', () => {
      expect(PopupUtils.escapeHtml('')).toBe('');
    });

    test('should not modify plain text', () => {
      expect(PopupUtils.escapeHtml('Hello World')).toBe('Hello World');
    });

    test('should escape ampersand', () => {
      expect(PopupUtils.escapeHtml('Tom & Jerry')).toBe('Tom &amp; Jerry');
    });
  });

  describe('updateToggle', () => {
    test('should set toggle-on class when isOn is true', () => {
      const element = { className: '' };
      PopupUtils.updateToggle(element, true);
      expect(element.className).toBe('toggle toggle-on');
    });

    test('should set toggle-off class when isOn is false', () => {
      const element = { className: '' };
      PopupUtils.updateToggle(element, false);
      expect(element.className).toBe('toggle toggle-off');
    });
  });

  describe('isToggleOn', () => {
    test('should return true for toggle-on element', () => {
      const element = { classList: { contains: (cls) => cls === 'toggle-on' } };
      expect(PopupUtils.isToggleOn(element)).toBe(true);
    });

    test('should return false for toggle-off element', () => {
      const element = { classList: { contains: (cls) => cls === 'toggle-on' ? false : true } };
      expect(PopupUtils.isToggleOn(element)).toBe(false);
    });
  });

  describe('renderIdentityChips', () => {
    test('should render identity chips with selected state', () => {
      const html = PopupUtils.renderIdentityChips(
        ['程序员', '好爸爸'],
        ['程序员'],
        []
      );

      expect(html).toContain('程序员');
      expect(html).toContain('selected');
    });

    test('should show checkmark for selected identities', () => {
      const html = PopupUtils.renderIdentityChips(
        ['程序员'],
        ['程序员'],
        []
      );

      expect(html).toContain('✓');
    });

    test('should show checkmark for default identities', () => {
      const html = PopupUtils.renderIdentityChips(
        ['程序员', '好爸爸'],
        [],
        ['程序员']
      );

      expect(html).toContain('selected');
    });

    test('should include add button', () => {
      const html = PopupUtils.renderIdentityChips([], [], []);
      expect(html).toContain('+ 添加');
    });

    test('should handle empty identities', () => {
      const html = PopupUtils.renderIdentityChips(null, null, null);
      expect(html).toContain('+ 添加');
    });
  });

  describe('renderTagChips', () => {
    test('should render tag chips', () => {
      const html = PopupUtils.renderTagChips(['python', '教育']);

      expect(html).toContain('#python');
      expect(html).toContain('#教育');
    });

    test('should include remove button', () => {
      const html = PopupUtils.renderTagChips(['test']);

      expect(html).toContain('✕');
    });

    test('should include add button', () => {
      const html = PopupUtils.renderTagChips([]);

      expect(html).toContain('+ 添加');
    });

    test('should handle empty tags', () => {
      const html = PopupUtils.renderTagChips(null);

      expect(html).toContain('+ 添加');
    });
  });

  describe('renderContentPreview', () => {
    test('should render content with character count', () => {
      const html = PopupUtils.renderContentPreview('Hello World');

      expect(html).toContain('Hello World');
      expect(html).toContain('11 字符');
    });

    test('should truncate long content', () => {
      const longContent = 'A'.repeat(600);
      const html = PopupUtils.renderContentPreview(longContent);

      expect(html).toContain('...');
      expect(html).toContain('600 字符');
    });

    test('should escape HTML in content', () => {
      const html = PopupUtils.renderContentPreview('<script>alert(1)</script>');

      expect(html).not.toContain('<script>');
      expect(html).toContain('&lt;script&gt;');
    });

    test('should use custom max chars', () => {
      const content = 'A'.repeat(200);
      const html = PopupUtils.renderContentPreview(content, 100);

      expect(html).toContain('...');
    });
  });

  describe('renderEmptyState', () => {
    test('should render empty state message', () => {
      const html = PopupUtils.renderEmptyState('剪切板为空');

      expect(html).toContain('剪切板为空');
      expect(html).toContain('empty-state');
    });
  });

  describe('renderSaveStatus', () => {
    test('should render success status', () => {
      const result = PopupUtils.renderSaveStatus('success', '保存成功');

      expect(result.className).toBe('save-status success');
      expect(result.textContent).toBe('保存成功');
    });

    test('should render error status', () => {
      const result = PopupUtils.renderSaveStatus('error', '保存失败');

      expect(result.className).toBe('save-status error');
    });

    test('should render loading status', () => {
      const result = PopupUtils.renderSaveStatus('loading', '保存中...');

      expect(result.className).toBe('save-status loading');
    });
  });

  describe('toggleIdentity', () => {
    test('should add identity if not present', () => {
      const identities = ['程序员'];
      const result = PopupUtils.toggleIdentity(identities, '好爸爸');

      expect(result).toContain('程序员');
      expect(result).toContain('好爸爸');
    });

    test('should remove identity if present', () => {
      const identities = ['程序员', '好爸爸'];
      const result = PopupUtils.toggleIdentity(identities, '程序员');

      expect(result).not.toContain('程序员');
      expect(result).toContain('好爸爸');
    });
  });

  describe('addTag', () => {
    test('should add new tag', () => {
      const tags = ['python'];
      const result = PopupUtils.addTag(tags, '教育');

      expect(result).toContain('教育');
    });

    test('should not add duplicate tag', () => {
      const tags = ['python'];
      const result = PopupUtils.addTag(tags, 'python');

      expect(result.length).toBe(1);
    });

    test('should trim whitespace', () => {
      const tags = [];
      const result = PopupUtils.addTag(tags, '  test  ');

      expect(result).toContain('test');
    });

    test('should not add empty tag', () => {
      const tags = [];
      const result = PopupUtils.addTag(tags, '   ');

      expect(result.length).toBe(0);
    });
  });

  describe('removeTag', () => {
    test('should remove existing tag', () => {
      const tags = ['python', '教育'];
      const result = PopupUtils.removeTag(tags, 'python');

      expect(result).not.toContain('python');
      expect(result).toContain('教育');
    });

    test('should handle non-existent tag', () => {
      const tags = ['python'];
      const result = PopupUtils.removeTag(tags, '教育');

      expect(result).toContain('python');
    });
  });

  describe('createIngestFormData', () => {
    test('should create FormData with all fields', () => {
      const formData = PopupUtils.createIngestFormData(
        'Test Title',
        'https://example.com',
        ['程序员'],
        ['python'],
        'Test content'
      );

      expect(formData.get('source_type')).toBe('browser_clip');
      expect(formData.get('source_url')).toBe('https://example.com');
      expect(formData.get('identities')).toBe('程序员');
      expect(formData.get('tags')).toBe('python');
      expect(formData.get('title')).toBe('Test Title');
    });

    test('should use default title when not provided', () => {
      const formData = PopupUtils.createIngestFormData(
        null,
        'https://example.com',
        [],
        [],
        'Content'
      );

      expect(formData.get('title')).toBe('未命名文档');
    });

    test('should create file blob', () => {
      const formData = PopupUtils.createIngestFormData(
        'Title',
        'https://example.com',
        [],
        [],
        'Content'
      );

      const file = formData.get('file');
      expect(file).not.toBeNull();
    });
  });

  describe('isValidApiEndpoint', () => {
    test('should validate http URL', () => {
      expect(PopupUtils.isValidApiEndpoint('http://localhost:8000')).toBe(true);
    });

    test('should validate https URL', () => {
      expect(PopupUtils.isValidApiEndpoint('https://api.example.com')).toBe(true);
    });

    test('should reject invalid URL', () => {
      expect(PopupUtils.isValidApiEndpoint('not-a-url')).toBe(false);
    });

    test('should reject empty string', () => {
      expect(PopupUtils.isValidApiEndpoint('')).toBe(false);
    });
  });

  describe('getDefaultSettings', () => {
    test('should return default settings object', () => {
      const settings = PopupUtils.getDefaultSettings();

      expect(settings.apiEndpoint).toBe('http://localhost:8000');
      expect(settings.autoExtract).toBe(true);
      expect(settings.aiTags).toBe(true);
      expect(settings.saveImages).toBe(false);
      expect(settings.identities).toContain('程序员');
    });
  });

  describe('mergeSettings', () => {
    test('should merge stored settings with defaults', () => {
      const merged = PopupUtils.mergeSettings({ apiEndpoint: 'http://custom:9000' });

      expect(merged.apiEndpoint).toBe('http://custom:9000');
      expect(merged.autoExtract).toBe(true);
    });

    test('should keep default for missing keys', () => {
      const merged = PopupUtils.mergeSettings({});

      expect(merged.apiEndpoint).toBe('http://localhost:8000');
    });

    test('should override default identities', () => {
      const merged = PopupUtils.mergeSettings({ defaultIdentities: ['学生'] });

      expect(merged.defaultIdentities).toContain('学生');
    });
  });
});
