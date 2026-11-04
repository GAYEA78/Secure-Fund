(function () {
  var root = document.documentElement;
  var CHART_SRC = "https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.js";
  var charts = [];
  var performanceCache = null;
  var busy = false;
  var bar = null;
  var barTimer = null;

  function css(name) {
    return getComputedStyle(root).getPropertyValue(name).trim();
  }

  function money(v, signed) {
    var n = Number(v) || 0;
    var text = "$" + Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (!signed) { return (n < 0 ? "\u2212" : "") + text; }
    return (n > 0 ? "+" : n < 0 ? "\u2212" : "") + text;
  }

  function alpha(hex, a) {
    var h = hex.replace("#", "");
    if (h.length === 3) { h = h.split("").map(function (c) { return c + c; }).join(""); }
    var n = parseInt(h, 16);
    return "rgba(" + ((n >> 16) & 255) + "," + ((n >> 8) & 255) + "," + (n & 255) + "," + a + ")";
  }

  function readJSON(id) {
    var el = document.getElementById(id);
    if (!el) { return null; }
    try { return JSON.parse(el.textContent); } catch (e) { return null; }
  }

  function shortDate(iso) {
    var d = new Date(iso + "T12:00:00");
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }

  function longDate(iso) {
    var d = new Date(iso + "T12:00:00");
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }

  function withChart(callback) {
    if (window.Chart) { callback(); return; }
    var script = document.querySelector("script[data-chart-lib]");
    if (!script) {
      script = document.createElement("script");
      script.src = CHART_SRC;
      script.setAttribute("data-chart-lib", "");
      document.head.appendChild(script);
    }
    script.addEventListener("load", callback, { once: true });
  }

  function destroyCharts() {
    charts.forEach(function (c) { c.destroy(); });
    charts = [];
  }

  function chartDefaults() {
    Chart.defaults.font.family = css("--font");
    Chart.defaults.font.size = 12;
    Chart.defaults.color = css("--muted");
  }

  function drawAllocation() {
    var canvas = document.getElementById("allocation-chart");
    if (!canvas) { return; }
    var palette = ["--chart-1", "--chart-2", "--chart-3", "--chart-4", "--chart-5", "--chart-6"].map(css);
    charts.push(new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: readJSON("allocation-labels") || [],
        datasets: [{ data: readJSON("allocation-values") || [], backgroundColor: palette, borderColor: css("--surface"), borderWidth: 2 }]
      },
      options: {
        maintainAspectRatio: false,
        cutout: "68%",
        animation: false,
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 10, boxHeight: 10, padding: 14 } },
          tooltip: { callbacks: { label: function (ctx) { return " " + ctx.label + "  " + money(ctx.parsed); } } }
        }
      }
    }));
  }

  function drawPerformance(data) {
    var panel = document.querySelector("[data-performance]");
    var canvas = document.getElementById("performance-chart");
    if (!panel || !canvas || !data) { return; }

    var total = panel.querySelector("[data-perf-total]");
    var since = panel.querySelector("[data-perf-since]");
    var empty = panel.querySelector("[data-perf-empty]");
    var box = canvas.parentElement;

    if (!data.labels || !data.labels.length) {
      total.textContent = "";
      since.textContent = "Starts with your first trade.";
      box.hidden = true;
      empty.hidden = false;
      return;
    }

    var last = data.gain[data.gain.length - 1];
    total.textContent = money(last, true);
    total.className = "perf-figure " + (last > 0 ? "pos" : last < 0 ? "neg" : "");
    since.textContent = "Since your first trade on " + longDate(data.since);
    box.hidden = false;
    empty.hidden = data.labels.length > 1;

    var pos = css("--pos");
    var neg = css("--neg");
    var rule = css("--rule");

    charts.push(new Chart(canvas, {
      type: "line",
      data: {
        labels: data.labels,
        datasets: [{
          label: "Total gain",
          data: data.gain,
          borderWidth: 2,
          borderColor: last >= 0 ? pos : neg,
          segment: {
            borderColor: function (ctx) { return ctx.p1.parsed.y >= 0 ? pos : neg; }
          },
          fill: { target: "origin", above: alpha(pos, 0.12), below: alpha(neg, 0.12) },
          pointRadius: data.labels.length > 40 ? 0 : 2,
          pointHoverRadius: 4,
          pointBackgroundColor: last >= 0 ? pos : neg,
          tension: 0.25
        }]
      },
      options: {
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: function (items) { return longDate(items[0].label); },
              label: function (ctx) {
                var i = ctx.dataIndex;
                return [
                  " Gain  " + money(data.gain[i], true),
                  " Holdings  " + money(data.value[i]),
                  " Net invested  " + money(data.invested[i])
                ];
              }
            }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            border: { color: rule },
            ticks: { maxTicksLimit: 7, autoSkip: true, maxRotation: 0, callback: function (v) { return shortDate(this.getLabelForValue(v)); } }
          },
          y: {
            grid: { color: function (ctx) { return ctx.tick.value === 0 ? css("--rule-strong") : rule; } },
            border: { display: false },
            ticks: { maxTicksLimit: 6, callback: function (v) { return money(v, true); } }
          }
        }
      }
    }));
  }

  function loadPerformance() {
    var panel = document.querySelector("[data-performance]");
    if (!panel) { return; }
    var src = panel.getAttribute("data-src");
    fetch(src, { credentials: "same-origin", headers: { "Accept": "application/json" } })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        if (!data || !panel.isConnected) { return; }
        performanceCache = data;
        withChart(function () { chartDefaults(); drawPerformance(data); });
      })
      .catch(function () {
        var since = panel.querySelector("[data-perf-since]");
        if (since) { since.textContent = "Couldn't load price history. Refresh to try again."; }
      });
  }

  function drawCharts(useCache) {
    destroyCharts();
    var needsChart = document.getElementById("allocation-chart") || document.getElementById("performance-chart");
    if (!needsChart) { return; }
    withChart(function () {
      chartDefaults();
      drawAllocation();
      if (useCache && performanceCache) { drawPerformance(performanceCache); }
    });
    if (!useCache) { loadPerformance(); }
  }

  function updateSums() {
    document.querySelectorAll("[data-sum]").forEach(function (form) {
      var output = form.querySelector("[data-sum-output]");
      if (!output) { return; }
      var total = 0;
      form.querySelectorAll("[data-sum-input]").forEach(function (input) {
        var value = parseFloat(String(input.value).replace(",", "."));
        if (!isNaN(value)) { total += value; }
      });
      output.textContent = total.toFixed(2) + "%";
      output.classList.toggle("neg", Math.abs(total - 100) > 0.01);
    });
  }

  function init() {
    document.querySelectorAll("[data-scroll-end]").forEach(function (el) { el.scrollTop = el.scrollHeight; });
    updateSums();
    drawCharts(false);
  }

  function progressStart() {
    if (!bar) {
      bar = document.createElement("div");
      bar.className = "progress";
      root.appendChild(bar);
    }
    clearTimeout(barTimer);
    bar.style.transition = "none";
    bar.style.opacity = "1";
    bar.style.width = "0";
    void bar.offsetWidth;
    bar.style.transition = "";
    bar.style.width = "35%";
    barTimer = setTimeout(function () { bar.style.width = "75%"; }, 400);
  }

  function progressDone() {
    if (!bar) { return; }
    clearTimeout(barTimer);
    bar.style.width = "100%";
    barTimer = setTimeout(function () { bar.style.opacity = "0"; }, 200);
  }

  function swapBody(doc) {
    destroyCharts();
    document.title = doc.title;
    document.body.replaceChildren.apply(document.body, Array.prototype.slice.call(doc.body.childNodes));
  }

  function visit(url, options) {
    options = options || {};
    if (busy) { return; }
    busy = true;
    progressStart();
    var scrollY = window.scrollY;
    var startPath = location.pathname;

    fetch(url, {
      method: options.method || "GET",
      body: options.body || null,
      credentials: "same-origin",
      headers: { "Accept": "text/html" }
    })
      .then(function (res) {
        var type = res.headers.get("content-type") || "";
        if (type.indexOf("text/html") === -1) {
          window.location.href = res.url || url;
          return null;
        }
        return res.text().then(function (html) { return { html: html, url: res.url || url, redirected: res.redirected }; });
      })
      .then(function (result) {
        if (!result) { return; }
        var doc = new DOMParser().parseFromString(result.html, "text/html");
        var finalUrl = new URL(result.url, location.href);
        swapBody(doc);
        var moved = (options.method || "GET") === "GET" || result.redirected;
        if (options.push !== false && moved && finalUrl.href !== location.href) {
          history.pushState({ live: true }, "", finalUrl.href);
        }
        var samePage = finalUrl.pathname === startPath;
        window.scrollTo(0, samePage && options.keepScroll ? scrollY : 0);
        init();
      })
      .catch(function () {
        if (options.form) {
          HTMLFormElement.prototype.submit.call(options.form);
        } else {
          window.location.href = url;
        }
      })
      .then(function () {
        busy = false;
        progressDone();
      });
  }

  function liveForm(form) {
    if (form.hasAttribute("data-no-live")) { return false; }
    if (form.target && form.target !== "_self") { return false; }
    var action = new URL(form.getAttribute("action") || location.href, location.href);
    return action.origin === location.origin;
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (event.defaultPrevented || !liveForm(form)) { return; }
    event.preventDefault();
    if (busy) { return; }

    var submitter = event.submitter || null;
    var data = new FormData(form);
    if (submitter && submitter.name) { data.append(submitter.name, submitter.value); }
    var method = (form.getAttribute("method") || "get").toUpperCase();
    var action = new URL(form.getAttribute("action") || location.href, location.href);

    if (submitter) {
      submitter.disabled = true;
      submitter.setAttribute("aria-busy", "true");
    }

    if (method === "GET") {
      action.search = new URLSearchParams(data).toString();
      visit(action.href, { method: "GET", keepScroll: true, form: form });
    } else {
      visit(action.href, { method: "POST", body: data, keepScroll: true, form: form });
    }
  });

  document.addEventListener("click", function (event) {
    var toggle = event.target.closest("[data-theme-toggle]");
    if (toggle) {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("theme", next); } catch (e) {}
      drawCharts(true);
      return;
    }

    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) { return; }
    var link = event.target.closest("a[href]");
    if (!link || link.hasAttribute("data-no-live") || link.hasAttribute("download")) { return; }
    if (link.target && link.target !== "_self") { return; }
    var url = new URL(link.href, location.href);
    if (url.origin !== location.origin) { return; }
    if (url.pathname.indexOf("/media/") === 0 || url.pathname.indexOf("/admin/") === 0) { return; }
    if (url.hash && url.pathname === location.pathname && url.search === location.search) { return; }
    event.preventDefault();
    visit(url.href, { method: "GET" });
  });

  document.addEventListener("input", function (event) {
    if (event.target.matches("[data-sum-input]")) { updateSums(); }
  });

  document.addEventListener("change", function (event) {
    var input = event.target;
    if (!input.matches("[data-file-input]")) { return; }
    var label = document.querySelector(input.getAttribute("data-file-input"));
    if (label) { label.textContent = input.files.length ? input.files[0].name : ""; }
  });

  document.addEventListener("keydown", function (event) {
    var area = event.target;
    if (!area.matches || !area.matches("textarea[data-submit-on-enter]")) { return; }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (area.value.trim()) { area.form.requestSubmit(); }
    }
  });

  window.addEventListener("popstate", function () {
    visit(location.href, { method: "GET", push: false });
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();