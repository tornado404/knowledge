/**
 * Content Script Tests
 * Tests for page info extraction, selection handling, and full-page content extraction
 */

const ContentScript = require('./content-utils.js');

describe('Content Script', () => {
  beforeEach(() => {
    // Reset document
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

    test('should return empty string for missing description', () => {
      document.title = 'Test';
      document.body.innerHTML = '<div>Content</div>';

      const info = ContentScript.getPageInfo();

      expect(info.description).toBe('');
    });

    test('should return empty title when not set', () => {
      document.body.innerHTML = '<div>Content</div>';

      const info = ContentScript.getPageInfo();

      expect(info.title).toBe('');
    });
  });

  describe('getFavicon', () => {
    test('should find shortcut icon', () => {
      document.head.innerHTML = '<link rel="shortcut icon" href="/favicon-v2.ico">';

      const favicon = ContentScript.getFavicon();

      // Favicon returns full URL based on document location
      expect(favicon).toContain('favicon-v2.ico');
    });
  });

  describe('getMetaDescription', () => {
    test('should handle meta tag with additional attributes', () => {
      document.head.innerHTML = '<meta name="description" content="Test" id="desc" lang="en">';

      const desc = ContentScript.getMetaDescription();

      expect(desc).toBe('Test');
    });
  });

  describe('getSelection', () => {
    test('should return empty selection when nothing selected', () => {
      document.body.innerHTML = '<p>No selection here</p>';

      const result = ContentScript.getSelection();

      expect(result.selection).toBe('');
      expect(result.html).toBe('');
    });

    test('should return selected text', () => {
      document.body.innerHTML = '<p id="target">Selected text here</p>';

      // Create a selection
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
      expect(result.title).toBe('Article Title');
      expect(result.url).toBe('http://localhost/');
    });

    test('should remove script and style elements', () => {
      document.body.innerHTML = `
        <main>Content</main>
        <script>var x = 1;</script>
        <style>.hidden { display: none; }</style>
        <nav>Navigation</nav>
      `;
      document.title = 'Test';

      const result = ContentScript.getFullPageContent();

      expect(result.text).toContain('Content');
      expect(result.text).not.toContain('var x');
      expect(result.text).not.toContain('.hidden');
      expect(result.text).not.toContain('Navigation');
    });

    test('should remove header and footer', () => {
      document.body.innerHTML = `
        <header>Header Content</header>
        <main>Main Content</main>
        <footer>Footer Content</footer>
      `;
      document.title = 'Test';

      const result = ContentScript.getFullPageContent();

      expect(result.text).toContain('Main Content');
      expect(result.text).not.toContain('Header Content');
      expect(result.text).not.toContain('Footer Content');
    });

    test('should include HTML in response', () => {
      document.body.innerHTML = '<main><h1>Title</h1><p>Paragraph</p></main>';
      document.title = 'Test';

      const result = ContentScript.getFullPageContent();

      expect(result.html).toContain('<h1>Title</h1>');
    });

    test('should remove aside and comments', () => {
      document.body.innerHTML = `
        <main>Content</main>
        <aside>Sidebar</aside>
        <div class="comments">User comments</div>
      `;

      const result = ContentScript.getFullPageContent();

      expect(result.text).toContain('Content');
      expect(result.text).not.toContain('Sidebar');
      expect(result.text).not.toContain('User comments');
    });
  });

  describe('handleMessage', () => {
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
      document.title = 'Test';
      let response;
      ContentScript.handleMessage({ type: 'GET_FULLPAGE' }, {}, (res) => { response = res; });

      expect(response.text).toContain('Content');
    });

    test('should handle unknown message type', () => {
      let response;
      ContentScript.handleMessage({ type: 'UNKNOWN' }, {}, (res) => { response = res; });

      expect(response.error).toBe('Unknown message type');
    });

    test('should return true for async response', () => {
      const result = ContentScript.handleMessage({ type: 'GET_PAGE_INFO' }, {}, () => {});
      expect(result).toBe(true);
    });
  });
});
