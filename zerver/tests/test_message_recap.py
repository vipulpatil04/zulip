from typing import Any
from unittest import mock

import orjson
from django.conf import settings
from openai.resources.chat.completions import Completions
from openai.types.chat import ChatCompletion
from typing_extensions import override

from zerver.actions.message_recap import CITATION_RE, get_grouped_unread_messages, linkify_citations
from zerver.actions.realm_settings import do_change_realm_permission_group_setting
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import NamedUserGroup
from zerver.models.groups import SystemGroups
from zerver.models.realms import get_realm

LLM_FIXTURES_FILE = "zerver/tests/fixtures/llm/recap.json"


class LinkifyCitationsTestCase(ZulipTestCase):
    """Unit tests for the citation -> link safety mechanism at the heart of
    this feature. These don't touch the network or the LLM at all: they
    test that linkify_citations only ever turns a citation into a link
    when the cited id was genuinely part of the data we sent the model.
    """

    @override
    def setUp(self) -> None:
        super().setUp()
        self.realm = get_realm("zulip")
        self.stream_message: dict[str, Any] = {
            "id": 42,
            "type": "stream",
            "stream_id": 1,
            "display_recipient": "general",
            "subject": "some topic",
        }

    def test_valid_citation_becomes_link(self) -> None:
        lookup = {42: self.stream_message}
        result = linkify_citations("Alice said something important [#42].", self.realm, lookup)
        self.assertIn("near/42", result)
        self.assertNotIn("[#42]", result)

    def test_citation_format_variants_all_resolve(self) -> None:
        # The model is inconsistent about citation formatting in practice
        # (observed "[42]", "[#42]", and "【42】" from the same model across
        # different live calls), so linkify_citations needs to handle all
        # three, not just the format we asked for in the prompt.
        lookup = {42: self.stream_message}
        for citation_text in ("[42]", "[#42]", "【42】"):
            with self.subTest(citation_text=citation_text):
                result = linkify_citations(f"See this: {citation_text}.", self.realm, lookup)
                self.assertIn("near/42", result)

    def test_hallucinated_citation_is_dropped_not_linked(self) -> None:
        # An id that was never sent to the model (hallucinated, or copied
        # from a different section's data) must never become a link.
        lookup: dict[int, dict[str, Any]] = {42: self.stream_message}
        result = linkify_citations("Something happened [#99999].", self.realm, lookup)
        self.assertNotIn("99999", result)
        self.assertNotIn("near/99999", result)

    def test_empty_lookup_drops_every_citation(self) -> None:
        result = linkify_citations("Claim one [#1]. Claim two [#2].", self.realm, {})
        self.assertNotIn("near/", result)


class GetGroupedUnreadMessagesTestCase(ZulipTestCase):
    def test_groups_streams_pms_and_huddles_separately(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        cordelia = self.example_user("cordelia")
        self.subscribe(hamlet, "Denmark")
        self.subscribe(iago, "Denmark")

        self.send_stream_message(
            iago, "Denmark", content="hello there", topic_name="recap test topic"
        )
        self.send_personal_message(iago, hamlet, content="a direct message")
        self.send_group_direct_message(iago, [hamlet, cordelia], content="a group message")

        result = get_grouped_unread_messages(hamlet)

        self.assert_length(result["streams"], 1)
        self.assertEqual(result["streams"][0]["label"], "#Denmark > recap test topic")

        self.assert_length(result["pms"], 1)
        self.assertEqual(result["pms"][0]["label"], "Iago")

        self.assert_length(result["huddles"], 1)
        self.assertIn("Iago", result["huddles"][0]["label"])
        self.assertFalse(result["truncated"])


class MessageRecapEndpointTestCase(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user("hamlet")
        self.sender = self.example_user("iago")
        self.login_user(self.user)
        self.subscribe(self.user, "Denmark")
        self.first_message_id = self.send_stream_message(
            self.sender,
            "Denmark",
            content="Zulip just launched a message recap feature.",
            topic_name="recap launch",
        )
        self.send_stream_message(
            self.sender,
            "Denmark",
            content="It summarizes all of your unread messages in one place.",
            topic_name="recap launch",
        )

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

    def test_recap_returns_summary_with_working_link(self) -> None:
        if settings.GENERATE_LLM_FIXTURES:  # nocoverage
            # NOTE: You need proper credentials in zproject/dev-secrets.conf
            # to generate this fixture.
            with self.settings(TOPIC_SUMMARIZATION_MODEL="openai/gpt-oss-120b"):
                self.client_get("/json/messages/recap")
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
        # The recorded response cites the message ids that existed when the
        # fixture was captured, which won't match this run's ids (Zulip's
        # test suite shares one incrementing message id sequence across
        # test classes). Retarget its first citation at a message id that
        # genuinely exists in this run, so the test verifies real citation
        # -> link resolution instead of coincidentally matching stale ids.
        content = fixture_data["response"]["choices"][0]["message"]["content"]
        content = CITATION_RE.sub(f"[#{self.first_message_id}]", content, count=1)
        fixture_data["response"]["choices"][0]["message"]["content"] = content
        fake_response = ChatCompletion.model_validate(fixture_data["response"])

        # Fake credentials to ensure we crash if a real network request is
        # made, which would indicate a problem with the fixture setup.
        with (
            self.settings(
                TOPIC_SUMMARIZATION_MODEL="openai/gpt-oss-120b",
                TOPIC_SUMMARIZATION_API_KEY="test",
            ),
            mock.patch.object(Completions, "create", return_value=fake_response),
        ):
            result = self.client_get("/json/messages/recap")

        payload = self.assert_json_success(result)
        self.assert_length(payload["sections"], 1)
        section = payload["sections"][0]
        self.assertEqual(section["title"], "Channels")
        # The summary must reference the real message via a working narrow
        # link, not just mention it in prose.
        self.assertIn("#narrow/channel/", section["html"])
        self.assertFalse(payload["truncated"])

    def test_recap_requires_permission(self) -> None:
        # can_summarize_topics_group defaults to "everyone", so we need to
        # restrict it to see the permission check actually deny someone;
        # this is the same permission check (and default) the existing
        # topic summarizer feature uses.
        realm = get_realm("zulip")
        moderators_group = NamedUserGroup.objects.get(
            name=SystemGroups.MODERATORS, realm_for_sharding=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm, "can_summarize_topics_group", moderators_group, acting_user=None
        )

        with open(LLM_FIXTURES_FILE, "rb") as f:
            fixture_data = orjson.loads(f.read())
        fake_response = ChatCompletion.model_validate(fixture_data["response"])

        # Hamlet is not a moderator, so he should be denied.
        with (
            self.settings(
                TOPIC_SUMMARIZATION_MODEL="openai/gpt-oss-120b",
                TOPIC_SUMMARIZATION_API_KEY="test",
            ),
            mock.patch.object(Completions, "create", return_value=fake_response),
        ):
            result = self.client_get("/json/messages/recap")
        self.assert_json_error(result, "Insufficient permission")

    def test_recap_requires_model_configured(self) -> None:
        with self.settings(TOPIC_SUMMARIZATION_MODEL=None):
            result = self.client_get("/json/messages/recap")
        self.assert_json_error(result, "AI features are not enabled on this server.")
