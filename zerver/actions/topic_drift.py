import logging
import re
from typing import Any

import orjson
from django.conf import settings
from openai import APIError, OpenAI

from zerver.lib.topic import messages_for_topic
from zerver.models import Realm, Stream, UserProfile
from zerver.tornado.django_api import send_event_on_commit

logger = logging.getLogger(__name__)

DRIFT_PROMPT_SYSTEM = (
    "You are analyzing a chat topic in the Zulip team chat app to detect "
    "whether the discussion has drifted away from its title: sustained "
    "off-title discussion, or a new sub-thread that has taken over the "
    "conversation. A topic that is still generally on-subject, even if it "
    "has wandered briefly, has not drifted."
)
DRIFT_PROMPT_INSTRUCTION = (
    "Respond with only a JSON object of the form "
    '{"drifted": true or false, "suggested_title": "..."}. '
    "Set drifted to true only if the discussion has meaningfully moved away "
    "from the given title. If drifted is true, suggested_title should be a "
    "short, specific title (under 60 characters) for what the topic is "
    "actually about now. If drifted is false, suggested_title should be an "
    "empty string. Respond with nothing but that JSON object."
)

# Matches the first {...} block in the response, in case the model wraps
# the JSON in prose or a Markdown code fence despite being told not to.
JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def format_topic_messages_for_model(messages: list[dict[str, Any]]) -> str:
    data = [{"sender": message["sender"], "content": message["content"]} for message in messages]
    return orjson.dumps(data).decode()


def parse_drift_response(raw_response: str) -> str | None:
    """Returns the suggested title if the model reported drift, or None if
    it reported no drift, or if the response couldn't be parsed at all.
    """
    match = JSON_OBJECT_RE.search(raw_response)
    if match is None:
        logger.warning("Topic drift model response contained no JSON object: %r", raw_response)
        return None

    try:
        parsed = orjson.loads(match.group())
    except orjson.JSONDecodeError:
        logger.warning("Topic drift model response was not valid JSON: %r", raw_response)
        return None

    if not isinstance(parsed, dict) or "drifted" not in parsed:
        logger.warning("Topic drift model response missing expected fields: %r", raw_response)
        return None

    if not parsed["drifted"]:
        return None

    suggested_title = parsed.get("suggested_title")
    if not isinstance(suggested_title, str) or not suggested_title.strip():
        logger.warning(
            "Topic drift model reported drift but gave no usable suggested_title: %r",
            raw_response,
        )
        return None

    return suggested_title.strip()


def check_topic_drift(realm: Realm, stream: Stream, topic_name: str) -> str | None:
    """Returns a suggested new title if the topic appears to have drifted
    from its current title, or None if it hasn't (or the check couldn't be
    completed, e.g. the feature isn't configured or the LLM call failed).
    """
    model = settings.TOPIC_DRIFT_DETECTION_MODEL
    if model is None:  # nocoverage
        return None

    # A stream that has messages in it (checked below) necessarily has a
    # recipient; recipient_id is only None very transiently at creation.
    assert stream.recipient_id is not None
    messages = list(
        messages_for_topic(realm.id, stream.recipient_id, topic_name)
        .select_related("sender")
        .order_by("id")
    )
    if not messages:  # nocoverage
        return None

    formatted_messages = [
        {"sender": message.sender.full_name, "content": message.content} for message in messages
    ]
    prompt = (
        f'The topic is currently titled "{topic_name}". Here are the '
        f"messages in it, in order:\n"
        f"{format_topic_messages_for_model(formatted_messages)}\n\n"
        f"{DRIFT_PROMPT_INSTRUCTION}"
    )

    client = OpenAI(
        api_key=settings.TOPIC_SUMMARIZATION_API_KEY,
        base_url=settings.TOPIC_SUMMARIZATION_API_BASE,
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": DRIFT_PROMPT_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            **settings.TOPIC_DRIFT_DETECTION_PARAMETERS,
        )
    except APIError:
        logger.warning("Topic drift LLM call failed for %s/%s", stream.name, topic_name)
        return None

    raw_response = response.choices[0].message.content
    if raw_response is None:  # nocoverage
        return None
    return parse_drift_response(raw_response)


def get_realm_admin_user_ids(realm: Realm) -> list[int]:
    return list(
        UserProfile.objects.filter(
            realm=realm,
            is_active=True,
            role__in=(UserProfile.ROLE_REALM_ADMINISTRATOR, UserProfile.ROLE_REALM_OWNER),
        ).values_list("id", flat=True)
    )


def notify_admins_of_topic_drift(
    realm: Realm,
    stream: Stream,
    topic_name: str,
    message_id: int,
    suggested_title: str,
) -> None:
    """Delivers a drift suggestion to realm admins/owners in real time, via
    the same send_event_on_commit mechanism Zulip uses for other live
    updates (e.g. do_update_embedded_data in zerver/actions/message_edit.py).
    Treating this as an admin/moderation tool, rather than something every
    participant sees, was a deliberate scope decision for this feature.
    """
    admin_user_ids = get_realm_admin_user_ids(realm)
    if not admin_user_ids:  # nocoverage
        return

    event = {
        "type": "topic_drift_suggestion",
        "stream_id": stream.id,
        "topic_name": topic_name,
        "suggested_title": suggested_title,
        # Any message in the topic works here: the frontend uses this id
        # to call the existing PATCH /json/messages/<id> endpoint with
        # propagate_mode="change_all" to apply the suggested rename.
        "message_id": message_id,
    }
    send_event_on_commit(realm, event, admin_user_ids)
