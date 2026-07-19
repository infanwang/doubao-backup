#!/usr/bin/env python3
"""
Dream & Distill 自进化系统
借鉴 MiMo Code 的记忆进化机制：
- Dream: 每 7 天自动触发，合并、去重、压缩项目记忆
- Distill: 每 30 天自动触发，识别模式，固化为可复用的 skill
"""

import json
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class EvolutionTask:
    """进化任务"""
    task_type: str  # "dream" or "distill"
    last_run: datetime
    next_run: datetime
    interval_days: int
    status: str = "pending"


class DreamEngine:
    """Dream 引擎 - 合并、去重、压缩项目记忆"""
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_dir = workspace / "memory"
        self.memory_file = self.memory_dir / "MEMORY.md"
        self.history_file = self.memory_dir / "evolution_history.json"
        
    def run_dream(self) -> Dict:
        """执行 Dream - 合并、去重、压缩"""
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "dream",
            "stats": {},
        }
        
        if not self.memory_file.exists():
            result["status"] = "skipped"
            result["reason"] = "无项目记忆文件"
            return result
        
        content = self.memory_file.read_text(encoding="utf-8")
        original_size = len(content)
        
        # 1. 去重
        lines = content.split("\n")
        unique_lines = []
        seen_hashes = set()
        
        for line in lines:
            line_hash = hashlib.md5(line.strip().encode()).hexdigest()
            if line_hash not in seen_hashes and line.strip():
                seen_hashes.add(line_hash)
                unique_lines.append(line)
            elif not line.strip():
                unique_lines.append(line)  # 保留空行
        
        # 2. 压缩连续空行
        compressed_lines = []
        prev_empty = False
        for line in unique_lines:
            if not line.strip():
                if not prev_empty:
                    compressed_lines.append(line)
                prev_empty = True
            else:
                compressed_lines.append(line)
                prev_empty = False
        
        # 3. 合并相似段落
        merged_content = self._merge_similar_sections("\n".join(compressed_lines))
        
        # 4. 写回
        self.memory_file.write_text(merged_content, encoding="utf-8")
        
        new_size = len(merged_content)
        result["stats"] = {
            "original_lines": len(lines),
            "unique_lines": len(unique_lines),
            "final_lines": len(merged_content.split("\n")),
            "original_size": original_size,
            "new_size": new_size,
            "compression_ratio": f"{(1 - new_size/original_size)*100:.1f}%" if original_size > 0 else "0%",
        }
        result["status"] = "completed"
        
        # 记录历史
        self._record_evolution(result)
        
        return result
    
    def _merge_similar_sections(self, content: str) -> str:
        """合并相似的段落"""
        sections = content.split("\n## ")
        merged = [sections[0]]
        
        for section in sections[1:]:
            section_lines = section.split("\n")
            if len(section_lines) > 1:
                header = section_lines[0]
                body = "\n".join(section_lines[1:])
                
                # 检查是否与已有段落相似
                is_similar = False
                for i, existing in enumerate(merged):
                    if f"## {header}" in existing:
                        # 合并内容
                        existing_body = existing.split("\n", 1)[1] if "\n" in existing else ""
                        if body.strip() not in existing_body:
                            merged[i] = f"## {header}\n{existing_body}\n{body}"
                        is_similar = True
                        break
                
                if not is_similar:
                    merged.append(f"## {section}")
        
        return "\n".join(merged)
    
    def _record_evolution(self, result: Dict):
        """记录进化历史"""
        history = []
        if self.history_file.exists():
            try:
                history = json.loads(self.history_file.read_text(encoding="utf-8"))
            except Exception:
                history = []
        
        history.append(result)
        
        # 只保留最近 30 条记录
        history = history[-30:]
        
        self.history_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


class DistillEngine:
    """Distill 引擎 - 识别模式，固化为可复用的 skill"""
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_dir = workspace / "memory"
        self.skills_dir = workspace / ".mimocode" / "skills"
        self.history_file = self.memory_dir / "evolution_history.json"
    
    def run_distill(self) -> Dict:
        """执行 Distill - 识别模式，创建 skill"""
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "distill",
            "skills_created": [],
            "patterns_found": [],
        }
        
        # 1. 分析历史记录，识别模式
        patterns = self._identify_patterns()
        result["patterns_found"] = patterns
        
        # 2. 为每个模式创建 skill
        for pattern in patterns:
            skill_name = self._generate_skill_name(pattern)
            skill_content = self._generate_skill_content(pattern)
            
            if skill_name and skill_content:
                self._create_skill(skill_name, f"从使用模式中自动提取: {pattern['description']}", skill_content)
                result["skills_created"].append(skill_name)
        
        result["status"] = "completed"
        self._record_evolution(result)
        
        return result
    
    def _identify_patterns(self) -> List[Dict]:
        """识别重复模式"""
        patterns = []
        
        # 读取项目记忆
        memory_file = self.memory_dir / "MEMORY.md"
        if not memory_file.exists():
            return patterns
        
        content = memory_file.read_text(encoding="utf-8")
        
        # 简单的模式识别：查找重复的操作序列
        # 在实际 MiMo Code 中，这里会使用更复杂的分析
        
        # 示例：查找常见的工具调用模式
        tool_patterns = {
            "backup": ["backup", "备份", "导出"],
            "search": ["搜索", "查找", "查询"],
            "export": ["导出", "export", "格式"],
            "test": ["测试", "test", "验证"],
        }
        
        for pattern_name, keywords in tool_patterns.items():
            keyword_count = sum(1 for kw in keywords if kw in content)
            if keyword_count >= 2:
                patterns.append({
                    "type": "tool_usage",
                    "name": pattern_name,
                    "description": f"频繁使用 {pattern_name} 相关操作",
                    "keywords": keywords,
                    "frequency": keyword_count,
                })
        
        # 查找时间模式
        time_patterns = ["每天", "每周", "定期", "自动"]
        for tp in time_patterns:
            if tp in content:
                patterns.append({
                    "type": "schedule",
                    "name": f"定期{tp}",
                    "description": f"用户倾向于 {tp} 执行操作",
                    "keywords": [tp],
                })
        
        return patterns[:5]  # 最多返回 5 个模式
    
    def _generate_skill_name(self, pattern: Dict) -> str:
        """生成技能名称"""
        return f"auto-{pattern['name']}"
    
    def _generate_skill_content(self, pattern: Dict) -> str:
        """生成技能内容"""
        return f"""## {pattern['description']}

### 自动识别的操作模式
- 类型: {pattern['type']}
- 关键词: {', '.join(pattern.get('keywords', []))}
- 频率: {pattern.get('frequency', 'N/A')}

### 建议的操作流程
1. 确认操作目标
2. 执行相关操作
3. 验证结果

### 注意事项
- 此技能由系统自动创建
- 基于用户的使用模式分析
"""
    
    def _create_skill(self, name: str, description: str, content: str):
        """创建技能文件"""
        skill_dir = self.skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        skill_file = skill_dir / "SKILL.md"
        skill_content = f"""---
name: {name}
description: {description}
---

{content}
"""
        skill_file.write_text(skill_content, encoding="utf-8")
    
    def _record_evolution(self, result: Dict):
        """记录进化历史"""
        history = []
        if self.history_file.exists():
            try:
                history = json.loads(self.history_file.read_text(encoding="utf-8"))
            except Exception:
                history = []
        
        history.append(result)
        history = history[-30:]
        
        self.history_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


class EvolutionManager:
    """进化管理器 - 协调 Dream 和 Distill"""
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.dream_engine = DreamEngine(workspace)
        self.distill_engine = DistillEngine(workspace)
        self.tasks_file = workspace / ".mimocode" / "evolution_tasks.json"
        
        self.tasks = self._load_tasks()
    
    def _load_tasks(self) -> List[EvolutionTask]:
        """加载进化任务"""
        if not self.tasks_file.exists():
            return [
                EvolutionTask("dream", datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(days=7), 7),
                EvolutionTask("distill", datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(days=30), 30),
            ]
        
        try:
            data = json.loads(self.tasks_file.read_text(encoding="utf-8"))
            return [
                EvolutionTask(
                    task_type=t["task_type"],
                    last_run=datetime.fromisoformat(t["last_run"]),
                    next_run=datetime.fromisoformat(t["next_run"]),
                    interval_days=t["interval_days"],
                )
                for t in data
            ]
        except Exception:
            return []
    
    def _save_tasks(self):
        """保存进化任务"""
        self.tasks_file.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {
                "task_type": t.task_type,
                "last_run": t.last_run.isoformat(),
                "next_run": t.next_run.isoformat(),
                "interval_days": t.interval_days,
            }
            for t in self.tasks
        ]
        self.tasks_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    def check_and_run(self) -> List[Dict]:
        """检查并执行到期的进化任务"""
        results = []
        now = datetime.now(timezone.utc)
        
        for task in self.tasks:
            if now >= task.next_run:
                if task.task_type == "dream":
                    result = self.dream_engine.run_dream()
                    results.append(result)
                elif task.task_type == "distill":
                    result = self.distill_engine.run_distill()
                    results.append(result)
                
                task.last_run = now
                task.next_run = now + timedelta(days=task.interval_days)
        
        self._save_tasks()
        return results
    
    def force_dream(self) -> Dict:
        """强制执行 Dream"""
        return self.dream_engine.run_dream()
    
    def force_distill(self) -> Dict:
        """强制执行 Distill"""
        return self.distill_engine.run_distill()
    
    def get_status(self) -> Dict:
        """获取进化状态"""
        now = datetime.now(timezone.utc)
        status = {}
        
        for task in self.tasks:
            status[task.task_type] = {
                "last_run": task.last_run.isoformat(),
                "next_run": task.next_run.isoformat(),
                "days_until_next": (task.next_run - now).days,
            }
        
        return status
