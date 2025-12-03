# app/api/v1/endpoints/events.py

import json
import asyncio
import aioredis
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.core.config import get_settings

settings = get_settings()

router = APIRouter(prefix="/events", tags=["events"])


async def redis_subscribe(channel_name: str):
    """
    Redis Pub/Sub 채널을 구독하고, 메세지가 들어올 때마다 yield 함.
    SSE 스트리밍에 사용됨.
    """
    redis = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel_name)

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)

            if message:
                yield {
                    "event": "message",
                    "data": message["data"]
                }

            await asyncio.sleep(0.01)  # CPU 과점 방지
    except asyncio.CancelledError:
        await pubsub.unsubscribe(channel_name)
        await pubsub.close()
        await redis.close()
        raise


@router.get("/requests/{request_id}")
async def request_event_stream(request_id: int):
    """
    특정 request_id에 대한 SSE 스트림 엔드포인트
    Celery가 작업 완료 시 Redis로 publish → 이 SSE로 push됨.
    """
    channel = f"request-events:{request_id}"

    async def event_generator():
        async for msg in redis_subscribe(channel):
            yield msg

    return EventSourceResponse(event_generator())
