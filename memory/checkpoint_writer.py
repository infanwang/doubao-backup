#!/usr/bin/env python3
"""
Checkpoint-Writer 记忆系统
借鉴 MiMo Code 的四层记忆架构：
- Session Memory (checkpoint.md) - 当前会话状态
- Project Memory (MEMORY.md) - 跨会话项目知识
- Global Memory - 用户级偏好
- History - 完整原始记录
"""

import json
import sqlite3
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any


class CheckpointWriter:
    """Checkpoint 写入器 - 独立于主 Agent 的状态提取者"""
    
    # checkpoint 的 11 个结构化字段
    CHECKPOINT_FIELDS = [
        "current_intent",      # 当前意图
        "next_action",         # 下一步动作
        "constraints",         # 工作约束
        "task_tree",           # 任务树
        "current_work",        # 当前工作
        "files_involved",      # 涉及文件
        "cross_task_findings", # 跨任务发现
        "errors_and_fixes",    # 错误与修复
        "runtime_state",       # 运行时状态
        "design_decisions",    # 设计决策
        "misc_notes",          # 杂项笔记
    ]
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_dir = workspace / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        self.session_file = self.memory_dir / "checkpoint.md"
        self.project_file = self.memory_dir / "MEMORY.md"
        self.global_file = Path.home() / ".config" / "mimocode-core" / "memory" / "GLOBAL.md"
        self.history_db = self.memory_dir / "history.db"
        self.notes_file = self.memory_dir / "notes.md"
        
        self._init_history_db()
    
    def _init_history_db(self):
        """初始化历史记录数据库"""
        conn = sqlite3.connect(str(self.history_db))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_name TEXT,
                tool_input TEXT,
                tool_output TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def write_checkpoint(self, state: Dict[str, Any]):
        """写入 session checkpoint"""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        lines = [f"# Session Checkpoint\n", f"Updated: {timestamp}\n"]
        
        for field in self.CHECKPOINT_FIELDS:
            value = state.get(field, "")
            lines.append(f"## {field.replace('_', ' ').title()}\n")
            lines.append(f"{value}\n")
        
        with open(self.session_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        return self.session_file
    
    def read_checkpoint(self) -> Dict[str, str]:
        """读取 session checkpoint"""
        if not self.session_file.exists():
            return {field: "" for field in self.CHECKPOINT_FIELDS}
        
        content = self.session_file.read_text(encoding="utf-8")
        state = {}
        current_field = None
        current_value = []
        
        for line in content.split("\n"):
            if line.startswith("## "):
                if current_field:
                    state[current_field] = "\n".join(current_value).strip()
                field_name = line[3:].strip().lower().replace(" ", "_")
                if field_name in self.CHECKPOINT_FIELDS:
                    current_field = field_name
                    current_value = []
                else:
                    current_field = None
            elif current_field:
                current_value.append(line)
        
        if current_field:
            state[current_field] = "\n".join(current_value).strip()
        
        return state
    
    def write_project_memory(self, content: str):
        """写入项目记忆"""
        with open(self.project_file, "w", encoding="utf-8") as f:
            f.write(content)
    
    def append_project_memory(self, content: str):
        """追加到项目记忆"""
        existing = ""
        if self.project_file.exists():
            existing = self.project_file.read_text(encoding="utf-8")
        
        with open(self.project_file, "w", encoding="utf-8") as f:
            f.write(existing + "\n" + content)
    
    def read_project_memory(self) -> str:
        """读取项目记忆"""
        if self.project_file.exists():
            return self.project_file.read_text(encoding="utf-8")
        return ""
    
    def write_global_memory(self, content: str):
        """写入全局记忆"""
        self.global_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.global_file, "w", encoding="utf-8") as f:
            f.write(content)
    
    def read_global_memory(self) -> str:
        """读取全局记忆"""
        if self.global_file.exists():
            return self.global_file.read_text(encoding="utf-8")
        return ""
    
    def append_notes(self, note: str):
        """追加笔记到 scratchpad"""
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = f"\n## [{timestamp}]\n{note}\n"
        
        with open(self.notes_file, "a", encoding="utf-8") as f:
            f.write(entry)
    
    def read_notes(self) -> str:
        """读取笔记"""
        if self.notes_file.exists():
            return self.notes_file.read_text(encoding="utf-8")
        return ""
    
    def clear_notes(self):
        """清空笔记"""
        if self.notes_file.exists():
            self.notes_file.write_text("")
    
    def record_history(self, role: str, content: str, tool_name: str = None, 
                       tool_input: str = None, tool_output: str = None):
        """记录历史"""
        conn = sqlite3.connect(str(self.history_db))
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO history (timestamp, role, content, tool_name, tool_input, tool_output)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (datetime.now(timezone.utc).isoformat(), role, content, tool_name, tool_input, tool_output))
        conn.commit()
        conn.close()
    
    def search_history(self, query: str, limit: int = 10) -> List[Dict]:
        """搜索历史记录"""
        conn = sqlite3.connect(str(self.history_db))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, role, content FROM history 
            WHERE content LIKE ? 
            ORDER BY id DESC LIMIT ?
        """, (f"%{query}%", limit))
        
        results = [{"timestamp": r[0], "role": r[1], "content": r[2]} for r in cursor.fetchall()]
        conn.close()
        return results
    
    def rebuild_context(self) -> str:
        """重建上下文 - 用于 session 恢复"""
        sections = []
        
        # 1. 任务清单（从 checkpoint）
        checkpoint = self.read_checkpoint()
        if checkpoint.get("task_tree"):
            sections.append(f"## 任务清单\n{checkpoint['task_tree']}")
        
        # 2. Session checkpoint
        if self.session_file.exists():
            sections.append(f"## Session 状态\n{self.session_file.read_text(encoding='utf-8')}")
        
        # 3. 项目记忆
        project_memory = self.read_project_memory()
        if project_memory:
            sections.append(f"## 项目记忆\n{project_memory}")
        
        # 4. 全局记忆
        global_memory = self.read_global_memory()
        if global_memory:
            sections.append(f"## 全局记忆\n{global_memory}")
        
        # 5. Notes
        notes = self.read_notes()
        if notes:
            sections.append(f"## 临时笔记\n{notes}")
        
        return "\n\n---\n\n".join(sections)


class MemoryManager:
    """记忆管理器 - 负责记忆的提炼和进化"""
    
    def __init__(self, checkpoint_writer: CheckpointWriter):
        self.writer = checkpoint_writer
    
    def extract_insights(self, session_data: Dict) -> List[str]:
        """从 session 数据中提取洞察"""
        insights = []
        
        # 提取设计决策
        if session_data.get("design_decisions"):
            insights.append(f"设计决策: {session_data['design_decisions']}")
        
        # 提取跨任务发现
        if session_data.get("cross_task_findings"):
            insights.append(f"发现: {session_data['cross_task_findings']}")
        
        # 提取错误与修复
        if session_data.get("errors_and_fixes"):
            insights.append(f"修复: {session_data['errors_and_fixes']}")
        
        return insights
    
    def should_promote_to_project(self, insight: str) -> bool:
        """判断是否应该提升到项目记忆"""
        # 简单启发式：包含关键词的洞察应该提升
        keywords = ["架构", "设计", "规则", "约定", "最佳实践", "注意事项"]
        return any(kw in insight for kw in keywords)
    
    def promote_to_project_memory(self, insights: List[str]):
        """将洞察提升到项目记忆"""
        for insight in insights:
            if self.should_promote_to_project_memory(insight):
                self.writer.append_project_memory(f"\n- {insight}")
    
    def dream(self):
        """Dream - 合并、去重、压缩项目记忆"""
        content = self.writer.read_project_memory()
        if not content:
            return
        
        # 简单的去重和压缩
        lines = content.split("\n")
        unique_lines = []
        seen = set()
        
        for line in lines:
            line_hash = hashlib.md5(line.strip().encode()).hexdigest()
            if line_hash not in seen and line.strip():
                seen.add(line_hash)
                unique_lines.append(line)
        
        compressed = "\n".join(unique_lines)
        self.writer.write_project_memory(compressed)
    
    def distill(self):
        """Distill - 识别模式，固化为可复用的 skill"""
        # 读取历史记录
        conn = sqlite3.connect(str(self.writer.history_db))
        cursor = conn.cursor()
        cursor.execute("SELECT content FROM history ORDER BY id DESC LIMIT 100")
        recent_content = [r[0] for r in cursor.fetchall()]
        conn.close()
        
        # 识别重复模式（简单的关键词频率分析）
        word_freq = {}
        for content in recent_content:
            words = content.split()
            for word in words:
                if len(word) > 3:
                    word_freq[word] = word_freq.get(word, 0) + 1
        
        # 找出高频词
        common_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
        
        if common_words:
            pattern = f"常见关键词: {', '.join([w[0] for w in common_words])}"
            self.writer.append_project_memory(f"\n## 自动识别的模式\n{pattern}")
