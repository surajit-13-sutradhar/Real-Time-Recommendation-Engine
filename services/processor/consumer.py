import json
import logging
import asyncio
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError

from config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPIC,
    KAFKA_GROUP_ID,
    KAFKA_AUTO_OFFSET_RESET,
)
from aggregator import UserEventAggregator

logger = logging.getLogger(__name__)


class EventProcessor:
    def __init__(self):
        self.aggregator = UserEventAggregator()
        self._consumer: AIOKafkaConsumer | None = None
        self._running = False

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=KAFKA_GROUP_ID,
            auto_offset_reset=KAFKA_AUTO_OFFSET_RESET,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            enable_auto_commit=True,
            auto_commit_interval_ms=1000,
            max_poll_records=100,       # process up to 100 messages per batch
            session_timeout_ms=30000,
            heartbeat_interval_ms=10000,
        )
        await self._consumer.start()
        self._running = True
        logger.info(
            "processor_started topic=%s group=%s",
            KAFKA_TOPIC, KAFKA_GROUP_ID,
        )

    async def stop(self) -> None:
        self._running = False
        if self._consumer:
            await self._consumer.stop()
            logger.info("processor_stopped")

    async def run(self) -> None:
        if not self._consumer:
            raise RuntimeError("Consumer not started")

        try:
            async for message in self._consumer:
                await self._handle_message(message)
        except asyncio.CancelledError:
            logger.info("processor_cancelled")
        except KafkaConnectionError as e:
            logger.error("kafka_connection_error error=%s", str(e))
            raise
        except Exception as e:
            logger.error("processor_unexpected_error error=%s", str(e))
            raise

    async def _handle_message(self, message) -> None:
        try:
            event = message.value
            self.aggregator.process(event)

            # Log stats every 100 events
            stats = self.aggregator.get_stats()
            if stats["total_events_processed"] % 100 == 0:
                logger.info("processor_stats %s", stats)

        except Exception as e:
            logger.error(
                "message_processing_error offset=%d error=%s",
                message.offset, str(e),
            )
            # Don't re-raise — log and continue to next message