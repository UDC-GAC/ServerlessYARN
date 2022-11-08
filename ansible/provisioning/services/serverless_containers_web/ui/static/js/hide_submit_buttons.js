/* Based on https://stackoverflow.com/questions/8685107/hiding-a-button-in-javascript */

function hide_resources_submit_buttons(structure_name) {
    var submit_buttons = document.getElementsByName('save-resources-' + structure_name)

    for (let i = 0; i < (submit_buttons.length - 1); i++) {
        submit_buttons[i].style.visibility = 'hidden';
    } 

    console.log(submit_buttons)
}

function hide_addNContainers_submit_buttons() {
    var submit_buttons = document.getElementsByName('save-containers')

    for (let i = 0; i < (submit_buttons.length - 1); i++) {
        submit_buttons[i].style.visibility = 'hidden';
    } 

    console.log(submit_buttons)
}

