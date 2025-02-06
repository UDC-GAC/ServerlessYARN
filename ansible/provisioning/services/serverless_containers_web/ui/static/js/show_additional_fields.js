$(document).ready(function(){
    var add_files_dir_conditions = document.getElementsByClassName('add_files_dir_condition');
    var add_install_conditions = document.getElementsByClassName('add_install_condition');
    var additional_files_dirs = document.getElementsByClassName('additional_files_dir');
    var additional_installs = document.getElementsByClassName('additional_install');
    var add_extra_framework_conditions = document.getElementsByClassName('add_extra_framework_condition');
    var frameworks = document.getElementsByClassName('framework');

    for (var i=0; i < add_files_dir_conditions.length; i++ ){add_files_dir_conditions[i].checked = false;}
    for (var i=0; i < add_install_conditions.length; i++ ){add_install_conditions[i].checked = false;}
    for (var i=0; i < add_extra_framework_conditions.length; i++ ){add_extra_framework_conditions[i].checked = false;}

    for (var i=0; i < additional_files_dirs.length; i++ ){$(additional_files_dirs[i].parentElement.parentElement).hide();}
    for (var i=0; i < additional_installs.length; i++ ){$(additional_installs[i].parentElement.parentElement).hide();}
    for (var i=0; i < frameworks.length; i++ ){$(frameworks[i].parentElement.parentElement).hide();}


    // files directory
    for (let i=0; i < add_files_dir_conditions.length; i++ ){
        $(add_files_dir_conditions[i]).change(function() {
            for (let j=0; j < additional_files_dirs.length; j++ ){
                if (add_files_dir_conditions[i].checked){
                    $(additional_files_dirs[j].parentElement.parentElement).show()
                }
                else {
                    $(additional_files_dirs[j].parentElement.parentElement).hide()
                }
            };
        });
    };

    // install script
    for (let i=0; i < add_install_conditions.length; i++ ){
        $(add_install_conditions[i]).change(function() {
            for (let j=0; j < additional_installs.length; j++ ){
                if (add_install_conditions[i].checked){
                    $(additional_installs[j].parentElement.parentElement).show()
                }
                else {
                    $(additional_installs[j].parentElement.parentElement).hide()
                }
            };
        });
    };

    // extra framework for Hadoop apps
    for (let i=0; i < add_extra_framework_conditions.length; i++ ){
        $(add_extra_framework_conditions[i]).change(function() {
            for (let j=0; j < frameworks.length; j++ ){
                if (add_extra_framework_conditions[i].checked){
                    $(frameworks[j].parentElement.parentElement).show()
                }
                else {
                    $(framework[j].parentElement.parentElement).hide()
                }
            };
        });
    };

});
