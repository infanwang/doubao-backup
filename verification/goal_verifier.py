#!/usr/bin/env python3
"""
Goal 验证机制
借鉴 MiMo Code 的独立完成度验证：
- 用户设定停止条件
- 独立模型验证任务完成度
- 防止 Agent 提前宣称"完成"
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class GoalStatus(Enum):
    PENDING = "pending"          # 待验证
    ACHIEVED = "achieved"        # 已达成
    NOT_ACHIEVED = "not_achieved"  # 未达成
    IMPOSSIBLE = "impossible"    # 不可能完成


@dataclass
class Goal:
    """目标定义"""
    description: str
    criteria: List[str] = None
    status: GoalStatus = GoalStatus.PENDING
    verification_count: int = 0
    max_verifications: int = 10
    
    def to_dict(self) -> Dict:
        return {
            "description": self.description,
            "criteria": self.criteria or [],
            "status": self.status.value,
            "verification_count": self.verification_count,
        }


class GoalVerifier:
    """目标验证器 - 独立于 Agent 的验证者"""
    
    def __init__(self, workspace: Path = None):
        self.workspace = workspace or Path.cwd()
        self.goals_file = self.workspace / ".mimocode" / "goals.json"
        self.goals: List[Goal] = []
        self._load_goals()
    
    def _load_goals(self):
        """加载目标"""
        if self.goals_file.exists():
            try:
                data = json.loads(self.goals_file.read_text(encoding="utf-8"))
                self.goals = [
                    Goal(
                        description=g["description"],
                        criteria=g.get("criteria", []),
                        status=GoalStatus(g["status"]),
                        verification_count=g.get("verification_count", 0),
                    )
                    for g in data
                ]
            except Exception:
                self.goals = []
    
    def _save_goals(self):
        """保存目标"""
        self.goals_file.parent.mkdir(parents=True, exist_ok=True)
        data = [g.to_dict() for g in self.goals]
        self.goals_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    def add_goal(self, description: str, criteria: List[str] = None) -> Goal:
        """添加目标"""
        goal = Goal(description=description, criteria=criteria)
        self.goals.append(goal)
        self._save_goals()
        return goal
    
    def verify_goal(self, goal_index: int, context: str) -> Tuple[GoalStatus, str]:
        """
        验证目标完成度
        
        这是一个简化的验证器。在实际的 MiMo Code 中，
        会使用独立的模型调用来验证。
        
        Args:
            goal_index: 目标索引
            context: 当前上下文（对话历史、工具输出等）
        
        Returns:
            (状态, 反馈信息)
        """
        if goal_index >= len(self.goals):
            return GoalStatus.NOT_ACHIEVED, "目标不存在"
        
        goal = self.goals[goal_index]
        
        if goal.verification_count >= goal.max_verifications:
            return GoalStatus.IMPOSSIBLE, f"已达到最大验证次数 ({goal.max_verifications})"
        
        goal.verification_count += 1
        
        # 简化的验证逻辑
        # 在实际 MiMo Code 中，这里会调用独立的模型来验证
        feedback = self._analyze_completion(goal, context)
        
        if feedback["achieved"]:
            goal.status = GoalStatus.ACHIEVED
            self._save_goals()
            return GoalStatus.ACHIEVED, feedback["message"]
        else:
            goal.status = GoalStatus.NOT_ACHIEVED
            self._save_goals()
            return GoalStatus.NOT_ACHIEVED, feedback["message"]
    
    def _analyze_completion(self, goal: Goal, context: str) -> Dict:
        """分析目标完成度"""
        # 简化的分析逻辑
        # 在实际 MiMo Code 中，这里会使用模型进行深度分析
        
        result = {
            "achieved": False,
            "message": "",
            "missing": [],
            "suggestions": [],
        }
        
        # 检查是否包含目标关键词
        goal_keywords = goal.description.lower().split()
        context_lower = context.lower()
        
        matched = sum(1 for kw in goal_keywords if kw in context_lower)
        match_ratio = matched / len(goal_keywords) if goal_keywords else 0
        
        if match_ratio > 0.8:
            result["achieved"] = True
            result["message"] = f"目标基本达成 (匹配度: {match_ratio:.0%})"
        else:
            result["achieved"] = False
            result["message"] = f"目标未完全达成 (匹配度: {match_ratio:.0%})"
            
            # 找出缺失的部分
            missing = [kw for kw in goal_keywords if kw not in context_lower]
            if missing:
                result["missing"] = missing
                result["suggestions"].append(f"可能缺少: {', '.join(missing[:3])}")
        
        # 检查标准
        if goal.criteria:
            for criterion in goal.criteria:
                if criterion.lower() not in context_lower:
                    result["achieved"] = False
                    result["missing"].append(criterion)
                    result["suggestions"].append(f"标准未满足: {criterion}")
        
        return result
    
    def get_active_goals(self) -> List[Goal]:
        """获取未完成的目标"""
        return [g for g in self.goals if g.status == GoalStatus.PENDING]
    
    def get_completed_goals(self) -> List[Goal]:
        """获取已完成的目标"""
        return [g for g in self.goals if g.status == GoalStatus.ACHIEVED]
    
    def clear_goals(self):
        """清空所有目标"""
        self.goals = []
        self._save_goals()


class GoalVerifierWithLLM(GoalVerifier):
    """带 LLM 验证的目标验证器"""
    
    def __init__(self, workspace: Path = None, llm_client=None):
        super().__init__(workspace)
        self.llm_client = llm_client
    
    def verify_goal_with_llm(self, goal_index: int, context: str) -> Tuple[GoalStatus, str]:
        """使用 LLM 验证目标完成度"""
        if not self.llm_client:
            return self.verify_goal(goal_index, context)
        
        if goal_index >= len(self.goals):
            return GoalStatus.NOT_ACHIEVED, "目标不存在"
        
        goal = self.goals[goal_index]
        
        if goal.verification_count >= goal.max_verifications:
            return GoalStatus.IMPOSSIBLE, f"已达到最大验证次数 ({goal.max_verifications})"
        
        goal.verification_count += 1
        
        # 构建验证提示词
        prompt = f"""你是一个独立的验证者。请分析以下目标是否已完成。

目标: {goal.description}
标准: {', '.join(goal.criteria) if goal.criteria else '无'}

当前上下文:
{context[:2000]}...

请回答:
1. 目标是否已达成? (是/否)
2. 如果未达成，缺少什么?
3. 有什么建议?

回答格式:
ACHIEVED: 是/否
MISSING: 缺少的内容
SUGGESTIONS: 建议
"""
        
        try:
            response = self.llm_client.generate(prompt)
            return self._parse_llm_response(response, goal)
        except Exception as e:
            return self.verify_goal(goal_index, context)
    
    def _parse_llm_response(self, response: str, goal: Goal) -> Tuple[GoalStatus, str]:
        """解析 LLM 响应"""
        response_lower = response.lower()
        
        if "achieved: 是" in response_lower or "achieved: yes" in response_lower:
            goal.status = GoalStatus.ACHIEVED
            self._save_goals()
            return GoalStatus.ACHIEVED, response
        
        # 提取缺失信息
        missing = ""
        if "missing:" in response_lower:
            start = response_lower.index("missing:") + 8
            end = response_lower.index("\n", start) if "\n" in response_lower[start:] else len(response)
            missing = response[start:end].strip()
        
        goal.status = GoalStatus.NOT_ACHIEVED
        self._save_goals()
        return GoalStatus.NOT_ACHIEVED, f"未达成。缺少: {missing}" if missing else response
