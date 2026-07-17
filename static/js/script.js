// static/js/script.js

document.addEventListener('DOMContentLoaded', function() {
  const tabs = document.querySelectorAll('.tabs button');
  const contents = document.querySelectorAll('.tab-content');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {

      tabs.forEach(t => t.classList.remove('active'));
      contents.forEach(c => c.classList.remove('active'));


      tab.classList.add('active');
      document.getElementById(tab.dataset.tab).classList.add('active');
    });
  });


  if (tabs.length > 0) {
    tabs[0].classList.add('active');
    const first = document.getElementById(tabs[0].dataset.tab);
    if (first) first.classList.add('active');
  }

 const toggle = document.getElementById('darkToggle');
 const container = document.querySelector('.dashboard-container');
 if (toggle && container) {
   toggle.addEventListener('click', (e) => {
     e.preventDefault();
     container.classList.toggle('dark-mode');
   });
 }

});
