function show_hide_field(conditions_to_check, fields_to_manage) {

    for (let i=0; i < conditions_to_check.length; i++ ){conditions_to_check[i].checked = false;}
    for (let i=0; i < fields_to_manage.length; i++ ){$(fields_to_manage[i].parentElement.parentElement).hide();}

    for (let i=0; i < conditions_to_check.length; i++ ){
        $(conditions_to_check[i]).change(function() {
            for (let j=0; j < fields_to_manage.length; j++ ){
                if (conditions_to_check[i].checked){
                    $(fields_to_manage[j].parentElement.parentElement).show()
                }
                else {
                    $(fields_to_manage[j].parentElement.parentElement).hide()
                }
            };
        });
    };
}

$(document).ready(function(){
    // install script
    var add_install_conditions = document.getElementsByClassName('add_install_condition');
    var additional_installs = document.getElementsByClassName('additional_install');
    // install files directory
    var add_install_files_conditions = document.getElementsByClassName('add_install_files_condition');
    var additional_install_files = document.getElementsByClassName('additional_install_files');
    // runtime files directory
    var add_runtime_files_conditions = document.getElementsByClassName('add_runtime_files_condition');
    var additional_runtime_files = document.getElementsByClassName('additional_runtime_files');
    // output directory
    var add_output_dir_conditions = document.getElementsByClassName('add_output_dir_condition');
    var additional_output_dir = document.getElementsByClassName('additional_output_dir');
    // extra framework for Hadoop apps
    var add_extra_framework_conditions = document.getElementsByClassName('add_extra_framework_condition');
    var frameworks = document.getElementsByClassName('framework');
    // read data from hdfs
    var read_from_global_conditions = document.getElementsByClassName('read_from_global_condition');
    var global_inputs = document.getElementsByClassName('global_input');
    var local_outputs = document.getElementsByClassName('local_output');
    // write data to hdfs
    var write_to_global_conditions = document.getElementsByClassName('write_to_global_condition');
    var local_inputs = document.getElementsByClassName('local_input');
    var global_outputs = document.getElementsByClassName('global_output');

    show_hide_field(add_install_conditions, additional_installs);
    show_hide_field(add_install_files_conditions, additional_install_files);
    show_hide_field(add_runtime_files_conditions, additional_runtime_files);
    show_hide_field(add_output_dir_conditions, additional_output_dir);
    show_hide_field(add_extra_framework_conditions, frameworks);
    show_hide_field(read_from_global_conditions, global_inputs);
    show_hide_field(read_from_global_conditions, local_outputs);
    show_hide_field(write_to_global_conditions, local_inputs);
    show_hide_field(write_to_global_conditions, global_outputs);
});
