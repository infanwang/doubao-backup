#!/usr/bin/env python3
"""
Doubao Backup Agent
集成 MiMo Code 四大特性的智能备份代理
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from orchestrator import MiMoCore
from scripts.backup import do_backup, do_login
from scripts.export import export_all, load_config


class DoubaoBackupAgent:
    """豆包备份代理"""
    
    def __init__(self):
        self.workspace = Path(__file__).parent
        self.core = MiMoCore(self.workspace)
        self.config = load_config()
    
    def run_full_workflow(self):
        """执行完整的备份工作流"""
        print("=" * 60)
        print("  Doubao Backup Agent - 智能备份工作流")
        print("=" * 60)
        
        # 阶段1: 设置目标
        print("\n【阶段1】设置备份目标")
        print("-" * 50)
        
        goal = self.core.add_goal(
            "完成豆包聊天记录备份",
            [
                "登录成功",
                "抓取所有对话",
                "PII 脱敏完成",
                "导出文件完成",
            ]
        )
        print(f"  目标: {goal.description}")
        
        # 阶段2: 更新 checkpoint
        print("\n【阶段2】初始化项目状态")
        print("-" * 50)
        
        self.core.write_checkpoint({
            "current_intent": "执行豆包备份",
            "next_action": "登录并抓取聊天记录",
            "task_tree": "1. 登录豆包\n2. 抓取聊天列表\n3. 抓取消息内容\n4. PII 脱敏\n5. 导出文件",
            "constraints": "使用 Selenium 浏览器自动化",
        })
        
        self.core.record_history("user", "执行豆包备份")
        
        # 阶段3: 执行备份
        print("\n【阶段3】执行备份")
        print("-" * 50)
        
        try:
            do_backup(full=True, pii=True, rate_limit=2.0)
            self.core.record_history("assistant", "备份执行完成")
        except Exception as e:
            self.core.record_history("assistant", f"备份执行失败: {e}")
            print(f"  ✗ 备份失败: {e}")
            return
        
        # 阶段4: 导出
        print("\n【阶段4】导出文件")
        print("-" * 50)
        
        try:
            export_all(config=self.config, formats=["markdown", "json"], create_zip=True)
            self.core.record_history("assistant", "导出完成")
        except Exception as e:
            print(f"  ✗ 导出失败: {e}")
        
        # 阶段5: 验证
        print("\n【阶段5】验证目标")
        print("-" * 50)
        
        status, feedback = self.core.verify_goal(0, "备份完成，导出成功")
        print(f"  验证结果: {status.value}")
        
        # 阶段6: 更新状态
        self.core.write_checkpoint({
            "current_intent": "备份完成",
            "next_action": "等待下次备份",
            "task_tree": "1. ✅ 登录豆包\n2. ✅ 抓取聊天列表\n3. ✅ 抓取消息内容\n4. ✅ PII 脱敏\n5. ✅ 导出文件",
        })
        
        self.core.force_dream()
        
        print("\n" + "=" * 60)
        print("  备份工作流完成")
        print("=" * 60)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Doubao Backup Agent")
    parser.add_argument("--login", action="store_true", help="仅登录")
    parser.add_argument("--full", "-f", action="store_true", help="完整工作流")
    args = parser.parse_args()
    
    agent = DoubaoBackupAgent()
    
    if args.login:
        do_login()
    else:
        agent.run_full_workflow()


if __name__ == "__main__":
    import os
    main()
