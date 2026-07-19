#!/usr/bin/env python3
"""
Skills 技能系统
借鉴 MiMo Code 的技能发现和加载机制：
- 技能通过 SKILL.md 文件定义
- 支持 frontmatter 元数据
- 按需加载，减少 token 消耗
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional
import re


class Skill:
    """技能定义"""
    
    def __init__(self, name: str, description: str, content: str, 
                 path: Path = None, hidden: bool = False):
        self.name = name
        self.description = description
        self.content = content
        self.path = path
        self.hidden = hidden
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "hidden": self.hidden,
            "path": str(self.path) if self.path else None
        }


class SkillManager:
    """技能管理器 - 负责技能的发现、加载和执行"""
    
    def __init__(self, workspace: Path = None):
        self.workspace = workspace or Path.cwd()
        self.skills: Dict[str, Skill] = {}
        self.skill_dirs = self._find_skill_dirs()
        self._discover_skills()
    
    def _find_skill_dirs(self) -> List[Path]:
        """查找技能目录"""
        dirs = []
        
        # 项目级技能目录
        project_dirs = [
            self.workspace / ".mimocode" / "skills",
            self.workspace / ".claude" / "skills",
            self.workspace / ".agents" / "skills",
        ]
        dirs.extend([d for d in project_dirs if d.exists()])
        
        # 全局技能目录
        global_dirs = [
            Path.home() / ".config" / "mimocode-core" / "skills",
            Path.home() / ".claude" / "skills",
        ]
        dirs.extend([d for d in global_dirs if d.exists()])
        
        return dirs
    
    def _discover_skills(self):
        """发现所有技能"""
        for skill_dir in self.skill_dirs:
            for skill_file in skill_dir.rglob("SKILL.md"):
                try:
                    skill = self._parse_skill_file(skill_file)
                    if skill:
                        self.skills[skill.name] = skill
                except Exception as e:
                    print(f"[!] 加载技能失败 {skill_file}: {e}")
    
    def _parse_skill_file(self, path: Path) -> Optional[Skill]:
        """解析 SKILL.md 文件"""
        content = path.read_text(encoding="utf-8")
        
        # 解析 frontmatter
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
        if not match:
            return None
        
        frontmatter_str = match.group(1)
        body = match.group(2).strip()
        
        try:
            frontmatter = yaml.safe_load(frontmatter_str)
        except yaml.YAMLError:
            return None
        
        name = frontmatter.get("name")
        description = frontmatter.get("description", "")
        hidden = frontmatter.get("hidden", False)
        
        if not name:
            return None
        
        return Skill(
            name=name,
            description=description,
            content=body,
            path=path,
            hidden=hidden
        )
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """获取技能"""
        return self.skills.get(name)
    
    def list_skills(self, include_hidden: bool = False) -> List[Skill]:
        """列出所有技能"""
        skills = list(self.skills.values())
        if not include_hidden:
            skills = [s for s in skills if not s.hidden]
        return skills
    
    def load_skill(self, name: str) -> Optional[str]:
        """加载技能内容"""
        skill = self.get_skill(name)
        if skill:
            return skill.content
        return None
    
    def register_skill(self, skill: Skill):
        """注册新技能"""
        self.skills[skill.name] = skill
    
    def create_skill(self, name: str, description: str, content: str, 
                     directory: Path = None) -> Skill:
        """创建新技能"""
        if directory is None:
            directory = self.workspace / ".mimocode" / "skills" / name
        
        directory.mkdir(parents=True, exist_ok=True)
        skill_file = directory / "SKILL.md"
        
        skill_content = f"""---
name: {name}
description: {description}
---

{content}
"""
        skill_file.write_text(skill_content, encoding="utf-8")
        
        skill = Skill(name=name, description=description, content=content, path=skill_file)
        self.register_skill(skill)
        
        return skill
    
    def get_available_skills_xml(self) -> str:
        """生成可用技能的 XML 列表（供 Agent 使用）"""
        skills = self.list_skills()
        if not skills:
            return "<available_skills></available_skills>"
        
        items = []
        for skill in skills:
            items.append(f"""  <skill>
    <name>{skill.name}</name>
    <description>{skill.description}</description>
  </skill>""")
        
        return f"<available_skills>\n{''.join(items)}\n</available_skills>"


# ========== 内置技能 ==========

BUILTIN_SKILLS = {
    "backup-workflow": Skill(
        name="backup-workflow",
        description="完整的备份工作流：登录 → 抓取 → 脱敏 → 导出",
        content="""## 备份工作流

### 步骤 1: 登录
```bash
python scripts/backup.py --login
```

### 步骤 2: 全量备份
```bash
python scripts/backup.py --full --pii --rate-limit 2.0
```

### 步骤 3: 导出
```bash
python scripts/export.py -f all --zip --build-index
```

### 注意事项
- 首次运行需要手动登录
- PII 脱敏会自动处理敏感信息
- 限速默认 2 秒/请求
"""
    ),
    
    "tdd-workflow": Skill(
        name="tdd-workflow",
        description="测试驱动开发工作流",
        content="""## TDD 工作流

### 循环
1. **Red**: 编写失败的测试
2. **Green**: 编写最少代码使测试通过
3. **Refactor**: 重构代码，保持测试通过

### 命令
```bash
# 运行测试
pytest tests/

# 运行特定测试
pytest tests/test_xxx.py -v

# 查看覆盖率
pytest --cov=src tests/
```
"""
    ),
    
    "debug-workflow": Skill(
        name="debug-workflow",
        description="系统化调试方法论",
        content="""## 调试工作流

### 步骤
1. **复现**: 确认问题可以稳定复现
2. **定位**: 使用二分法或日志定位问题
3. **分析**: 理解根本原因
4. **修复**: 实现最小修复
5. **验证**: 确认修复有效且无副作用

### 工具
- 日志分析
- 断点调试
- 单元测试
"""
    ),
    
    "export-formats": Skill(
        name="export-formats",
        description="多格式导出指南",
        content="""## 导出格式

### Markdown
```bash
python scripts/export.py -f markdown
```

### Word
```bash
python scripts/export.py -f word
```

### JSON (机器可读)
```bash
python scripts/export.py -f json
```

### JSONL (AI 训练)
```bash
python scripts/export.py -f jsonl
```

### HTML (浏览器查看)
```bash
python scripts/export.py -f html
```

### 全部格式 + ZIP
```bash
python scripts/export.py -f all --zip
```
"""
    ),
}
