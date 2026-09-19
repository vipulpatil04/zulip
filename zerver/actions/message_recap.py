import logging
import re
import time
from typing import Any, Callable, TypedDict

import orjson
from django.conf import settings
from openai import APIError, OpenAI

from zerver.actions.message_summary import make_message
from zerver.lib.markdown import markdown_convert
from zerver.lib.message import (
    aggregate_unread_data,
    get_raw_unread_data,
    messages_for_ids,
)
from zerver.lib.url_encoding import message_link_url
from zerver.models import Realm, UserProfile
from zerver.models.realms import MessageEditHistoryVisibilityPolicyEnum

logger = logging.getLogger(__name__)

# Matches the requested "[#12345]" citation format, plus variants we've
# observed the model produce despite instructions: "[12345]" without the
# "#", and "【12345】" using full-width CJK brackets instead of ASCII ones.
# The model is not reliable about this formatting, so we match broadly
# rather than assume it followed the prompt exactly.
CITATION_RE = re.compile(r"[\[【]#?(\d+)[\]】]")

# Groq's free tier limits usage by tokens/minute, not just requests/minute
# (as low as 8,000 TPM on the models we use), so a recap touching several
# sections can trip a 429 even though we only make a handful of requests.
# A short retry with backoff is enough to ride out that ceiling for a
# single user's request.
MAX_LLM_CALL_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 2.0

# Maximum number of unread messages we'll feed into the recap as a
# whole, across all conversations combined. This bounds the LLM cost
# and latency of a single recap request; users with more unread
# messages than this only get a recap of their most recent ones.
MAX_RECAP_MESSAGES = 150

# We batch all conversations of a given kind (channels, DMs, group DMs)
# into a single LLM call, rather than one call per conversation. Groq's
# free tier caps usage by tokens/minute, not just requests/minute, and
# one call per conversation repeats the (fixed-size) system prompt once
# per conversation, which burns through that budget far faster than a
# few batched calls do. See implementation.md for the full trade-off.
SECTION_PROMPT_INTRO = (
    "The following are groups of unread Zulip messages, each group belonging to "
    "one conversation (a channel topic, a direct message, or a group direct "
    "message). Each message is tagged with a numeric id."
)
SECTION_PROMPT_INSTRUCTION = (
    "Summarize each conversation separately, in 1-3 sentences per conversation. "
    "Write one Markdown heading per conversation, using exactly the conversation "
    "label given to you as the heading text, followed by the summary. Mention key "
    "conclusions and actions, if any. After any sentence that relies on specific "
    "messages, cite the message ids it's based on inline like [#12345] (you may "
    "cite more than one id per sentence). Only cite ids that were given to you; "
    "never invent an id."
)


class RecapConversation(TypedDict):
    # A human-readable label for this conversation, e.g. "#backend > API redesign"
    # for a channel topic, or a sender/participant name for direct messages.
    label: str
    messages: list[dict[str, Any]]


class GroupedUnreadMessages(TypedDict):
    streams: list[RecapConversation]
    pms: list[RecapConversation]
    huddles: list[RecapConversation]
    # True if there were more unread messages than MAX_RECAP_MESSAGES,
    # so some of them were left out of the recap.
    truncated: bool


class RecapSection(TypedDict):
    # Display title for this section, e.g. "Channels" or "Direct Messages".
    title: str
    # Rendered (Zulip Markdown -> HTML) summary text for this section,
    # with citations already validated and turned into narrow links.
    html: str


class RecapResult(TypedDict):
    # Only sections with at least one unread conversation are included.
    sections: list[RecapSection]
    truncated: bool


def get_grouped_unread_messages(user_profile: UserProfile) -> GroupedUnreadMessages:
    raw_unread_data = get_raw_unread_data(user_profile)
    aggregated = aggregate_unread_data(raw_unread_data, allow_empty_topic_name=False)

    # Each of these is a list of conversations, where each conversation
    # carries its own list of unread message ids (see aggregate_streams,
    # aggregate_pms, aggregate_direct_message_groups in zerver/lib/message.py).
    stream_conversations = aggregated["streams"]
    pm_conversations = aggregated["pms"]
    huddle_conversations = aggregated["huddles"]

    all_message_ids: list[int] = [
        message_id
        for conversation in (*stream_conversations, *pm_conversations, *huddle_conversations)
        for message_id in conversation["unread_message_ids"]
    ]

    # Keep only the most recent MAX_RECAP_MESSAGES messages overall, so a
    # user with a huge backlog still gets a fast, bounded-cost recap
    # rather than one that scales with their entire unread count.
    truncated = len(all_message_ids) > MAX_RECAP_MESSAGES
    kept_message_ids = set(sorted(all_message_ids, reverse=True)[:MAX_RECAP_MESSAGES])

    user_message_flags: dict[int, list[str]] = {
        message_id: [] for message_id in kept_message_ids
    }
    hydrated_messages = messages_for_ids(
        message_ids=sorted(kept_message_ids),
        user_message_flags=user_message_flags,
        search_fields={},
        # We only need the plain-text content to pass to the model.
        apply_markdown=False,
        client_gravatar=True,
        allow_empty_topic_name=False,
        message_edit_history_visibility_policy=MessageEditHistoryVisibilityPolicyEnum.none.value,
        user_profile=user_profile,
        realm=user_profile.realm,
    )
    message_by_id = {message["id"]: message for message in hydrated_messages}

    def build_conversations(
        conversation_message_ids: list[list[int]],
        label_fn: Callable[[list[dict[str, Any]]], str],
    ) -> list[RecapConversation]:
        result = []
        for message_ids in conversation_message_ids:
            messages = [
                message_by_id[message_id]
                for message_id in message_ids
                if message_id in kept_message_ids
            ]
            if not messages:
                # Every message in this conversation was truncated away.
                continue
            result.append(RecapConversation(label=label_fn(messages), messages=messages))
        return result

    def stream_label(messages: list[dict[str, Any]]) -> str:
        return f"#{messages[0]['display_recipient']} > {messages[0]['subject']}"

    def pm_label(messages: list[dict[str, Any]]) -> str:
        # Unread messages are always ones we received, so the sender is
        # the other party (or ourselves, in the self-DM edge case).
        return messages[0]["sender_full_name"]

    def huddle_label(messages: list[dict[str, Any]]) -> str:
        other_names = [
            recipient["full_name"]
            for recipient in messages[0]["display_recipient"]
            if recipient["id"] != user_profile.id
        ]
        return ", ".join(other_names)

    return GroupedUnreadMessages(
        streams=build_conversations(
            [c["unread_message_ids"] for c in stream_conversations], stream_label
        ),
        pms=build_conversations([c["unread_message_ids"] for c in pm_conversations], pm_label),
        huddles=build_conversations(
            [c["unread_message_ids"] for c in huddle_conversations], huddle_label
        ),
        truncated=truncated,
    )


def format_section_for_model(conversations: list[RecapConversation]) -> str:
    # Unlike format_zulip_messages_for_model in message_summary.py, we
    # include each message's id, since the model needs it to produce
    # the [#id] citations we validate and linkify afterward.
    data = [
        {
            "conversation": conversation["label"],
            "messages": [
                {"id": message["id"], "sender": message["sender_full_name"], "content": message["content"]}
                for message in conversation["messages"]
            ],
        }
        for conversation in conversations
    ]
    return orjson.dumps(data).decode()


def summarize_section(conversations: list[RecapConversation]) -> str | None:
    """Summarizes one section (e.g. all channel conversations) in a single
    LLM call, returning raw Markdown text with unvalidated [#id] citations.
    Callers are responsible for validating and linkifying those citations
    before showing the result to a user.
    """
    model = settings.TOPIC_SUMMARIZATION_MODEL
    if not conversations or model is None:  # nocoverage
        return None

    messages = [
        make_message(SECTION_PROMPT_INTRO, "system"),
        make_message(format_section_for_model(conversations)),
        make_message(SECTION_PROMPT_INSTRUCTION),
    ]

    client = OpenAI(
        api_key=settings.TOPIC_SUMMARIZATION_API_KEY,
        base_url=settings.TOPIC_SUMMARIZATION_API_BASE,
    )
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        **settings.TOPIC_SUMMARIZATION_PARAMETERS,
    )
    return response.choices[0].message.content


def build_message_lookup(conversations: list[RecapConversation]) -> dict[int, dict[str, Any]]:
    return {
        message["id"]: message
        for conversation in conversations
        for message in conversation["messages"]
    }


def linkify_citations(
    summary_text: str, realm: Realm, message_lookup: dict[int, dict[str, Any]]
) -> str:
    """Replaces [#id] (or [id]) citations with links to the real message,
    dropping any id that wasn't in the data we actually sent the model.
    This is what makes citations trustworthy: even if the model
    hallucinates an id, or copies one over from an unrelated section, it
    can never turn into a link, since it isn't in this section's lookup.
    """

    def replace(match: re.Match[str]) -> str:
        message_id = int(match.group(1))
        message = message_lookup.get(message_id)
        if message is None:
            logger.warning(
                "Recap model cited message id %d, which was not in the data provided; dropping citation.",
                message_id,
            )
            return ""
        url = message_link_url(realm, message)
        return f"[[jump to message]]({url})"

    return CITATION_RE.sub(replace, summary_text)


def summarize_section_with_retry(conversations: list[RecapConversation]) -> str | None:
    for attempt in range(MAX_LLM_CALL_ATTEMPTS):
        try:
            return summarize_section(conversations)
        except APIError as e:
            # Covers rate limits (429s), connection errors, and timeouts
            # alike: all are transient failures talking to the LLM
            # provider, and we'd rather degrade this one section than
            # fail the whole recap request for an unrelated section's sake.
            if attempt == MAX_LLM_CALL_ATTEMPTS - 1:
                logger.warning(
                    "Recap LLM call failed after %d attempts (%s: %s); giving up on this section.",
                    MAX_LLM_CALL_ATTEMPTS,
                    type(e).__name__,
                    e,
                )
                return None
            delay = RETRY_BASE_DELAY_SECONDS * (2**attempt)
            logger.info(
                "Recap LLM call failed (attempt %d/%d, %s); retrying in %.1fs.",
                attempt + 1,
                MAX_LLM_CALL_ATTEMPTS,
                type(e).__name__,
                delay,
            )
            time.sleep(delay)
    return None  # nocoverage -- unreachable; loop always returns or raises above.


def do_recap_unread_messages(user_profile: UserProfile) -> RecapResult:
    grouped = get_grouped_unread_messages(user_profile)

    section_specs: list[tuple[str, list[RecapConversation]]] = [
        ("Channels", grouped["streams"]),
        ("Direct Messages", grouped["pms"]),
        ("Group Direct Messages", grouped["huddles"]),
    ]

    sections: list[RecapSection] = []
    for title, conversations in section_specs:
        if not conversations:
            continue

        raw_summary = summarize_section_with_retry(conversations)
        if raw_summary is None:
            # Rate-limited past our retry budget. Degrade just this
            # section rather than failing the whole recap.
            sections.append(
                RecapSection(
                    title=title,
                    html="<p>Summary unavailable right now. Please try again shortly.</p>",
                )
            )
            continue

        message_lookup = build_message_lookup(conversations)
        linked_summary = linkify_citations(raw_summary, user_profile.realm, message_lookup)
        rendered_html = markdown_convert(
            linked_summary, message_realm=user_profile.realm
        ).rendered_content
        sections.append(RecapSection(title=title, html=rendered_html))

    return RecapResult(sections=sections, truncated=grouped["truncated"])
