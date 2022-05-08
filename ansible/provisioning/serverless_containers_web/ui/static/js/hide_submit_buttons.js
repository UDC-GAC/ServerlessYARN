/* Based on https://stackoverflow.com/questions/8685107/hiding-a-button-in-javascript */


function hide_buttons(structure_name) {
    var submit_buttons = document.getElementsByName('save-resources-' + structure_name)

    for (let i = 0; i < (submit_buttons.length - 1); i++) {
        submit_buttons[i].style.visibility = 'hidden';
    } 

    console.log(submit_buttons)
}


