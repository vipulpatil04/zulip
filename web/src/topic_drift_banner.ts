import {$} from "jquery";

import * as banners from "./banners.ts";
import type {Banner} from "./banners.ts";
import * as channel from "./channel.ts";
import {$t} from "./i18n.ts";

export type TopicDriftSuggestion = {
    stream_id: number;
    topic_name: string;
    suggested_title: string;
    message_id: number;
};

const topic_drift_suggestion_banner = (suggestion: TopicDriftSuggestion): Banner => ({
    intent: "info",
    label: $t(
        {
            defaultMessage:
                'The topic "{old_title}" seems to have drifted. Suggested new title: "{new_title}"',
        },
        {old_title: suggestion.topic_name, new_title: suggestion.suggested_title},
    ),
    buttons: [
        {
            variant: "solid",
            label: $t({defaultMessage: "Apply"}),
            custom_classes: "topic-drift-apply",
        },
    ],
    close_button: true,
    custom_classes: "topic-drift-suggestion-banner popup-banner",
});

export function show_topic_drift_suggestion(suggestion: TopicDriftSuggestion): void {
    banners.append(topic_drift_suggestion_banner(suggestion), $("#popup_banners_wrapper"));

    $("#popup_banners_wrapper").on(
        "click",
        ".topic-drift-apply",
        function (this: HTMLElement, e) {
            e.preventDefault();
            e.stopPropagation();

            const $banner = $(this).closest(".banner");
            void channel.patch({
                url: "/json/messages/" + suggestion.message_id,
                data: {
                    propagate_mode: "change_all",
                    topic: suggestion.suggested_title,
                    send_notification_to_old_thread: false,
                    send_notification_to_new_thread: true,
                },
                success() {
                    banners.close($banner);
                },
            });
        },
    );
}
