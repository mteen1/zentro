from typing import Any
import taskiq_fastapi
from taskiq import InMemoryBroker, ZeroMQBroker, AsyncBroker, AsyncResultBackend
from zentro.settings import settings
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend
from taskiq_aio_pika import AioPikaBroker

result_backend: AsyncResultBackend[Any] = RedisAsyncResultBackend(
    redis_url=str(settings.redis_url.with_path("/1")),
)
broker: AsyncBroker = AioPikaBroker(
    str(settings.rabbit_url),
).with_result_backend(result_backend)

if settings.environment.lower() == "pytest":
    broker = InMemoryBroker()

taskiq_fastapi.init(
    broker,
    "zentro.web.application:get_app",
)
