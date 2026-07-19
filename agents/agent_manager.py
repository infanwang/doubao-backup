#!/usr/bin/env python3
"""
Agent 多角色系统
借鉴 MiMo Code 的代理架构：
- Primary Agents: Build, Plan, Compose
- Subagents: General, Explore
- Hidden System Agents: Compaction, Title, Summary
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class AgentMode(Enum):
    PRIMARY = "primary"      # 主代理
    SUBAGENT = "subagent"    # 子代理
    ALL = "all"              # 两者皆可


@dataclass
class AgentConfig:
    """代理配置"""
    name: str
    description: str
    mode: AgentMode = AgentMode.ALL
    model: str = None
    temperature: float = 0.3
    max_steps: int = None
    tools: Dict[str, bool] = field(default_factory=dict)
    permission: Dict[str, Any] = field(default_factory=dict)
    prompt: str = None
    color: str = None
    hidden: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "mode": self.mode.value,
            "model": self.model,
            "temperature": self.temperature,
            "max_steps": self.max_steps,
            "tools": self.tools,
            "permission": self.permission,
            "hidden": self.hidden,
        }


class Agent:
    """代理实例"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.conversation_history = []
        self.state = {}
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @property
    def description(self) -> str:
        return self.config.description
    
    def can_use_tool(self, tool_name: str) -> bool:
        """检查是否可以使用某个工具"""
        if tool_name in self.config.tools:
            return self.config.tools[tool_name]
        return True  # 默认允许
    
    def add_message(self, role: str, content: str):
        """添加消息到对话历史"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def get_context(self) -> str:
        """获取代理上下文"""
        context_parts = []
        
        # 系统提示词
        if self.config.prompt:
            context_parts.append(f"# System Prompt\n{self.config.prompt}")
        
        # 对话历史
        for msg in self.conversation_history[-10:]:  # 最近 10 条
            context_parts.append(f"[{msg['role']}]: {msg['content']}")
        
        return "\n\n".join(context_parts)


class AgentManager:
    """代理管理器"""
    
    def __init__(self, workspace: Path = None):
        self.workspace = workspace or Path.cwd()
        self.agents: Dict[str, Agent] = {}
        self.current_agent: Optional[Agent] = None
        
        self._register_builtin_agents()
        self._load_custom_agents()
    
    def _register_builtin_agents(self):
        """注册内置代理"""
        builtin_configs = [
            AgentConfig(
                name="build",
                description="默认主代理，拥有完整工具权限，用于通用开发工作",
                mode=AgentMode.PRIMARY,
                tools={"write": True, "edit": True, "bash": True, "read": True},
                color="#4CAF50",
            ),
            AgentConfig(
                name="plan",
                description="受限主代理，用于只读分析和规划",
                mode=AgentMode.PRIMARY,
                tools={"write": False, "edit": False, "bash": False, "read": True},
                permission={"edit": "deny", "bash": "deny"},
                color="#2196F3",
            ),
            AgentConfig(
                name="compose",
                description="通过内置技能编排工作的主代理",
                mode=AgentMode.PRIMARY,
                tools={"write": True, "edit": True, "bash": True, "skill": True},
                color="#9C27B0",
            ),
            AgentConfig(
                name="general",
                description="通用子代理，用于研究复杂问题和执行多步骤任务",
                mode=AgentMode.SUBAGENT,
                tools={"write": True, "edit": True, "bash": True},
                color="#FF9800",
            ),
            AgentConfig(
                name="explore",
                description="快速只读代理，用于探索代码库",
                mode=AgentMode.SUBAGENT,
                tools={"write": False, "edit": False, "bash": False, "read": True},
                color="#00BCD4",
                hidden=False,
            ),
        ]
        
        for config in builtin_configs:
            self.agents[config.name] = Agent(config)
    
    def _load_custom_agents(self):
        """加载自定义代理"""
        agent_dirs = [
            self.workspace / ".mimocode" / "agents",
            Path.home() / ".config" / "mimocode-core" / "agents",
        ]
        
        for agent_dir in agent_dirs:
            if not agent_dir.exists():
                continue
            
            for agent_file in agent_dir.glob("*.md"):
                try:
                    config = self._parse_agent_file(agent_file)
                    if config:
                        self.agents[config.name] = Agent(config)
                except Exception as e:
                    print(f"[!] 加载代理失败 {agent_file}: {e}")
    
    def _parse_agent_file(self, path: Path) -> Optional[AgentConfig]:
        """解析代理 Markdown 文件"""
        import re
        import yaml
        
        content = path.read_text(encoding="utf-8")
        
        # 解析 frontmatter
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
        if not match:
            return None
        
        frontmatter_str = match.group(1)
        prompt = match.group(2).strip()
        
        try:
            frontmatter = yaml.safe_load(frontmatter_str)
        except yaml.YAMLError:
            return None
        
        name = path.stem
        description = frontmatter.get("description", "")
        mode_str = frontmatter.get("mode", "all")
        mode = AgentMode(mode_str) if mode_str in [m.value for m in AgentMode] else AgentMode.ALL
        
        return AgentConfig(
            name=name,
            description=description,
            mode=mode,
            model=frontmatter.get("model"),
            temperature=frontmatter.get("temperature", 0.3),
            max_steps=frontmatter.get("steps"),
            tools=frontmatter.get("tools", {}),
            permission=frontmatter.get("permission", {}),
            prompt=prompt,
            color=frontmatter.get("color"),
            hidden=frontmatter.get("hidden", False),
        )
    
    def get_agent(self, name: str) -> Optional[Agent]:
        """获取代理"""
        return self.agents.get(name)
    
    def list_agents(self, mode: AgentMode = None, include_hidden: bool = False) -> List[Agent]:
        """列出代理"""
        agents = list(self.agents.values())
        
        if mode:
            agents = [a for a in agents if a.config.mode == mode or a.config.mode == AgentMode.ALL]
        
        if not include_hidden:
            agents = [a for a in agents if not a.config.hidden]
        
        return agents
    
    def switch_agent(self, name: str) -> Optional[Agent]:
        """切换当前代理"""
        agent = self.get_agent(name)
        if agent:
            self.current_agent = agent
            return agent
        return None
    
    def get_next_agent(self) -> Optional[Agent]:
        """获取下一个主代理（用于 Tab 切换）"""
        primary_agents = self.list_agents(mode=AgentMode.PRIMARY)
        if not primary_agents:
            return None
        
        if self.current_agent:
            try:
                current_idx = primary_agents.index(self.current_agent)
                next_idx = (current_idx + 1) % len(primary_agents)
                return primary_agents[next_idx]
            except ValueError:
                return primary_agents[0]
        
        return primary_agents[0]
    
    def create_agent(self, name: str, description: str, mode: str = "all",
                     tools: Dict[str, bool] = None, prompt: str = None,
                     directory: Path = None) -> Agent:
        """创建新代理"""
        if directory is None:
            directory = self.workspace / ".mimocode" / "agents"
        
        directory.mkdir(parents=True, exist_ok=True)
        
        agent_mode = AgentMode(mode) if mode in [m.value for m in AgentMode] else AgentMode.ALL
        
        config = AgentConfig(
            name=name,
            description=description,
            mode=agent_mode,
            tools=tools or {},
            prompt=prompt,
        )
        
        # 写入 Markdown 文件
        agent_file = directory / f"{name}.md"
        content = f"""---
description: {description}
mode: {mode}
tools:
  write: {tools.get('write', True) if tools else True}
  edit: {tools.get('edit', True) if tools else True}
  bash: {tools.get('bash', True) if tools else True}
---

{prompt or f'You are {name}. {description}'}
"""
        agent_file.write_text(content, encoding="utf-8")
        
        agent = Agent(config)
        self.agents[name] = agent
        
        return agent


# ========== 代理创建示例 ==========

EXAMPLE_AGENTS = {
    "backup-agent": AgentConfig(
        name="backup-agent",
        description="专门执行备份任务的代理",
        mode=AgentMode.SUBAGENT,
        tools={"bash": True, "read": True, "write": True},
        prompt="你是备份代理，负责执行聊天记录的备份、脱敏和导出任务。",
        color="#4CAF50",
    ),
    
    "search-agent": AgentConfig(
        name="search-agent",
        description="专门执行搜索任务的代理",
        mode=AgentMode.SUBAGENT,
        tools={"read": True, "bash": True},
        prompt="你是搜索代理，负责在备份数据中执行全文搜索和筛选。",
        color="#2196F3",
    ),
    
    "security-agent": AgentConfig(
        name="security-agent",
        description="安全审计代理，检查 PII 脱敏和数据安全",
        mode=AgentMode.SUBAGENT,
        tools={"read": True, "bash": True},
        prompt="你是安全代理，负责检查数据中的敏感信息并确保脱敏。",
        color="#F44336",
    ),
}
