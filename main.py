import asyncio
import datetime
import json
import os
from astrbot.api.star import Context, Star, register
from astrbot.api.event import AstrMessageEvent
from astrbot.api.message_components import Plain, At
from astrbot.api.event.filter import command

@register("rollcall", "w33d", "群点名插件，通过指令启动/停止群点名，并支持查询距离下一次点名的时间", "1.0.1", "https://github.com/Last-emo-boy/roll-bot")
class RollCallPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # JSON 文件用于持久化存储需要点名的群号，建议放在当前插件目录下
        self.file_path = os.path.join(os.path.dirname(__file__), "rollcall_groups.json")
        self.groups = self.load_groups()
        # 存储下一次点名的时间，用于查询和日志显示
        self.next_call_time = None
        # 启动定时任务和日志输出任务
        asyncio.create_task(self.scheduled_rollcall())
        asyncio.create_task(self.stayalive_log())

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
        """将当前群号列表保存到 JSON 文件"""
        data = {"groups": self.groups}
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print("保存 JSON 文件错误:", e)

    @command("start_rollcall")
    async def start_rollcall(self, event: AstrMessageEvent):
        """
        启动当前群的群点名，将群号写入 JSON 文件中。
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

    @command("query_rollcall")
    async def query_rollcall(self, event: AstrMessageEvent):
        """
        查询距离下一次群点名（每天22:00）还有多少时间。
        """
        if not self.next_call_time:
            yield event.plain_result("点名任务尚未启动。")
        else:
            now = datetime.datetime.now()
            delta = self.next_call_time - now
            if delta.total_seconds() < 0:
                yield event.plain_result("即将执行点名，请稍后查看。")
            else:
                hours, rem = divmod(int(delta.total_seconds()), 3600)
                minutes, seconds = divmod(rem, 60)
                yield event.plain_result(f"距离下一次点名还有 {hours} 小时 {minutes} 分 {seconds} 秒。")

    async def scheduled_rollcall(self):
        """
        定时任务：每天等待到晚上22:00，遍历 JSON 文件中记录的群号，
        向每个群发送“晚点名”消息并@所有人。
        """
        while True:
            now = datetime.datetime.now()
            # 设置今天22:00的目标时间(服务器UTC时间，我懒得改了)
            target_time = now.replace(hour=15, minute=0, second=0, microsecond=0)
            if now >= target_time:
                target_time += datetime.timedelta(days=1)
            self.next_call_time = target_time
            delay = (target_time - now).total_seconds()
            await asyncio.sleep(delay)

            # 每次执行前重新加载最新的群号列表（以支持动态更新）
            self.groups = self.load_groups()
            for group in self.groups:
                # 构造消息链：发送“晚点名”并@所有人（请根据实际平台调整 At 参数）
                chain = [
                    Plain("晚点名"),
                    At(qq="all")
                ]
                await self.context.send_message(group, chain)

    async def stayalive_log(self):
        """
        每60秒在控制台打印一次日志，显示当前时间、下一次点名时间及剩余时间，
        以确认插件正常运行。
        """
        while True:
            now = datetime.datetime.now()
            if self.next_call_time:
                delta = self.next_call_time - now
                print(f"[stayalive] 当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}, "
                      f"下一次点名时间：{self.next_call_time.strftime('%Y-%m-%d %H:%M:%S')}, "
                      f"剩余时间：{str(delta).split('.')[0]}")
            else:
                print(f"[stayalive] 当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}, 点名任务未设定下一次执行时间。")
            await asyncio.sleep(60)

    async def terminate(self):
        """插件停用时的清理操作（如需要可添加）"""
        pass
