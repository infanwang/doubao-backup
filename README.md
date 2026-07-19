# 豆包聊天记录自动备份工具

> 7月15日豆包下线智能体，聊天记录面临丢失风险。本工具帮你自动备份所有对话。

借鉴 [DeepSeek Chat Backup](https://github.com/infanwang/deepseek-backup) 设计，支持 PII 脱敏、限速防风控、增量去重、多格式导出。

## 功能特性

### 安全特性
- **PII 脱敏**: 自动识别并脱敏手机号、邮箱、身份证等敏感信息
- **限速防风控**: 可配置请求间隔，避免被封禁
- **增量去重**: SHA-256 内容哈希，只备份有变化的对话
- **本地存储**: 所有数据不上传任何服务器

### 导出格式
| 格式 | 用途 |
|------|------|
| Markdown | 阅读、文档 |
| Word | 正式报告 |
| JSON | 程序处理 |
| JSONL | AI 训练数据 |
| HTML | 本地浏览 |

### 其他功能
- SQLite FTS5 全文搜索
- 日期/关键词筛选
- ZIP 归档
- cron 定时备份

## 快速开始

### 安装依赖
```bash
pip install selenium python-docx markdown pyyaml
```

### 首次登录
```bash
python scripts/backup.py --login
```

### 全量备份
```bash
python scripts/backup.py --full --pii
```

### 导出所有格式
```bash
python scripts/export.py -f all --zip --build-index
```

## 命令参考

### 备份
| 命令 | 说明 |
|------|------|
| `backup.py --login` | 登录 |
| `backup.py --full` | 全量备份 |
| `backup.py` | 增量备份 |
| `backup.py --pii` | PII 脱敏 |
| `backup.py --rate-limit 3.0` | 限速 |

### 导出
| 命令 | 说明 |
|------|------|
| `export.py -f all` | 导出所有格式 |
| `export.py -f jsonl` | JSONL 训练格式 |
| `export.py --build-index` | 构建搜索索引 |
| `export.py --search "关键词"` | 全文搜索 |
| `export.py --zip` | ZIP 归档 |

## 灵感来源

借鉴 [DeepSeek Chat Backup](https://github.com/infanwang/deepseek-backup) 的设计：

| 特性 | 灵感来源 |
|------|----------|
| PII 脱敏 | DataClaw |
| FTS5 搜索 | Kept |
| JSONL 格式 | DataClaw |
| 逐会话 ZIP | DeepSeek Exporter |
| 标签系统 | Chat Memo |

## License

MIT
