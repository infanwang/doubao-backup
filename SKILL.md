---
name: doubao-backup
description: Automatic backup tool for Doubao (豆包) chat history. Supports full/incremental backup, PII desensitization, rate limiting, multi-format export. Use when user mentions "backup Doubao", "export 豆包 chats", "save 豆包 conversations", "豆包聊天记录", or "备份豆包聊天记录".
license: MIT
compatibility: Requires Python 3.10+, Selenium, Chromium browser
metadata:
  author: cloudpeak
  version: 1.0.0
  category: productivity
  tags: [doubao, backup, chat-history, selenium, automation, export, bytedance]
---

# 豆包聊天记录自动备份工具

备份豆包聊天记录，支持 PII 脱敏、限速防风控、增量去重、多格式导出。

## Prerequisites

```bash
pip install selenium python-docx markdown pyyaml
```

## Quick Start

```bash
# 登录
python scripts/backup.py --login

# 全量备份（PII脱敏）
python scripts/backup.py --full --pii

# 导出所有格式
python scripts/export.py -f all --zip --build-index
```

## Security Features

### PII Desensitization

```bash
python scripts/backup.py --pii
```

自动脱敏：手机号、邮箱、身份证、银行卡、IP、API密钥

### Rate Limiting

```bash
python scripts/backup.py --rate-limit 3.0
```

### Incremental Dedup

基于 SHA-256 内容哈希，跳过未变化的对话。

## Export Formats

| Format | Command |
|--------|---------|
| Markdown | `-f markdown` |
| Word | `-f word` |
| JSON | `-f json` |
| JSONL | `-f jsonl` |
| HTML | `-f html` |

## Search

```bash
python scripts/export.py --build-index
python scripts/export.py --search "关键词"
```

## CLI Reference

```
backup.py:
  --full          Full backup
  --login         Login
  --pii           PII desensitization
  --rate-limit    Request interval (default: 2.0s)

export.py:
  --format        Export formats
  --keyword       Filter by keyword
  --search        Full-text search
  --build-index   Build search index
  --zip           ZIP archive
  --list          List conversations
  --stats         Show statistics
```
