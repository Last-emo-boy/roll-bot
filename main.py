import asyncio
import datetime
import json
import os
from astrbot.api.all import *

@register("rollcall", "Your Name", "群点名插件，通过指令启动/停止群点名，群号持久化存储到 JSON 文件", "1.0.0", "repo url")
class RollCallPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 定义 JSON 文件路径，建议使用绝对路径或放在 AstrBot 的 data 目录下
        self.file_path = os.path.join(os.path.dirname(__file__), "rollcall_groups.json")
        self.groups = self.load_groups()
        # 启动定时任务
        asyncio.create_task(self.scheduled_rollcall())

    def load_groups(self):
        """从 JSON 文件中加载群号列表，返回列表"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # data 结构示例：{"groups": ["123456", "654321"]}
                return data.get("groups", [])
            except Exception as e:
                print("加载 JSON 文件错误:", e)
                return []
        else:
            return []

    def save_groups(self):
        """保存群号列表到 JSON 文件"""
        data = {"groups": self.groups}
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print("保存 JSON 文件错误:", e)

    @command("start_rollcall")
    async def start_rollcall(self, event: AstrMessageEvent):
        """
        启动当前群的群点名，持久化群号到 JSON 文件中。
        仅支持群聊使用。
        """
        group_id = event.message_obj.group_id
        if not group_id:
            yield event.plain_result("此指令仅支持群聊使用。")
            return

        if group_id in self.groups:
            yield event.plain_result("群点名已经启动，无需重复添加。")
        else:
            self.groups.append(group_id)
            self.save_groups()
            yield event.plain_result("群点名已启动，本群将在每天22:00收到点名消息。")

    @command("stop_rollcall")
    async def stop_rollcall(self, event: AstrMessageEvent):
        """
        停止当前群的群点名，将群号从 JSON 文件中移除。
        仅支持群聊使用。
        """
        group_id = event.message_obj.group_id
        if not group_id:
            yield event.plain_result("此指令仅支持群聊使用。")
            return

        if group_id in self.groups:
            self.groups.remove(group_id)
            self.save_groups()
            yield event.plain_result("群点名已停止。")
        else:
            yield event.plain_result("本群未启动群点名。")

    async def scheduled_rollcall(self):
        """
        定时任务，每天等待到晚上22:00（若已过则延迟到第二天），然后遍历 JSON 文件中记录的群号，
        向每个群发送“晚点名”消息并@所有人。
        """
        while True:
            now = datetime.datetime.now()
            # 计算今天晚上22:00的时间
            target_time = now.replace(hour=22, minute=0, second=0, microsecond=0)
            if now >= target_time:
                target_time += datetime.timedelta(days=1)
            delay = (target_time - now).total_seconds()
            await asyncio.sleep(delay)

            # 每次执行前重新加载最新的群号列表
            self.groups = self.load_groups()
            for group in self.groups:
                # 构造消息链，此处使用 At(qq="all") 表示@所有人，实际情况请根据平台调整
                chain = [
                    Plain("晚点名"),
                    At(qq="all")
                ]
                await self.context.send_message(group, chain)
