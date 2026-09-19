import logging
from collections.abc import Mapping
from types import FrameType
from typing import Any

from typing_extensions import override

from zerver.actions.topic_drift import check_topic_drift, notify_admins_of_topic_drift
from zerver.models import Realm, Stream
from zerver.worker.base import InterruptConsumeError, QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("topic_drift_check")
class TopicDriftChecker(QueueProcessingWorker):
    @override
    def consume(self, event: Mapping[str, Any]) -> None:
        try:
            realm = Realm.objects.get(id=event["realm_id"])
            stream = Stream.objects.get(id=event["stream_id"], realm=realm)
        except (Realm.DoesNotExist, Stream.DoesNotExist):  # nocoverage
            # Realm or channel may have been deleted since this was queued.
            return

        topic_name = event["topic_name"]
        suggested_title = check_topic_drift(realm, stream, topic_name)
        if suggested_title is None:
            logger.info("No topic drift detected for %s/%s", stream.name, topic_name)
            return

        logger.info(
            "Topic drift detected for %s/%s; suggested title: %r",
            stream.name,
            topic_name,
            suggested_title,
        )
        notify_admins_of_topic_drift(
            realm, stream, topic_name, event["message_id"], suggested_title
        )

    @override
    def timer_expired(
        self, limit: int, events: list[dict[str, Any]], signal: int, frame: FrameType | None
    ) -> None:
        assert len(events) == 1
        event = events[0]

        logging.warning(
            "Timed out in %s after %s seconds while checking topic drift for %s/%s",
            self.queue_name,
            limit,
            event["stream_id"],
            event["topic_name"],
        )
        raise InterruptConsumeError
