
var cells = document.getElementsByTagName("td");

for (i = 0; i < cells.length; i++) {
    if (cells[i].innerText.includes('_')) {
        cells[i].innerText = cells[i].innerText.replaceAll('_', ' ');
    }
}
