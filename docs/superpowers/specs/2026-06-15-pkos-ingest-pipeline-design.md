# PKOS Ingest Pipeline 设计文档

> **实现状态**: MVP 阶段 12/12 任务已全部完成（2026-06-15）。详见 [`docs/superpowers/plans/2026-06-15-pkos-ingest-pipeline.md`](../plans/2026-06-15-pkos-ingest-pipeline.md)。

## 1. 背景与目标

PKOS（Personal Knowledge Operating System）是一个长期运行的个人知识操作系统。本设计聚焦于其 MVP 阶段的核心子系统——**Ingest Pipeline**：负责将多模态原始素材（PDF、图片、网页、文本等）自动转化为结构化的 Markdown 知识文档，归档至 Vault，并向量化索引以支持后续检索与问答。

### 设计原则
- Markdown 是一等公民，所有内容最终形态为 Markdown
- 身份标签化（identities），主题目录化
- 复用现有基础设施，避免过度架构
- 异步、可重试、可观测

---

## 2. 架构概览 ✅ 已实现

```
┌─────────────────────────────────────────────────────────────────────┐
│                         API / 多端上传                                │
│              POST /pkos/v1/ingest (multipart/form-data)               │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Inbox 临时缓冲区                                   │
│              kgsrc/pkos/inbox/{task_id}/原始文件                      │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    IngestPipeline 状态机                              │
│  REGISTERED → PARSING → UNDERSTANDING → CLASSIFYING → ARCHIVING     │
│                                                    ↓                 │
│                                                 INDEXED              │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Vault 结构化归档                                   │
│         kgsrc/pkos/vault/{主题}/YYYY-MM-DD-{slug}.md                 │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Milvus 向量索引（增量更新）                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Vault 目录结构与 Markdown 格式 ✅ 已实现

### 3.1 目录结构

Vault 采用**主题聚类目录 + 身份标签**的混合组织方式：

```
kgsrc/pkos/vault/
├── 人工智能/
│   ├── 2026-06-15-RAG-优化实践.md
│   └── 2026-06-10-向量数据库选型.md
├── 教育/
│   └── 2026-06-15-用Python教孩子数学.md
├── 骑行/
│   └── 2026-06-12-碳纤维轮组维护指南.md
├── 项目规划/
│   └── 2026-06-14-PKOS-MVP-路线图.md
└── 未分类/
    └── 2026-06-15-未知内容.md
```

- **一级目录**：主题聚类（由 LLM 自动推断，如"人工智能"、"教育"、"骑行"）
  - 主题目录不存在时自动创建
  - LLM 推断的主题名会经过 slug 化处理（去除特殊字符、统一空格为`-`）
- **文件名**：`YYYY-MM-DD-{标题slug}.md`
- **身份归属**：不体现在目录层级，而是文档 YAML frontmatter 中的 `identities` 字段（支持多选）

### 3.2 Markdown 标准格式

```markdown
---
title: "用 Python 教孩子数学"
date: 2026-06-15T10:30:00+08:00
source_type: "browser_clip"
source_url: "https://example.com/original"
identities: [程序员, 好爸爸]
tags: [python, 教育, 数学启蒙, 亲子]
summary: "通过编写简单的Python脚本，将抽象的数学概念转化为可视化的互动程序，让孩子在玩耍中学习数学思维..."
---

# 用 Python 教孩子数学

> **来源**：[原文链接](https://example.com/original)
> **归档时间**：2026-06-15

（正文内容，清洗后的纯文本或 Markdown）

## 关键要点

- 要点一
- 要点二

---
*本内容由 PKOS Ingest Pipeline 自动归档*
```

### 3.3 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | string | 文档标题，由 LLM 提取或用户指定 |
| `date` | ISO 8601 | 归档时间（处理完成时间） |
| `source_type` | enum | `browser_clip` / `pdf` / `image` / `api` / `screenshot` |
| `source_url` | string? | 原始来源 URL（如有） |
| `identities` | string[] | 身份标签，如 `["程序员", "好爸爸"]` |
| `tags` | string[] | 主题标签，如 `["python", "教育"]` |
| `summary` | string | LLM 生成的内容摘要 |

---

## 4. IngestPipeline 状态机 ✅ 已实现

### 4.1 状态定义

每个文件被注册为一个 `IngestTask`，经过以下阶段：

```
REGISTERED ──► PARSING ──► UNDERSTANDING ──► CLASSIFYING ──► ARCHIVING ──► INDEXED
                  │              │                │              │
                  ▼              ▼                ▼              ▼
               FAILED        FAILED           FAILED        FAILED
                  │              │                │              │
                  └──────────────┴────────────────┴──────────────┘
                                 │
                                 ▼
                          RETRY (最多 3 次)
                                 │
                                 ▼
                          DEAD_LETTER
```

### 4.2 各阶段职责

| 阶段 | 输入 | 输出 | 失败策略 |
|------|------|------|---------|
| `REGISTERED` | API 请求 / 文件监控事件 | 任务对象，原始文件存入 Inbox | — |
| `PARSING` | 原始文件（PDF/图片/网页/文本） | 纯文本内容 + 提取的媒体文件（图片存 MinIO） | 重试，退化为文件名作为内容 |
| `UNDERSTANDING` | 纯文本 | 结构化数据：`title`, `summary`, `entities`, `source_url` | 重试，退化为前 100 字作为摘要 |
| `CLASSIFYING` | 结构化数据 | 主题目录路径 + `identities[]` + `tags[]` | 重试，退化为 `未分类/` + 空标签 |
| `ARCHIVING` | 完整结构化数据 | 写入 Vault 的标准 Markdown 文件 | **不可重试**，失败即进入死信队列 |
| `INDEXED` | Markdown 文件路径 | Milvus 向量索引更新 | 异步后台重试，不影响主流程 |

### 4.3 重试策略

- PARSING / UNDERSTANDING / CLASSIFYING 阶段失败时，指数退避重试（1s, 3s, 9s），最多 3 次
- ARCHIVING 阶段为幂等写入（同一 task_id 不会重复写入），失败直接进入死信队列
- INDEXED 阶段由独立的后台任务消费，失败可无限重试

---

## 5. 多模态解析 ⚡ 部分实现（MVP 范围已落地）

### 5.1 支持的内容类型

| 来源类型 | MVP 支持 | 处理方式 |
|---------|---------|---------|
| 文本 / Markdown | ✅ | 直接读取，清洗现有 frontmatter |
| PDF | ✅ | `unstructured` 库提取文本 + 图片引用 |
| 图片（截图/照片） | ✅ | 上传至 MinIO → LLM 视觉模型生成描述 → Markdown 中 `![desc](minio_url)` |
| 网页剪藏 | ✅ | 后端下载 URL → `readability-lxml` / `trafilatura` 提取正文 |
| 视频 | ⏸️ 二期 | 提取音频 → Whisper 转录 → LLM 摘要 |
| 聊天记录 | ⏸️ 二期 | 结构化 JSON 导入专用格式 |
| 代码仓库同步 | ⏸️ 二期 | 监听 Git 事件，提取 README 和关键代码注释 |

### 5.2 图片处理规范

- 图片文件统一上传至 MinIO（或本地对象存储目录）
- LLM（视觉模型）生成图片内容描述
- Markdown 中引用格式：`![AI描述：一张展示Python代码和数学公式的截图](minio://bucket/path/to/image.png)`
- 原始图片保留，不压缩（存储成本由用户控制）

---

## 6. API 设计 ✅ 已实现

### 6.1 摄入任务

```http
POST /pkos/v1/ingest
Content-Type: multipart/form-data

Body:
  - file: <二进制文件>
  - source_type: "browser_clip" | "pdf" | "image" | "screenshot" | "api"
  - source_url?: <可选，原始链接>
  - identities?: ["程序员", ...]  ← 用户显式指定时跳过 LLM 推断

Response: 201 Created
{
  "task_id": "uuid",
  "status": "REGISTERED",
  "created_at": "2026-06-15T10:30:00+08:00"
}
```

### 6.2 查询任务状态

```http
GET /pkos/v1/ingest/{task_id}

Response: 200 OK
{
  "task_id": "uuid",
  "status": "CLASSIFYING",
  "stage": "CLASSIFYING",
  "error": null,
  "vault_path": null,
  "created_at": "2026-06-15T10:30:00+08:00",
  "updated_at": "2026-06-15T10:31:15+08:00"
}
```

### 6.3 Vault 文档搜索

复用现有 `/chat` 的 RAG 能力，限定搜索范围为 Vault 目录：

```http
GET /pkos/v1/vault/search?q=向量数据库选型

Response: 200 OK
{
  "results": [
    {
      "path": "人工智能/2026-06-10-向量数据库选型.md",
      "title": "向量数据库选型",
      "summary": "...",
      "score": 0.92
    }
  ]
}
```

### 6.4 Vault 文档筛选

```http
GET /pkos/v1/vault/documents?identity=程序员&tag=python

Response: 200 OK
{
  "documents": [
    {
      "path": "教育/2026-06-15-用Python教孩子数学.md",
      "title": "用 Python 教孩子数学",
      "identities": ["程序员", "好爸爸"],
      "tags": ["python", "教育"]
    }
  ]
}
```

---

## 7. 与现有代码的复用关系 ✅ 已实现

| PKOS 新模块 | 复用现有模块 | 说明 |
|------------|------------|------|
| `IngestTask` 模型 | — | 新建，适配文件处理状态机 |
| `IngestPipeline` | `multi_agent/MessageBus` | 复用消息总线做阶段间事件通知 |
| `IngestTaskStore` | `session_persistence.py` | 复用 `SessionPersistence` 的存储模式（JSON 文件 + 过期清理），新建 `IngestTaskStore` 类持久化 Ingest 任务状态 |
| `VaultVectorStore` | `vectorstore.py` | 复用 `MilvusVectorStore`，新增"增量索引 Vault 目录"接口 |
| `DocumentParser` | `loader.py` + `splitter.py` | 复用 Markdown 加载和分割逻辑，扩展 PDF/图片/网页解析 |
| `LLMClassifier` | `chain.py` | 复用 `ChatAnthropic` 调用模式，封装分类/摘要/实体提取 Prompt |
| `PKOSAPI` | `chat.py` | FastAPI 路由扩展，复用现有中间件和启动逻辑 |

**不复用的组件**：`OrchestratorAgent` 和 `Worker` 体系。Ingest Pipeline 是单文件顺序处理，不需要任务分解和多 Worker 并行协调。

---

## 8. 错误处理与可观测性 ⚡ 部分实现（DLQ、Metrics 已落地；结构化日志待补充）

### 8.1 死信队列（Dead Letter）

- ARCHIVING 阶段失败后不可重试，原始文件 + 错误日志 + 中间结果存入 `kgsrc/pkos/dead_letter/{task_id}/`
- 支持通过 API 重新提交：`POST /pkos/v1/ingest/{task_id}/retry`
- 人工介入后可手动修复并重新触发

### 8.2 监控指标

暴露 Prometheus 风格指标（或 JSON 端点）：

```
GET /pkos/v1/metrics

{
  "ingest_tasks_total": 1523,
  "ingest_tasks_by_status": {
    "REGISTERED": 2,
    "PARSING": 1,
    "UNDERSTANDING": 3,
    "CLASSIFYING": 0,
    "ARCHIVING": 1,
    "INDEXED": 1510,
    "FAILED": 3,
    "DEAD_LETTER": 3
  },
  "stage_duration_seconds": {
    "PARSING": { "p50": 0.5, "p99": 3.2 },
    "UNDERSTANDING": { "p50": 2.1, "p99": 8.5 },
    "CLASSIFYING": { "p50": 1.8, "p99": 5.4 }
  }
}
```

### 8.3 日志

- 每个 `task_id` 有独立的结构化日志链路
- 日志包含：`task_id`, `stage`, `source_type`, `duration_ms`, `error?`
- 日志目录：`kgsrc/pkos/logs/ingest/YYYY-MM-DD/{task_id}.log`

---

## 9. 安全与边界 ⚡ 部分实现（文件大小限制、图片白名单已落地；PDF 隔离进程待补充）

- Inbox 目录只接受通过 API 写入的文件，不直接暴露文件系统写入接口（防止恶意文件上传）
- 文件大小限制：单次上传不超过 50MB
- 图片文件类型白名单：`png`, `jpg`, `jpeg`, `webp`, `gif`
- PDF 解析在独立进程中执行（`unstructured` 的隔离性），防止恶意 PDF 攻击
- LLM 调用有 Token 预算限制，超长文本自动截断并告警

---

## 10. 二期规划

以下功能不在 MVP 范围内，但架构预留扩展点：

| 功能 | 说明 | 扩展点 | 优先级 |
|------|------|--------|--------|
| 视频处理 | 提取音频 → Whisper 转录 → LLM 摘要 | 新增 `VideoParser` Worker | P2 |
| 聊天记录导入 | 微信/飞书/Discord 结构化导出 | 新增 `ChatLogParser` | P2 |
| 代码仓库同步 | 监听 Git Webhook，提取关键文档 | 新增 `GitSyncParser` | P3 |
| 知识图谱 | 跨文档实体关联，双向链接自动补全 | Vault 扫描 + 实体提取 Pipeline | P3 |
| 过期知识检测 | 基于时间衰减和更新频率的知识健康度评分 | 定时任务扫描 Vault frontmatter | P3 |
| 浏览器插件 | Chrome/Firefox 剪藏插件 | 调用现有 `/pkos/v1/ingest` API | P1 |
| 多端 App | 手机拍照/截图直接上传 | 同上 | P2 |
| 结构化日志 | 每 task_id 独立日志链路 | `kgsrc/pkos/logger.py` | P1 |
| MinIO 对象存储 | 替换本地图片存储为 MinIO/S3 | `ImageParser` 改造 | P2 |

---

---

## 12. 下一步执行计划

MVP 阶段已完整落地（12/12 任务，对应 12 个 commit）。Phase 1 验证已完成，发现并修复了以下问题：

### Phase 1 验证结果（2026-06-15）

| 验证项 | 结果 | 发现的问题 |
|--------|------|-----------|
| 全量测试运行 | ✅ 46/46 通过 | 需要 `PYTHONPATH` 包含项目根目录 |
| FastAPI 集成 | ✅ 所有端点正常 | 相对导入路径问题（已修复） |
| CLI 端到端 | ✅ 链路打通 | 导入路径 + fallback title 格式 + index 状态标记（已修复） |

### 已修复的 Bug

1. **Import 路径错误** — `main.py` 和 `kgsrc/pkos/` 模块使用 `knowledge_vector.pkos` 或 `..knowledge_vector` 相对导入，统一改为 `kgsrc.pkos` / `knowledge_vector` 绝对导入
2. **Pipeline index 状态标记** — `index_document()` 返回 False 时仍标记为 INDEXED，现已检查返回值
3. **Classifier fallback title 污染** — fallback 时 title 包含 `#` Markdown 标记，现已清洗
4. **CLI 缺少 `--task-id` 参数** — `status` 子命令需要 task_id 但 parser 未定义，已补充

### Phase 2: 高优先级扩展（P1）

5. **浏览器剪藏插件 Spec** — 设计 Chrome Extension / Userscript，调用现有 `POST /pkos/v1/ingest` API，支持一键剪藏当前网页
   - 输出: `docs/superpowers/specs/2026-06-xx-pkos-browser-clip.md`
6. **结构化日志** — 实现每 `task_id` 独立的日志链路，输出到 `kgsrc/pkos/logs/ingest/YYYY-MM-DD/{task_id}.log`
   - 文件: `kgsrc/pkos/logger.py`
   - 格式: JSON Lines，字段 `task_id`, `stage`, `duration_ms`, `error`

### Phase 3: 中优先级扩展（P2）

7. **MinIO 图片存储** — 替换 `ImageParser` 本地存储为 MinIO/S3 兼容对象存储
8. **视频处理** — Whisper 转录 + LLM 摘要流水线
9. **手机端上传** — 基于现有 API 的简单 Web 上传页面

### 待创建 Spec 清单

| Spec 文件名 | 目标 | 预计工期 |
|-----------|------|---------|
| `2026-06-xx-pkos-browser-clip.md` | 浏览器剪藏插件设计 | 1 天 |
| `2026-06-xx-pkos-structured-logging.md` | 结构化日志与可观测性 | 0.5 天 |
| `2026-06-xx-pkos-minio-storage.md` | MinIO 对象存储集成 | 0.5 天 |

---

## 11. 关键决策记录

1. **身份标签化而非目录化**：身份是多维属性，目录是单维结构。用 YAML frontmatter 的 `identities` 字段支持多选，目录按主题聚类，兼顾 Obsidian 文件树浏览和灵活筛选。
2. **不复用 Orchestrator-Worker 架构**：现有 Multi-Agent 系统是为"用户提问 → 多 Worker 并行检索 → 合并回答"设计的。Ingest Pipeline 是"单文件顺序经过 5 个处理阶段"，架构不匹配，强行套用会产生不必要的复杂度。
3. **图片存 MinIO、Markdown 引用**：MinIO 作为对象存储与 Vault 解耦，支持未来替换为 S3/OSS；Markdown 中保留 AI 描述文本，即使图片丢失，内容仍可理解。
4. **ARCHIVING 阶段失败即死信**：写入磁盘是幂等操作（同一 task_id 不会重复写入），失败原因通常是磁盘满或权限问题，重试无法解决，直接进入死信队列等待人工介入。
