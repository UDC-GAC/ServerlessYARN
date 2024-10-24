$(document).ready(function(){
    $("#div_id_files_dir").hide();
    $("#div_id_install_script").hide();
    document.getElementById('add_files_dir').checked = false;
    document.getElementById('add_install').checked = false;

    $("#add_install").change(function() {
        if ( document.getElementById('add_install').checked) {
            $("#div_id_install_script").show();
        }
        else{
            $("#div_id_install_script").hide();
        }
    });

    $("#add_files_dir").change(function() {
        if ( document.getElementById('add_files_dir').checked) {
            $("#div_id_files_dir").show();
        }
        else{
            $("#div_id_files_dir").hide();
        }
    });

});
