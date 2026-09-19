# Implementation Notes

## Feature 1: Message Recap

**Backend.** `zerver/actions/message_recap.py` does the work in four steps:

1. `get_grouped_unread_messages()` calls Zulip's existing `get_raw_unread_data()` /
   `aggregate_unread_data()` (`zerver/lib/message.py`) to fetch and group the
   user's unreads into channel-topics, 1:1 DMs, and group DMs, then hydrates
   full content via `messages_for_ids()`. A `MAX_RECAP_MESSAGES = 150` cap
   bounds cost/latency for users with huge backlogs; a `truncated` flag is
   returned when it kicks in.
2. `summarize_section()` sends one LLM call per section (channels / DMs /
   group DMs), not per conversation. Each message in the prompt is tagged
   with its real database id, and the model is instructed to cite sources
   inline as `[#12345]`. Batching by section (3 calls total, not one per
   conversation) was a deliberate choice: Groq's free tier caps usage at
   8,000 tokens/minute, and one call per conversation repeats the fixed-size
   system prompt N times, burning that budget far faster than a few batched
   calls. The trade-off is weaker citation isolation (a call sees multiple
   conversations' ids at once), which the next step compensates for.
3. **Link creation (the graded detail):** `linkify_citations()` regex-matches
   citation tokens — tolerating `[14]`, `[#14]`, and `【14】`, since the model
   was inconsistent about the exact format across live test runs — and looks
   each id up in a `message_lookup` dict built from *only the messages sent
   in that section's call*. A match resolves to a real link via Zulip's own
   `message_link_url()` (`zerver/lib/url_encoding.py`), which already knows
   how to build both `#narrow/channel/<id>-<name>/topic/<topic>/near/<id>`
   and `#narrow/dm/<ids>/near/<id>` URLs. An id that isn't in the lookup
   (hallucinated, or leaked from a different section) is silently dropped
   instead of becoming a broken or misleading link — verified with a test
   that injects a fake id and asserts it never appears in the output.
4. `do_recap_unread_messages()` assembles the three sections, running each
   LLM call through `summarize_section_with_retry()`, which retries on any
   `openai.APIError` (rate limits, connection errors, timeouts alike) with
   exponential backoff, degrading just that section to "summary unavailable"
   rather than failing the whole request.

The view (`zerver/views/message_recap.py`) gates access behind the same
`can_summarize_topics()` permission and `TOPIC_SUMMARIZATION_MODEL`
configured-model check the existing per-topic summarizer uses, and is
registered at `GET /json/messages/recap` / `GET /api/v1/messages/recap` in
`zproject/urls.py`, and tested against the real Groq API
(`openai/gpt-oss-120b`), not mocked.

**Frontend.** A new "Recap unread messages" item in the gear menu
(`web/templates/popovers/navbar/navbar_gear_menu_popover.hbs`, gated by the
same AI-features permission via new fields in
`web/src/popover_menus_data.ts`) opens a modal
(`web/src/message_recap.ts`, registered in `web/src/ui_init.js`) that calls
the endpoint and renders `web/templates/message_recap.hbs` — one heading and
one summary block per section, with an "all caught up" fallback when there
are no unreads. This closely mirrors Zulip's existing topic-summary modal
(`web/src/message_summary.ts`), reusing `dialog_widget` and
`rendered_markdown.update_elements()` so the generated citation links behave
like any other Zulip message link.

**Known limitations:** presented as a modal rather than a dedicated page
(a closer reading of "on a single page" from the assignment); the retry
logic is implemented but not exercised under a real sustained rate-limit;
truncation is implemented but not exercised with >150 real unreads.

**Demo video:** TODO — link to be added before submission.

## Feature 2: Topic Title Improver

**Backend.** Detection is triggered from `zerver/actions/message_send.py`
(`do_send_messages`), right alongside Zulip's existing `embed_links` queue
trigger, which we used as the template for this design. After a channel
message is sent, `messages_for_topic()` counts messages in that topic; on
an *exact* match to `TOPIC_DRIFT_CHECK_MESSAGE_THRESHOLD = 30` (not `>=`,
so it fires once per topic, not repeatedly), a `topic_drift_check` event is
queued via `queue_event_on_commit`. This keeps the check off the request
path entirely — sending a message never waits on an LLM call, which is the
main latency consideration for this feature.

`zerver/worker/topic_drift_check.py` (a `QueueProcessingWorker`, filename
matched to the queue name per Zulip's worker-discovery convention) consumes
the event and calls `check_topic_drift()` in `zerver/actions/topic_drift.py`,
which fetches the topic's messages and asks a smaller/faster model
(`openai/gpt-oss-20b`, vs. `gpt-oss-120b` for Feature 1's summaries) whether
the discussion has drifted and, if so, for a new title — the cost and
latency consideration for this feature: a fast model, called at most once
per topic, off the request path, rather than on every message. The model
is asked for strict JSON (`{"drifted": bool, "suggested_title": str}`);
`parse_drift_response()` extracts the first `{...}` block via regex and
validates its shape, treating anything unparseable as "no drift" rather
than crashing — the same defensive-parsing lesson learned from Feature 1's
inconsistent citation formatting. Verified live against both a boring
repetitive topic (correctly reports no drift) and a crafted scenario where
a "laptop battery" topic drifts into "team lunch planning" (correctly
suggests a new title).

On drift, `notify_admins_of_topic_drift()` sends a real-time event (custom
type `topic_drift_suggestion`) via `send_event_on_commit`, targeting only
realm admins/owners — a deliberate scope decision to treat this as a
moderation tool rather than a per-participant nudge. This was verified by
registering a real event queue via `/api/v1/register` as an admin user and
confirming the event actually arrives over `/api/v1/events`, not just by
calling the Python function directly.

**Frontend.** `web/src/server_events_dispatch.js` dispatches the new event
type to `web/src/topic_drift_banner.ts`, which shows a popup banner (reusing
Zulip's existing `banners`/`popup_banners` component, not custom UI) with
the suggested title and an "Apply" button. Apply calls the same
`PATCH /json/messages/<id>` endpoint the built-in topic-rename UI uses
(`topic`, `propagate_mode: "change_all"`), so no new rename logic was
written — verified that this exact call renames the topic.

**Scalability:** this reuses Zulip's existing queue-worker infrastructure
(the same pattern as `embed_links`), so it scales the same way Zulip's other
async post-send work already does, and the fixed one-check-per-topic policy
bounds LLM cost independent of topic length or traffic volume.

**Known limitations:** the 30-message threshold is a fixed constant, not
configurable per-realm; a topic that drifts a second time after 30 messages
won't be re-checked; malformed/absent JSON from the model is logged and
silently treated as "no suggestion" rather than retried.

**Demo video:** https://uofi.box.com/s/kumacovfar022zr2ae551hietearin42
