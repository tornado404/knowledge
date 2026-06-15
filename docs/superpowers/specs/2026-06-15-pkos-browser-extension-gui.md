# PKOS Browser Extension v1 — GUI Popup 设计

> 实现状态：待实现

## 目标

点击浏览器插件图标，弹出标准 Chrome 弹出窗口（popup），包含"读取当前页面 URL"按钮，按下后显示当前链接。

## 架构：标准 Popup 方式

```
用户点击插件图标
    ↓
Chrome 自动弹出 popup.html（320x400 窗口）
    ↓
用户点击"读取当前页面 URL"
    ↓
popup.js 调用 chrome.tabs.query 获取当前 active tab URL
    ↓
渲染到 popup 页面内
```

## 文件结构

```
browser-extension/
├── manifest.json          # v3，声明 popup.html
├── popup.html             # 弹出窗口 UI
├── popup.css              # 弹出窗口样式（深色主题）
└── popup.js               # 读取当前页面 URL 并显示
```

## 组件职责

### manifest.json
- manifest_version: 3
- action.default_popup: popup.html
- permissions: `activeTab`

### popup.html
- 固定尺寸（浏览器控制，通常约 400x600 max），包含标题、按钮、URL 显示区域

### popup.css
- 深色主题，圆角，适合小窗口的紧凑布局

### popup.js
- 绑定按钮点击事件
- 调用 `chrome.tabs.query({active: true, currentWindow: true})` 获取当前 tab
- 更新 DOM 显示 URL 和标题

## 扩展点（后续迭代）

- 自动提取页面标题 + 正文内容
- 一键发送到 PKOS Ingest Pipeline (`POST /pkos/v1/ingest`)
- 支持 Markdown 预览和编辑
- 历史剪藏记录
- 身份/标签选择
