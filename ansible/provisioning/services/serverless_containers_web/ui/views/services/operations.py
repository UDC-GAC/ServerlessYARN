from ui.utils import request_to_state_db

def processServiceConfigPost(request, url, service_name, config_name):
    full_url = url + service_name + "/" + config_name.upper()
    json_fields = []
    multiple_choice_fields = ["guardable_resources","structures_persisted","resources_persisted","structures_refeeded",
                              "generated_metrics","documents_persisted","resources_balanced","structures_balanced"]

    error = ""
    error_message = "Error submiting {0} for service {1}".format(config_name, service_name)

    if config_name in json_fields:
        ## JSON field request (not used at the moment)
        new_value = request.POST[config_name]
        new_values_list = new_value.strip("[").strip("]").split(",")
        put_field_data = {"value":[v.strip().strip('"') for v in new_values_list]}
        error, _ = request_to_state_db(full_url, "put", error_message, put_field_data)

    elif config_name in multiple_choice_fields:
        ## MultipleChoice field request
        new_values_list = request.POST.getlist(config_name)
        put_field_data = {"value":[v.strip().strip('"') for v in new_values_list]}
        error, _ = request_to_state_db(full_url, "put", error_message, put_field_data)

    else:
        ## Other field request
        new_value = request.POST[config_name]

        if new_value != '':
            put_field_data = {'value': new_value.lower()}
            error, _ = request_to_state_db(full_url, "put", error_message, put_field_data)

    return error
