/**
 * Jest setup file - Mock Chrome Extension APIs
 */

// Mock chrome.storage.local
const mockStorage = {
  _data: {},
  get: jest.fn((keys) => {
    const result = {};
    const keyArray = Array.isArray(keys) ? keys : [keys];
    keyArray.forEach(key => {
      if (mockStorage._data[key] !== undefined) {
        result[key] = mockStorage._data[key];
      }
    });
    return Promise.resolve(result);
  }),
  set: jest.fn((data) => {
    Object.assign(mockStorage._data, data);
    return Promise.resolve();
  }),
  remove: jest.fn((keys) => {
    const keyArray = Array.isArray(keys) ? keys : [keys];
    keyArray.forEach(key => delete mockStorage._data[key]);
    return Promise.resolve();
  }),
  clear: jest.fn(() => {
    mockStorage._data = {};
    return Promise.resolve();
  }),
};

// Mock chrome.tabs
const mockTabs = {
  query: jest.fn((queryInfo, callback) => {
    callback([{ id: 123, url: 'https://example.com', title: 'Test Page' }]);
  }),
  sendMessage: jest.fn((tabId, message, callback) => {
    if (callback) callback({ title: 'Test Page', url: 'https://example.com' });
  }),
};

// Mock chrome.runtime
const mockRuntime = {
  onInstalled: { addListener: jest.fn() },
  onMessage: { addListener: jest.fn() },
  sendMessage: jest.fn((message, callback) => {
    if (callback) callback({ title: 'Test Page', url: 'https://example.com' });
  }),
  lastError: null,
};

// Mock chrome.contextMenus
const mockContextMenus = {
  create: jest.fn(),
  onClicked: { addListener: jest.fn() },
};

// Mock chrome.action
const mockAction = {
  openPopup: jest.fn(() => Promise.resolve()),
};

// Assign to global chrome object
global.chrome = {
  storage: { local: mockStorage },
  tabs: mockTabs,
  runtime: mockRuntime,
  contextMenus: mockContextMenus,
  action: mockAction,
};

// Export for use in tests
module.exports = {
  mockStorage,
  mockTabs,
  mockRuntime,
  mockContextMenus,
  mockAction,
};
