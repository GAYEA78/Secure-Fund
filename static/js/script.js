document.addEventListener("DOMContentLoaded", function () {
  var root = document.documentElement;

  document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
    button.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch (e) {}
      document.dispatchEvent(new CustomEvent("themechange", { detail: next }));
    });
  });

  document.querySelectorAll("[data-file-input]").forEach(function (input) {
    var label = document.querySelector(input.getAttribute("data-file-input"));
    input.addEventListener("change", function () {
      if (label) { label.textContent = input.files.length ? input.files[0].name : ""; }
    });
  });

  document.querySelectorAll("[data-scroll-end]").forEach(function (el) {
    el.scrollTop = el.scrollHeight;
  });

  document.querySelectorAll("[data-sum]").forEach(function (form) {
    var output = form.querySelector("[data-sum-output]");
    var inputs = form.querySelectorAll("[data-sum-input]");
    function update() {
      var total = 0;
      inputs.forEach(function (input) {
        var value = parseFloat(String(input.value).replace(",", "."));
        if (!isNaN(value)) { total += value; }
      });
      output.textContent = total.toFixed(2) + "%";
      output.classList.toggle("neg", Math.abs(total - 100) > 0.01);
    }
    inputs.forEach(function (input) { input.addEventListener("input", update); });
    update();
  });

  document.querySelectorAll("textarea[data-submit-on-enter]").forEach(function (area) {
    area.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        if (area.value.trim()) { area.form.requestSubmit(); }
      }
    });
  });
});