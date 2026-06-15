# PKOS Browser Extension v2 — 完整功能设计

> 实现状态：✅ 已实现

## 目标

基于已完成的 v1 GUI 基础，扩展完整的网页剪藏功能，支持三种剪藏模式、设置面板、身份/标签管理，并与 PKOS Ingest Pipeline API 对接。

## 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser Extension                         │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Popup UI (popup.html/js/css)                            ││
│  │  ├─ 主界面：模式切换 + 内容预览 + 身份/标签 + 保存按钮    ││
│  │  └─ 设置面板：服务器配置 + 默认身份 + 行为开关 + 快捷键  ││
│  └─────────────────────────────────────────────────────────┘│
│                           │                                  │
│  ┌─────────────────────────┴───────────────────────────────┐│
│  │ Background Service Worker (background.js)               ││
│  │  ├─ 监听剪切板变化                                       ││
│  │  ├─ 监听右键菜单事件                                     ││
│  │  └─ 管理扩展状态                                         ││
│  └─────────────────────────────────────────────────────────┘│
│                           │                                  │
│  ┌─────────────────────────┴───────────────────────────────┐│
│  │ Content Script (content.js)                             ││
│  │  ├─ 获取选中内容                                         ││
│  │  ├─ 提取页面正文 (Readability/Trafilatura)              ││
│  │  └─ 获取页面元信息 (title, URL, favicon)                ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
              POST /pkos/v1/ingest
              PKOS Ingest Pipeline API
```

## 三种剪藏模式

### 1. 剪切板模式（默认）

- **触发方式**：打开插件时自动读取系统剪切板内容
- **数据来源**：`navigator.clipboard.readText()` 或用户手动粘贴
- **适用场景**：用户在其他应用复制文本后，快速保存到 PKOS
- **内容格式**：纯文本或 Markdown

### 2. 选中内容模式

- **触发方式**：
  - 页面选中文本后右键菜单 → "保存到 PKOS"
  - 或在插件面板切换到"选中内容"模式
- **数据来源**：`window.getSelection().toString()`
- **适用场景**：保存页面片段、引用、关键段落
- **内容格式**：HTML 片段（保留格式）或纯文本

### 3. 全文模式

- **触发方式**：在插件面板切换到"全文"模式
- **数据来源**：
  - 使用 Readability.js 或 Trafilatura 提取正文
  - 可选保留完整 HTML
- **适用场景**：长文存档、博客文章、技术文档
- **内容格式**：Markdown（正文提取）或 HTML（完整页面）

## 文件结构

```
browser-extension/
├── manifest.json           # v3，扩展配置
├── popup.html              # 主界面 HTML
├── popup.css               # 样式（深色主题）
├── popup.js                # 主界面交互逻辑
├── background.js           # Service Worker，后台任务
├── content.js              # 内容脚本，页面交互
├── lib/
│   └── readability.js      # Mozilla Readability 库
├── settings.html           # 设置面板 HTML
├── settings.js             # 设置面板逻辑
└── icons/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```

## 组件职责

### popup.html / popup.js

**主界面状态管理**：
- 当前模式：`clipboard` | `selection` | `fullpage`
- 当前页面信息：`title`, `url`, `favicon`
- 剪藏内容：`content`（文本/HTML）
- 身份标签：`identities[]`
- 主题标签：`tags[]`

**UI 组件**：
- 模式切换栏（三个按钮）
- 标题输入框（可编辑）
- URL 显示（只读）
- 内容预览区（滚动区域）
- 身份选择器（多选）
- 标签选择器（多选 + 手动添加）
- 操作按钮：保存 / 取消

**交互逻辑**：
1. 打开时自动读取剪切板 + 当前页面信息
2. 切换模式时更新内容预览
3. 点击"保存"→ 调用 `chrome.storage.local` 获取设置 → POST `/pkos/v1/ingest`
4. 显示保存状态（成功/失败）

### settings.html / settings.js

**设置项**：

| 设置项 | 类型 | 存储键 | 说明 |
|--------|------|--------|------|
| API 地址 | string | `apiEndpoint` | PKOS 后端地址，默认 `http://localhost:8000` |
| 默认身份 | string[] | `defaultIdentities` | 每次剪藏自动附加的身份 |
| 自动提取正文 | boolean | `autoExtract` | 全文模式自动使用 Readability |
| AI 生成标签 | boolean | `aiTags` | 是否请求后端 LLM 生成标签 |
| 保存图片 | boolean | `saveImages` | 全文模式是否下载图片 |

**存储方式**：`chrome.storage.local`

### background.js

**职责**：
- 监听剪切板变化（轮询或事件）
- 注册右键菜单：`chrome.contextMenus.create()`
- 接收 content script 消息，转发到 popup
- 管理扩展全局状态

### content.js

**注入规则**：`<all_urls>`

**职责**：
- 获取选中内容：`window.getSelection()`
- 提取页面正文：调用 Readability.js
- 获取页面元信息：`document.title`, `document.URL`, `document.querySelector('link[rel="icon"]')`
- 与 background/popup 通信：`chrome.runtime.sendMessage()`

## API 对接

### 保存剪藏

```javascript
// popup.js
async function saveToPKOS(content, metadata) {
  const settings = await chrome.storage.local.get(['apiEndpoint', 'defaultIdentities']);

  const formData = new FormData();
  formData.append('source_type', metadata.sourceType); // 'browser_clip'
  formData.append('source_url', metadata.url);
  formData.append('identities', [...settings.defaultIdentities, ...metadata.identities].join(','));
  formData.append('tags', metadata.tags.join(','));
  formData.append('title', metadata.title);

  // 内容作为文件上传或直接 POST
  const blob = new Blob([content], { type: 'text/markdown' });
  formData.append('file', blob, 'clip.md');

  const response = await fetch(`${settings.apiEndpoint}/pkos/v1/ingest`, {
    method: 'POST',
    body: formData,
  });

  return response.json();
}
```

### 查询任务状态

```javascript
async function checkStatus(taskId) {
  const settings = await chrome.storage.local.get(['apiEndpoint']);
  const response = await fetch(`${settings.apiEndpoint}/pkos/v1/ingest/${taskId}`);
  return response.json();
}
```

## 身份与标签系统

### 身份（Identities）

- 预设身份列表（从后端获取或本地缓存）
- 用户可添加自定义身份
- 存储在 `chrome.storage.local` 的 `identities` 键
- 支持多选，显示为芯片样式

### 标签（Tags）

- AI 自动生成（如果启用）
- 用户手动添加
- 支持删除
- 存储在当前剪藏请求中

## 设置面板导航

点击主界面"设置"按钮 → 在同一 popup 窗口内切换到 settings.html

**实现方式**：
- 方案 A：单页面应用，popup.html 包含两个 `<div>`，通过 `display: none` 切换
- 方案 B：使用 `iframe` 加载 settings.html

推荐方案 A，减少复杂度。

## 错误处理

| 错误场景 | 处理方式 |
|----------|----------|
| API 连接失败 | 显示错误提示，提供重试按钮 |
| 剪切板为空 | 显示提示"剪切板为空，请先复制内容" |
| 未选中内容 | 在选中模式下显示"请在页面上选择内容" |
| 提取正文失败 | 退化为完整 HTML 保存 |
| 网络超时 | 显示"保存中..."状态，超时后提示重试 |

## 实现优先级

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P0 | 主界面三种模式 | 核心剪藏功能 |
| P0 | 身份/标签选择 | 与 PKOS 后端对接必需 |
| P0 | 设置面板（API 地址） | 配置后端连接 |
| P1 | 右键菜单"保存到 PKOS" | 快速剪藏入口 |
| P1 | 保存状态反馈 | 显示成功/失败/处理中 |
| P2 | 自动提取正文（Readability） | 全文模式优化 |
| P2 | AI 自动生成标签 | 后端 LLM 能力 |
| P3 | 剪切板自动检测 | 无需手动粘贴 |
| P3 | 历史记录面板 | 查看已保存内容 |

## 扩展点

- **快捷键**：通过 Chrome `commands` API 注册全局快捷键
- **同步设置**：`chrome.storage.sync` 跨设备同步配置
- **离线支持**：Service Worker 缓存剪藏内容，网络恢复后同步
- **批量导出**：一次保存多个选中片段
