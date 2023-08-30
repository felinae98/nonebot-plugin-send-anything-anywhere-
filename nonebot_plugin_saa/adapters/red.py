from functools import partial
from typing import Any, Dict, List

from nonebot import get_driver
from nonebot.adapters import Bot, Event
from nonebot.drivers import Request, ForwardMixin

from ..types import Text, Image, Mention
from ..utils import (
    TargetQQGroup,
    MessageFactory,
    PlatformTarget,
    TargetQQPrivate,
    SupportedAdapters,
    SupportedPlatform,
    MessageSegmentFactory,
    register_sender,
    register_get_bot_id,
    register_ms_adapter,
    register_list_targets,
    register_convert_to_arg,
    assamble_message_factory,
    register_target_extractor,
)

try:
    from nonebot.adapters.red import Bot as BotRed
    from nonebot.adapters.red import Message, MessageSegment
    from nonebot.adapters.red.event import (
        MessageEvent,
        GroupMessageEvent,
        PrivateMessageEvent,
    )

    adapter = SupportedAdapters.red
    register_red = partial(register_ms_adapter, adapter)

    MessageFactory.register_adapter_message(SupportedAdapters.red, Message)

    @register_red(Text)
    def _text(t: Text) -> MessageSegment:
        return MessageSegment.text(t.data["text"])

    @register_red(Image)
    async def _image(i: Image) -> MessageSegment:
        image = i.data["image"]
        if isinstance(image, str):
            driver = get_driver()
            assert isinstance(driver, ForwardMixin), "driver should be ForwardDriver"
            image_data = await driver.request(Request("GET", image))
            assert isinstance(image_data.content, bytes)
            return MessageSegment.image(image_data.content)
        return MessageSegment.image(image)

    @register_red(Mention)
    async def _mention(m: Mention) -> MessageSegment:
        return MessageSegment.at(m.data["user_id"])

    # @register_red(Reply)
    # async def _reply(r: Reply) -> MessageSegment:
    #     return MessageSegment.reply(r.data["message_id"])

    @register_target_extractor(PrivateMessageEvent)
    def _extract_private_msg_event(event: Event) -> TargetQQPrivate:
        assert isinstance(event, PrivateMessageEvent)
        assert event.senderUin, "senderUin should not be None for private message"
        return TargetQQPrivate(user_id=int(event.senderUin))

    @register_target_extractor(GroupMessageEvent)
    def _extract_group_msg_event(event: Event) -> TargetQQGroup:
        assert isinstance(event, GroupMessageEvent)
        return TargetQQGroup(group_id=int(event.peerUid))

    @register_convert_to_arg(adapter, SupportedPlatform.qq_private)
    def _gen_private(target: PlatformTarget) -> Dict[str, Any]:
        assert isinstance(target, TargetQQPrivate)
        return {
            "chat_type": "friend",
            "target": str(target.user_id),
        }

    @register_convert_to_arg(adapter, SupportedPlatform.qq_group)
    def _gen_group(target: PlatformTarget) -> Dict[str, Any]:
        assert isinstance(target, TargetQQGroup)
        return {
            "chat_type": "group",
            "target": str(target.group_id),
        }

    @register_sender(SupportedAdapters.red)
    async def send(
        bot,
        msg: MessageFactory[MessageSegmentFactory],
        target,
        event,
        at_sender: bool,
        reply: bool,
    ):
        assert isinstance(bot, BotRed)
        assert isinstance(target, (TargetQQGroup, TargetQQPrivate))
        if event:
            assert isinstance(event, MessageEvent)
            full_msg = assamble_message_factory(
                msg,
                Mention(event.get_user_id()),
                None,
                at_sender,
                reply,
            )
        else:
            full_msg = msg
        message_to_send = Message()
        for message_segment_factory in full_msg:
            message_segment = await message_segment_factory.build(bot)
            message_to_send += message_segment
        await bot.send_message(message=message_to_send, **target.arg_dict(bot))

    # @AggregatedMessageFactory.register_aggregated_sender(adapter)
    # async def aggregate_send(
    #     bot: Bot,
    #     message_factories: List[MessageFactory],
    #     target: PlatformTarget,
    #     event: Optional[Event],
    # ):
    #     assert isinstance(bot, BotRed)
    #     login_info = await bot.get_login_info()

    #     msg_list: List[Message] = []
    #     for msg_fac in message_factories:
    #         msg = await msg_fac.build(bot)
    #         assert isinstance(msg, Message)
    #         msg_list.append(msg)
    #     aggregated_message_segment = Message(
    #         [
    #             MessageSegment.node_custom(
    #                 user_id=login_info["user_id"],
    #                 nickname=login_info["nickname"],
    #                 content=msg,
    #             )
    #             for msg in msg_list
    #         ]
    #     )

    #     if isinstance(target, TargetQQGroup):
    #         await bot.send_group_forward_msg(
    #             group_id=target.group_id, messages=aggregated_message_segment
    #         )
    #     elif isinstance(target, TargetQQPrivate):
    #         await bot.send_private_forward_msg(
    #             user_id=target.user_id, messages=aggregated_message_segment
    #         )
    #     else:  # pragma: no cover
    #         raise RuntimeError(f"{target.__class__.__name__} not supported")

    @register_list_targets(SupportedAdapters.red)
    async def list_targets(bot: Bot) -> List[PlatformTarget]:
        assert isinstance(bot, BotRed)

        targets = []
        groups = await bot.get_groups()
        for group in groups:
            group_id = int(group.groupCode)
            target = TargetQQGroup(group_id=group_id)
            targets.append(target)

        # 获取好友列表
        users = await bot.get_friends()
        for user in users:
            user_id = int(user.uin)
            target = TargetQQPrivate(user_id=user_id)
            targets.append(target)

        return targets

    @register_get_bot_id(adapter)
    def _get_bot_id(bot: Bot):
        assert isinstance(bot, BotRed)
        return bot.self_id

except ImportError:
    pass
except Exception as e:
    raise e