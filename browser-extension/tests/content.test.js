/**
 * Content Script Tests
 * Tests for page info extraction, selection handling, and full-page content extraction
 */

const ContentScript = require('./content-utils.js');

describe('Content Script', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    document.head.innerHTML = '';
    document.title = '';
  });

  describe('getPageInfo', () => {
    test('should extract page title', () => {
      document.title = 'Test Page Title';
      document.body.innerHTML = '<div>Content</div>';

      const info = ContentScript.getPageInfo();

      expect(info.title).toBe('Test Page Title');
      expect(info.url).toBe('http://localhost/');
    });

    test('should extract favicon link', () => {
      document.head.innerHTML = '<link rel="icon" href="https://example.com/favicon.png">';
      document.title = 'Test';

      const info = ContentScript.getPageInfo();

      expect(info.favicon).toBe('https://example.com/favicon.png');
    });

    test('should return default favicon when no link element', () => {
      document.title = 'Test';
      document.body.innerHTML = '<div>Content</div>';

      const info = ContentScript.getPageInfo();

      expect(info.favicon).toBe('http://localhost/favicon.ico');
    });

    test('should extract meta description', () => {
      document.head.innerHTML = '<meta name="description" content="This is a test description">';
      document.title = 'Test';

      const info = ContentScript.getPageInfo();

      expect(info.description).toBe('This is a test description');
    });
  });

  describe('getSelection', () => {
    test('should return empty selection when nothing selected', () => {
      document.body.innerHTML = '<p>No selection here</p>';
      ContentScript._reset();

      const result = ContentScript.getSelection();

      expect(result.selection).toBe('');
      expect(result.html).toBe('');
    });

    test('should return selected text', () => {
      document.body.innerHTML = '<p id="target">Selected text here</p>';

      const target = document.getElementById('target');
      const range = document.createRange();
      range.selectNodeContents(target);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);

      const result = ContentScript.getSelection();

      expect(result.selection).toContain('Selected text here');
    });

    test('should include HTML of selection', () => {
      document.body.innerHTML = '<p id="target"><strong>Bold</strong> text</p>';

      const target = document.getElementById('target');
      const range = document.createRange();
      range.selectNodeContents(target);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);

      const result = ContentScript.getSelection();

      expect(result.html).toContain('<strong>Bold</strong>');
    });
  });

  describe('Selection Caching', () => {
    // Wikipedia 朱元璋词条内容作为测试数据
    const ZHU_YUANZHANG = {
      intro: '明太祖朱元璋（1328年10月21日—1398年6月24日），字国瑞，原名朱重八、朱兴宗，濠州钟离（今安徽省凤阳县）人，中国明朝开国皇帝。',
      html: '<p><strong>明太祖朱元璋</strong>（1328年10月21日—1398年6月24日）...</p>'
    };

    beforeEach(() => {
      ContentScript._reset();
      document.body.innerHTML = '';
    });

    test('should cache selection in memory', () => {
      document.body.innerHTML = `<p id="intro">${ZHU_YUANZHANG.intro}</p>`;

      const intro = document.getElementById('intro');
      const range = document.createRange();
      range.selectNodeContents(intro);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);

      ContentScript.onSelectionChange(selection);

      expect(ContentScript._cachedSelection.text).toContain('朱元璋');
    });

    test('should return cached selection when Chrome clears selection', () => {
      document.body.innerHTML = `<p id="intro">${ZHU_YUANZHANG.intro}</p>`;

      // 用户选中文字
      const intro = document.getElementById('intro');
      const range = document.createRange();
      range.selectNodeContents(intro);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);

      // 缓存选中内容
      ContentScript.onSelectionChange(selection);

      // 验证当前有选中
      let result = ContentScript.getSelection();
      expect(result.selection).toContain('朱元璋');

      // Chrome 清除 selection（popup 打开时）
      ContentScript.clearSelection();

      // 仍然能返回缓存的内容
      result = ContentScript.getSelection();
      expect(result.selection).toContain('朱元璋');
      expect(result.selection).toContain('明朝开国皇帝');
    });

    test('should handle multiple selection changes (last one wins)', () => {
      document.body.innerHTML = `
        <p id="p1">朱元璋出生于贫苦农民家庭。</p>
        <p id="p2">他后来建立了明朝，成为开国皇帝。</p>
      `;

      // 第一次选中
      const p1 = document.getElementById('p1');
      let range = document.createRange();
      range.selectNodeContents(p1);
      let selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      ContentScript.onSelectionChange(selection);

      // 第二次选中
      const p2 = document.getElementById('p2');
      range = document.createRange();
      range.selectNodeContents(p2);
      selection.removeAllRanges();
      selection.addRange(range);
      ContentScript.onSelectionChange(selection);

      // popup 打开
      ContentScript.clearSelection();

      const result = ContentScript.getSelection();
      expect(result.selection).toContain('开国皇帝');
      expect(result.selection).not.toContain('贫苦农民');
    });

    test('should not cache empty selection', () => {
      document.body.innerHTML = '<p>Content</p>';
      const selection = window.getSelection();
      selection.removeAllRanges();

      ContentScript.onSelectionChange(selection);

      expect(ContentScript._cachedSelection.text).toBe('');
    });

    test('should handle HTML content in cached selection', () => {
      document.body.innerHTML = `<div id="content">${ZHU_YUANZHANG.html}</div>`;

      const content = document.getElementById('content');
      const range = document.createRange();
      range.selectNodeContents(content);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);

      ContentScript.onSelectionChange(selection);
      ContentScript.clearSelection();

      const result = ContentScript.getSelection();
      expect(result.selection).toContain('朱元璋');
      expect(result.html).toContain('<strong>');
    });
  });

  describe('getFullPageContent', () => {
    test('should extract text content from body', () => {
      document.body.innerHTML = `
        <main>
          <h1>Article Title</h1>
          <p>This is the article content.</p>
        </main>
      `;
      document.title = 'Article Title';

      const result = ContentScript.getFullPageContent();

      expect(result.text).toContain('Article Title');
      expect(result.text).toContain('article content');
    });

    test('should remove script and style elements', () => {
      document.body.innerHTML = `
        <main>Content</main>
        <script>var x = 1;</script>
        <style>.hidden { display: none; }</style>
        <nav>Navigation</nav>
      `;

      const result = ContentScript.getFullPageContent();

      expect(result.text).toContain('Content');
      expect(result.text).not.toContain('var x');
      expect(result.text).not.toContain('.hidden');
    });

    test('should remove header and footer', () => {
      document.body.innerHTML = `
        <header>Header</header>
        <main>Main Content</main>
        <footer>Footer</footer>
      `;

      const result = ContentScript.getFullPageContent();

      expect(result.text).toContain('Main Content');
      expect(result.text).not.toContain('Header');
      expect(result.text).not.toContain('Footer');
    });
  });

  describe('handleMessage', () => {
    beforeEach(() => {
      document.body.innerHTML = '';
      document.title = '';
      ContentScript._reset();
    });

    test('should handle GET_PAGE_INFO message', () => {
      document.title = 'Test Page';
      let response;
      ContentScript.handleMessage({ type: 'GET_PAGE_INFO' }, {}, (res) => { response = res; });

      expect(response.title).toBe('Test Page');
    });

    test('should handle GET_SELECTION message', () => {
      document.body.innerHTML = '<p>Content</p>';
      let response;
      ContentScript.handleMessage({ type: 'GET_SELECTION' }, {}, (res) => { response = res; });

      expect(response.selection).toBe('');
    });

    test('should handle GET_FULLPAGE message', () => {
      document.body.innerHTML = '<main>Content</main>';
      let response;
      ContentScript.handleMessage({ type: 'GET_FULLPAGE' }, {}, (res) => { response = res; });

      expect(response.text).toContain('Content');
    });

    test('should handle unknown message type', () => {
      let response;
      ContentScript.handleMessage({ type: 'UNKNOWN' }, {}, (res) => { response = res; });

      expect(response.error).toBe('Unknown message type');
    });
  });
});
