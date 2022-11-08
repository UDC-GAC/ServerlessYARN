// Based on https://www.w3schools.com/howto/howto_js_accordion.asp

var acc = document.getElementsByClassName("accordion");
var i;

for (i = 0; i < acc.length; i++) {
  acc[i].addEventListener("click", function() {
    this.classList.toggle("active");

    var panel = this.nextElementSibling;
    while(panel.className != null && panel.className != "panel") {
      panel = panel.nextElementSibling;
    }
    
    if (panel.className != null) {
      if (panel.style.maxHeight) {
        panel.style.maxHeight = null;
      } else {
        panel.style.maxHeight = panel.scrollHeight + "px";
      }
  
      parent = this.parentNode
      while ( parent.className == "panel") {
        parent.style.maxHeight = parent.scrollHeight + panel.scrollHeight + "px";
        parent = parent.parentNode
      }  
    }
  });
}
