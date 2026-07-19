#!/usr/bin/env python3
"""
MiMo Code 核心协调器
整合所有组件：
- Checkpoint-Writer 记忆系统
- Skills 技能系统
- Agent 多角色系统
- Dream/Distill 自进化
- Goal 验证机制
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

from memory.checkpoint_writer import CheckpointWriter, MemoryManager
from skills.skill_manager import SkillManager, Skill
from agents.agent_manager import AgentManager, Agent, AgentMode
from verification.goal_verifier import GoalVerifier, Goal, GoalStatus
from evolution.dream_distill import EvolutionManager


class MiMoCore:
    """MiMo Code 核心系统"""
    
    def __init__(self, workspace: Path = None):
        self.workspace = workspace or Path.cwd()
        
        # 初始化各个子系统
        self.checkpoint = CheckpointWriter(self.workspace)
        self.memory = MemoryManager(self.checkpoint)
        self.skills = SkillManager(self.workspace)
        self.agents = AgentManager(self.workspace)
        self.verifier = GoalVerifier(self.workspace)
        self.evolution = EvolutionManager(self.workspace)
        
        # 设置当前代理
        self.agents.switch_agent("build")
    
    # ========== 记忆系统 ==========
    
    def write_checkpoint(self, state: Dict[str, Any]) -> Path:
        """写入 checkpoint"""
        return self.checkpoint.write_checkpoint(state)
    
    def read_checkpoint(self) -> Dict[str, str]:
        """读取 checkpoint"""
        return self.checkpoint.read_checkpoint()
    
    def append_notes(self, note: str):
        """追加笔记"""
        self.checkpoint.append_notes(note)
    
    def read_notes(self) -> str:
        """读取笔记"""
        return self.checkpoint.read_notes()
    
    def record_history(self, role: str, content: str, **kwargs):
        """记录历史"""
        self.checkpoint.record_history(role, content, **kwargs)
    
    def search_history(self, query: str, limit: int = 10) -> List[Dict]:
        """搜索历史"""
        return self.checkpoint.search_history(query, limit)
    
    def rebuild_context(self) -> str:
        """重建上下文"""
        return self.checkpoint.rebuild_context()
    
    # ========== 技能系统 ==========
    
    def list_skills(self) -> List[Dict]:
        """列出可用技能"""
        return [s.to_dict() for s in self.skills.list_skills()]
    
    def load_skill(self, name: str) -> Optional[str]:
        """加载技能内容"""
        return self.skills.load_skill(name)
    
    def create_skill(self, name: str, description: str, content: str) -> Skill:
        """创建新技能"""
        return self.skills.create_skill(name, description, content)
    
    def get_available_skills_xml(self) -> str:
        """获取可用技能 XML"""
        return self.skills.get_available_skills_xml()
    
    # ========== 代理系统 ==========
    
    def list_agents(self) -> List[Dict]:
        """列出代理"""
        return [a.config.to_dict() for a in self.agents.list_agents()]
    
    def switch_agent(self, name: str) -> Optional[Agent]:
        """切换代理"""
        return self.agents.switch_agent(name)
    
    def get_current_agent(self) -> Optional[Agent]:
        """获取当前代理"""
        return self.agents.current_agent
    
    def create_agent(self, name: str, description: str, **kwargs) -> Agent:
        """创建新代理"""
        return self.agents.create_agent(name, description, **kwargs)
    
    # ========== 目标验证 ==========
    
    def add_goal(self, description: str, criteria: List[str] = None) -> Goal:
        """添加目标"""
        return self.verifier.add_goal(description, criteria)
    
    def verify_goal(self, goal_index: int, context: str) -> tuple:
        """验证目标"""
        return self.verifier.verify_goal(goal_index, context)
    
    def get_active_goals(self) -> List[Goal]:
        """获取活跃目标"""
        return self.verifier.get_active_goals()
    
    # ========== 自进化 ==========
    
    def run_evolution(self) -> List[Dict]:
        """运行进化任务"""
        return self.evolution.check_and_run()
    
    def force_dream(self) -> Dict:
        """强制 Dream"""
        return self.evolution.force_dream()
    
    def force_distill(self) -> Dict:
        """强制 Distill"""
        return self.evolution.force_distill()
    
    def get_evolution_status(self) -> Dict:
        """获取进化状态"""
        return self.evolution.get_status()
    
    # ========== 综合功能 ==========
    
    def execute_with_goal(self, task: str, goal_description: str, 
                          goal_criteria: List[str] = None) -> Dict:
        """执行任务并验证目标"""
        # 1. 添加目标
        goal = self.add_goal(goal_description, goal_criteria)
        
        # 2. 记录任务开始
        self.record_history("system", f"开始任务: {task}")
        
        # 3. 执行任务（这里只是示例，实际需要集成具体的执行逻辑）
        result = {
            "task": task,
            "goal": goal.to_dict(),
            "status": "executing",
        }
        
        return result
    
    def get_system_status(self) -> Dict:
        """获取系统状态"""
        return {
            "workspace": str(self.workspace),
            "current_agent": self.agents.current_agent.name if self.agents.current_agent else None,
            "skills_count": len(self.skills.list_skills()),
            "agents_count": len(self.agents.list_agents()),
            "active_goals": len(self.verifier.get_active_goals()),
            "evolution_status": self.evolution.get_status(),
        }


# ========== 命令行接口 ==========

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="MiMo Code 核心系统")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # status 命令
    subparsers.add_parser("status", help="显示系统状态")
    
    # checkpoint 命令
    checkpoint_parser = subparsers.add_parser("checkpoint", help="Checkpoint 操作")
    checkpoint_parser.add_argument("action", choices=["read", "write"], help="操作类型")
    
    # skills 命令
    subparsers.add_parser("skills", help="列出可用技能")
    
    # agents 命令
    subparsers.add_parser("agents", help="列出代理")
    
    # goals 命令
    goals_parser = subparsers.add_parser("goals", help="目标操作")
    goals_parser.add_argument("action", choices=["list", "add"], help="操作类型")
    goals_parser.add_argument("--description", help="目标描述")
    
    # evolution 命令
    evo_parser = subparsers.add_parser("evolution", help="进化操作")
    evo_parser.add_argument("action", choices=["status", "dream", "distill"], help="操作类型")
    
    # history 命令
    hist_parser = subparsers.add_parser("history", help="历史搜索")
    hist_parser.add_argument("query", help="搜索关键词")
    
    args = parser.parse_args()
    
    core = MiMoCore()
    
    if args.command == "status":
        status = core.get_system_status()
        print(json.dumps(status, ensure_ascii=False, indent=2))
    
    elif args.command == "skills":
        skills = core.list_skills()
        print("可用技能:")
        for s in skills:
            print(f"  - {s['name']}: {s['description']}")
    
    elif args.command == "agents":
        agents = core.list_agents()
        print("代理列表:")
        for a in agents:
            print(f"  - {a['name']} ({a['mode']}): {a['description']}")
    
    elif args.command == "goals":
        if args.action == "list":
            goals = core.get_active_goals()
            print(f"活跃目标: {len(goals)}")
            for g in goals:
                print(f"  - {g.description}")
        elif args.action == "add" and args.description:
            goal = core.add_goal(args.description)
            print(f"已添加目标: {goal.description}")
    
    elif args.command == "evolution":
        if args.action == "status":
            status = core.get_evolution_status()
            print(json.dumps(status, ensure_ascii=False, indent=2))
        elif args.action == "dream":
            result = core.force_dream()
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.action == "distill":
            result = core.force_distill()
            print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.command == "history":
        results = core.search_history(args.query)
        print(f"搜索 '{args.query}' 结果: {len(results)} 条")
        for r in results:
            print(f"  [{r['timestamp']}] {r['role']}: {r['content'][:50]}...")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
