from ui.utils import request_to_state_db

def processRulesPost(request, url, rule_name, field, field_put_url):
    full_url = url + rule_name + "/" + field_put_url
    new_value = request.POST[field]
    error = ""
    if new_value != '':
        put_field_data = {'value': new_value}
        if field_put_url == "events_required":
            if field == "up_events_required":
                event_type = "up"
            else:
                event_type = "down"

            put_field_data['event_type'] = event_type

        error_message = "Error submitting {0} for rule {1}".format(field, rule_name)
        error, _ = request_to_state_db(full_url, "put", error_message, put_field_data)

    return error