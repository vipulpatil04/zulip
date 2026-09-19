import {$} from "jquery";
import * as z from "zod/mini";

import render_message_recap from "../templates/message_recap.hbs";

import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t} from "./i18n.ts";
import * as rendered_markdown from "./rendered_markdown.ts";

const recap_response_schema = z.object({
    sections: z.array(
        z.object({
            title: z.string(),
            html: z.string(),
        }),
    ),
    truncated: z.boolean(),
});

function open_recap_modal(): void {
    dialog_widget.launch({
        modal_title_text: $t({defaultMessage: "Recap of unread messages"}),
        modal_content_html: "<div></div>", // TODO: Add a loading indicator here instead of a placeholder.
        close_on_submit: true,
        id: "message-recap-modal",
        footer_minor_text: $t({defaultMessage: "AI summaries may have errors."}),
        modal_submit_button_text: $t({defaultMessage: "Close"}),
        on_click() {
            // Just close the modal; there is nothing else to do.
        },
        single_footer_button: true,
        on_show() {
            $("#message-recap-modal .modal__content").addClass("hide");
        },
        post_render() {
            const close_on_success = false;
            dialog_widget.submit_api_request(
                channel.get,
                "/json/messages/recap",
                {},
                {
                    success_continuation(response_data) {
                        const data = recap_response_schema.parse(response_data);
                        const recap_html = render_message_recap({
                            sections: data.sections,
                            truncated: data.truncated,
                        });
                        $("#message-recap-modal .modal__content")
                            .removeClass("hide")
                            .addClass("rendered_markdown");
                        $("#message-recap-modal .modal__content").html(recap_html);
                        rendered_markdown.update_elements(
                            $("#message-recap-modal .modal__content"),
                        );
                    },
                },
                close_on_success,
            );
        },
    });
}

export function initialize(): void {
    $(document).on("click", ".recap-unread-messages-link", () => {
        open_recap_modal();
    });
}
