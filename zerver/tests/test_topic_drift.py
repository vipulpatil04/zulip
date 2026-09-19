from typing import Any
from unittest import mock

import orjson
from django.conf import settings
from openai.resources.chat.completions import Completions
from openai.types.chat import ChatCompletion
from typing_extensions import override

from zerver.actions.message_send import TOPIC_DRIFT_CHECK_MESSAGE_THRESHOLD
from zerver.actions.topic_drift import get_realm_admin_user_ids, parse_drift_response
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import mock_queue_publish
from zerver.models import Stream
from zerver.models.realms import get_realm
from zerver.worker.topic_drift_check import TopicDriftChecker

LLM_FIXTURES_FILE = "zerver/tests/fixtures/llm/topic_drift.json"


class ParseDriftResponseTestCase(ZulipTestCase):
    """Pure unit tests for the model-response parser: no network, no LLM,
    no database. This is our defense against the model not reliably
    following the requested JSON format.
    """

    def test_valid_drifted_response(self) -> None:
        raw = '{"drifted": true, "suggested_title": "New topic title"}'
        self.assertEqual(parse_drift_response(raw), "New topic title")

    def test_valid_not_drifted_response(self) -> None:
        raw = '{"drifted": false, "suggested_title": ""}'
        self.assertIsNone(parse_drift_response(raw))

    def test_json_wrapped_in_prose_still_parses(self) -> None:
        raw = 'Sure, here is my analysis:\n{"drifted": true, "suggested_title": "Lunch plans"}\nHope that helps!'
        self.assertEqual(parse_drift_response(raw), "Lunch plans")

    def test_malformed_json_returns_none(self) -> None:
        raw = "{drifted: true, suggested_title: oops missing quotes}"
        self.assertIsNone(parse_drift_response(raw))

    def test_no_json_object_returns_none(self) -> None:
        raw = "I think the topic has drifted to be about lunch."
        self.assertIsNone(parse_drift_response(raw))

    def test_drifted_true_with_empty_title_returns_none(self) -> None:
        raw = '{"drifted": true, "suggested_title": "   "}'
        self.assertIsNone(parse_drift_response(raw))

    def test_missing_drifted_field_returns_none(self) -> None:
        raw = '{"suggested_title": "New title"}'
        self.assertIsNone(parse_drift_response(raw))


class TopicDriftTriggerTestCase(ZulipTestCase):
    """Verifies the trigger in do_send_messages fires exactly once, at the
    configured threshold, and not before or after -- the property that
    keeps this feature's LLM cost bounded regardless of topic length.
    """

    def test_trigger_fires_exactly_once_at_threshold(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)
        self.subscribe(user, "Denmark")

        with mock_queue_publish("zerver.actions.message_send.queue_event_on_commit") as patched:
            for i in range(TOPIC_DRIFT_CHECK_MESSAGE_THRESHOLD - 1):
                self.send_stream_message(
                    user, "Denmark", content=f"message {i}", topic_name="drift trigger test"
                )
            # No drift check should have been queued before the threshold.
            patched.assert_not_called()

            last_message_id = self.send_stream_message(
                user,
                "Denmark",
                content="the message that crosses the threshold",
                topic_name="drift trigger test",
            )
            patched.assert_called_once()
            queue_name = patched.call_args[0][0]
            self.assertEqual(queue_name, "topic_drift_check")
            event = patched.call_args[0][1]
            self.assertEqual(event["message_id"], last_message_id)
            self.assertEqual(event["topic_name"], "drift trigger test")

            # Further messages in the same topic must not re-trigger it.
            self.send_stream_message(
                user, "Denmark", content="one more message", topic_name="drift trigger test"
            )
            patched.assert_called_once()


class TopicDriftWorkerTestCase(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.realm = get_realm("zulip")
        self.stream = Stream.objects.get(name="Denmark", realm=self.realm)
        self.sender = self.example_user("hamlet")
        self.subscribe(self.sender, "Denmark")

        if settings.GENERATE_LLM_FIXTURES:  # nocoverage
            self.patcher = mock.patch.object(
                Completions, "create", autospec=True, side_effect=Completions.create
            )
            self.mocked_completion = self.patcher.start()

    @override
    def tearDown(self) -> None:
        if settings.GENERATE_LLM_FIXTURES:  # nocoverage
            self.patcher.stop()
        super().tearDown()

    def _send_drift_scenario(self) -> int:
        for i in range(20):
            self.send_stream_message(
                self.sender,
                "Denmark",
                content=f"Printer troubleshooting note {i}: checked drivers and toner.",
                topic_name="printer setup issues",
            )
        drift_messages = [
            "Forget the printer for now, is everyone in for the hackathon this weekend?",
            "Yes! Let's form a team.",
            "What should we build?",
            "An internal on-call tracking tool.",
            "I'll book a room for Saturday.",
        ]
        last_message_id = 0
        for content in drift_messages:
            last_message_id = self.send_stream_message(
                self.sender, "Denmark", content=content, topic_name="printer setup issues"
            )
        return last_message_id

    def test_worker_detects_drift_and_notifies_admins(self) -> None:
        last_message_id = self._send_drift_scenario()
        event: dict[str, Any] = {
            "realm_id": self.realm.id,
            "stream_id": self.stream.id,
            "topic_name": "printer setup issues",
            "message_id": last_message_id,
        }

        if settings.GENERATE_LLM_FIXTURES:  # nocoverage
            # NOTE: You need proper credentials in zproject/dev-secrets.conf
            # to generate this fixture.
            with self.settings(TOPIC_DRIFT_DETECTION_MODEL="openai/gpt-oss-20b"):
                TopicDriftChecker().consume(event)
            call_args = self.mocked_completion.call_args
            response = self.mocked_completion(*call_args.args, **call_args.kwargs)
            with open(LLM_FIXTURES_FILE, "wb") as f:
                fixture_data = {
                    "model": call_args.kwargs["model"],
                    "messages": call_args.kwargs["messages"],
                    "response": response.model_dump(mode="json"),
                }
                f.write(orjson.dumps(fixture_data, option=orjson.OPT_INDENT_2) + b"\n")
            return

        with open(LLM_FIXTURES_FILE, "rb") as f:
            fixture_data = orjson.loads(f.read())
        fake_response = ChatCompletion.model_validate(fixture_data["response"])

        admin_ids = get_realm_admin_user_ids(self.realm)
        self.assertGreater(len(admin_ids), 0)

        with (
            self.settings(
                TOPIC_DRIFT_DETECTION_MODEL="openai/gpt-oss-20b",
                TOPIC_SUMMARIZATION_API_KEY="test",
            ),
            mock.patch.object(Completions, "create", return_value=fake_response),
            self.capture_send_event_calls(expected_num_events=1) as events,
        ):
            TopicDriftChecker().consume(event)

        notice = events[0]
        notification_event = notice["event"]
        self.assertEqual(notification_event["type"], "topic_drift_suggestion")
        self.assertEqual(notification_event["stream_id"], self.stream.id)
        self.assertEqual(notification_event["message_id"], last_message_id)
        self.assertTrue(notification_event["suggested_title"])
        # Only realm admins/owners should receive this, per the scope
        # decision to treat this as a moderation tool.
        self.assertEqual(sorted(notice["users"]), sorted(admin_ids))

    def test_worker_does_nothing_when_not_drifted(self) -> None:
        message_id = 0
        for i in range(5):
            message_id = self.send_stream_message(
                self.sender,
                "Denmark",
                content=f"Still talking about the printer, note {i}.",
                topic_name="printer setup issues",
            )
        event: dict[str, Any] = {
            "realm_id": self.realm.id,
            "stream_id": self.stream.id,
            "topic_name": "printer setup issues",
            "message_id": message_id,
        }

        no_drift_response = {
            "id": "test",
            "object": "chat.completion",
            "created": 0,
            "model": "openai/gpt-oss-20b",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": '{"drifted": false, "suggested_title": ""}',
                    },
                }
            ],
        }
        fake_response = ChatCompletion.model_validate(no_drift_response)

        with (
            self.settings(
                TOPIC_DRIFT_DETECTION_MODEL="openai/gpt-oss-20b",
                TOPIC_SUMMARIZATION_API_KEY="test",
            ),
            mock.patch.object(Completions, "create", return_value=fake_response),
            self.capture_send_event_calls(expected_num_events=0),
        ):
            TopicDriftChecker().consume(event)
