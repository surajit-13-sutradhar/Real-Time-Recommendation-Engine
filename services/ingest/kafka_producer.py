import json
import logging
import asyncio
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError, KafkaTimeoutError

logger = logging.getLogger(__name__)

_producer: AIOKafkaProducer | None = None


async def get_producer() -> AIOKafkaProducer:
    global _producer
    if _producer is None:
        raise RuntimeError("Kafka producer is not initialised")
    return _producer


async def start_producer(bootstrap_servers: str) -> None:
    global _producer
    _producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        compression_type="gzip",
        acks="all",               # wait for all replicas to confirm
        enable_idempotence=True,  # no duplicate messages on retry
        request_timeout_ms=10000,
        retry_backoff_ms=300,
    )
    await _producer.start()
    logger.info("Kafka producer started, connected to %s", bootstrap_servers)


async def stop_producer() -> None:
    global _producer
    if _producer is not None:
        await _producer.stop()
        _producer = None
        logger.info("Kafka producer stopped")


async def publish_event(topic: str, event: dict, key: str | None = None) -> bool:
    try:
        producer = await get_producer()
        encoded_key = key.encode("utf-8") if key else None
        await producer.send_and_wait(topic, value=event, key=encoded_key)
        logger.info("event_published topic=%s key=%s", topic, key)
        return True
    except KafkaConnectionError:
        logger.error("kafka_connection_failed topic=%s", topic)
        return False
    except KafkaTimeoutError:
        logger.error("kafka_timeout topic=%s", topic)
        return False
    except Exception as e:
        logger.error("kafka_publish_error topic=%s error=%s", topic, str(e))
        return False