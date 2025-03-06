import asyncio
import datetime
import json
import os
from astrbot.api.star import Context, Star, register
from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.event.filter import command
from astrbot.api.message_components import Plain, At
from astrbot.api import logger

@register("rollcall", "w33d", "群点名插件，通过指令启动/停止群点名，并支持查询下一次点名时间", "1.0.2", "https://github.com/Last-emo-boy/roll-bot")
class RollCallPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # JSON 文件用于持久化存储需要点名的目标，存放在插件目录下
        self.file_path = os.path.join(os.path.dirname(__file__), "rollcall_groups.json")
        self.targets = self.load_targets()
        # 存储下一次点名的时间，用于查询和日志显示
        self.next_call_time = None
        # 启动定时任务和日志输出任务
        asyncio.get_event_loop().create_task(self.scheduled_rollcall())
        asyncio.get_event_loop().create_task(self.stayalive_log())

    def load_targets(self):
        """从 JSON 文件中加载已注册的会话 ID 列表"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # JSON 格式示例：{"targets": ["unified_msg_origin1", "unified_msg_origin2"]}
                return data.get("targets", [])
            except Exception as e:
                logger.error("加载 JSON 文件错误: %s", e)
                return []
        else:
            return []

    def save_targets(self):
        """将当前注册的会话 ID 列表保存到 JSON 文件"""
        data = {"targets": self.targets}
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error("保存 JSON 文件错误: %s", e)

    @command("start_rollcall")
    async def start_rollcall(self, event: AstrMessageEvent):
        """
        启动当前群的点名，将当前群的 unified_msg_origin 注册到 JSON 文件中。
        仅支持群聊使用。
        """
        target = event.unified_msg_origin
        if not target:
            yield event.plain_result("无法获取当前会话ID，此指令仅支持群聊使用。")
            return
        if target in self.targets:
            yield event.plain_result("群点名已启动，无需重复添加。")
        else:
            self.targets.append(target)
            self.save_targets()
            yield event.plain_result("群点名已启动，本群将在每天22:00收到点名消息。")

    @command("stop_rollcall")
    async def stop_rollcall(self, event: AstrMessageEvent):
        """
        停止当前群的点名，将当前群的 unified_msg_origin 从 JSON 文件中移除。
        仅支持群聊使用。
        """
        target = event.unified_msg_origin
        if not target:
            yield event.plain_result("无法获取当前会话ID，此指令仅支持群聊使用。")
            return
        if target in self.targets:
            self.targets.remove(target)
            self.save_targets()
            yield event.plain_result("群点名已停止。")
        else:
            yield event.plain_result("本群尚未启动点名。")

    @command("query_rollcall")
    async def query_rollcall(self, event: AstrMessageEvent):
        """
        查询距离下一次点名（每天22:00）还有多少时间。
        """
        if not self.next_call_time:
            yield event.plain_result("点名任务尚未启动。")
        else:
            now = datetime.datetime.now()
            delta = self.next_call_time - now
            if delta.total_seconds() < 0:
                yield event.plain_result("点名即将执行，请稍后查看。")
            else:
                hours, rem = divmod(int(delta.total_seconds()), 3600)
                minutes, seconds = divmod(rem, 60)
                yield event.plain_result(f"距离下一次点名还有 {hours} 小时 {minutes} 分 {seconds} 秒。")

    async def scheduled_rollcall(self):
        """
        定时任务：每天等待到 22:00 后，遍历 JSON 文件中注册的目标，
        发送“晚点名”消息并 @所有人（请根据实际平台调整 At 参数）。
        """
        while True:
            now = datetime.datetime.now()
            target_time = now.replace(hour=14, minute=0, second=0, microsecond=0)
            if now >= target_time:
                target_time += datetime.timedelta(days=1)
            self.next_call_time = target_time
            delay = (target_time - now).total_seconds()
            logger.info("等待 %s 秒直到下一次点名时间: %s", delay, target_time.strftime("%Y-%m-%d %H:%M:%S"))
            await asyncio.sleep(delay)

            # 每次执行前重新加载最新的目标列表，支持动态更新
            self.targets = self.load_targets()
            for target in self.targets:
                chain = MessageChain()
                chain.chain.extend([
                    Plain("晚点名"),
                    At(qq="all")
                ])
                try:
                    await self.context.send_message(target, chain)
                    logger.info("已向目标 %s 发送点名消息。", target)
                except Exception as e:
                    logger.error("向 %s 发送点名消息失败: %s", target, e)

    async def stayalive_log(self):
        """
        每 60 秒使用 logger 输出一次日志，显示当前时间、下一次点名时间及剩余时间，
        以确认插件正在正常运行。
        """
        while True:
            now = datetime.datetime.now()
            if self.next_call_time:
                delta = self.next_call_time - now
                logger.info("[stayalive] 当前时间: %s, 下一次点名: %s, 剩余时间: %s",
                            now.strftime("%Y-%m-%d %H:%M:%S"),
                            self.next_call_time.strftime("%Y-%m-%d %H:%M:%S"),
                            str(delta).split('.')[0])
            else:
                logger.info("[stayalive] 当前时间: %s, 点名任务尚未设定。",
                            now.strftime("%Y-%m-%d %H:%M:%S"))
            await asyncio.sleep(60)

    async def terminate(self):
        """
        插件停用时的清理操作（如需要可添加）。
        """
        pass
