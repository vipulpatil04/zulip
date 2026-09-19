from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.actions.message_recap import do_recap_unread_messages
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.models import UserProfile


def get_messages_recap(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    if settings.TOPIC_SUMMARIZATION_MODEL is None:  # nocoverage
        raise JsonableError(_("AI features are not enabled on this server."))

    # Reuses the same permission gate as the existing topic summarizer,
    # since both features are "let an LLM read and summarize my messages"
    # and a realm that disables one presumably wants to disable the other.
    if not user_profile.can_summarize_topics():
        raise JsonableError(_("Insufficient permission"))

    recap = do_recap_unread_messages(user_profile)
    return json_success(request, {"sections": recap["sections"], "truncated": recap["truncated"]})
