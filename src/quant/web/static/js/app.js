/* Quant System Web Console — Client-side logic */

(function () {
     "use strict";

    var nativeFetch = window.fetch.bind(window);
    var authPrompt = null;

    window.quantEscapeHtml = function (value) {
         return String(value ?? "").replace(/[&<>"']/g, function (character) {
              return {
                    "&": "&amp;",
                    "<": "&lt;",
                    ">": "&gt;",
                    '"': "&quot;",
                    "'": "&#039;"
               }[character];
           });
       };

    window.fetch = function (resource, options) {
         var requestOptions = Object.assign({}, options || {});
         var headers = new Headers(requestOptions.headers || {});
         var key = sessionStorage.getItem("quantConsoleApiKey");
         if (key && String(resource).startsWith("/api/v1/")) {
              headers.set("Authorization", "Bearer " + key);
           }
         requestOptions.headers = headers;

         return nativeFetch(resource, requestOptions).then(function (response) {
              if (response.status !== 401 || !String(resource).startsWith("/api/v1/")) {
                   return response;
               }
              if (!authPrompt) {
                   authPrompt = Promise.resolve(
                        window.prompt("Quant console API key")
                     ).finally(function () {
                        authPrompt = null;
                     });
               }
              return authPrompt.then(function (enteredKey) {
                   if (!enteredKey) {
                        return response;
                    }
                    sessionStorage.setItem("quantConsoleApiKey", enteredKey);
                    headers.set("Authorization", "Bearer " + enteredKey);
                    return nativeFetch(resource, requestOptions);
                 });
             });
         };

    /* Status badge rendering */

    function statusBadge(state) {
         var cls = "badge badge-" + (state || "unknown").replace(/\s+/g, "_");
         return '<span class="' + cls + '">' + (state || "unknown") + "</span>";
    }

    /* Expose shared helpers for page templates */

    window.quantRenderStatus = statusBadge;

    window.quantFadeIn = function (el, delay) {
         if (!el) return;
         el.style.opacity = "0";
         el.style.transition = "opacity 300ms ease";
         setTimeout(function () {
              el.style.opacity = "1";
            }, delay || 0);
        };

    window.quantShowLoading = function (tbodyId) {
         var body = document.getElementById(tbodyId);
         if (body) {
              body.innerHTML = '<tr><td colspan="100%" style="text-align:center;color:var(--text-tertiary);padding:24px;">Loading...</td></tr>';
            }
        };

    /* Freshness indicator */

    function freshnessLabel(ageSeconds) {
         if (ageSeconds === null || ageSeconds === undefined) {
              return "<span class='text-secondary'>unknown</span>";
           }
         if (ageSeconds < 60) {
              return ageSeconds + "s ago";
           }
         if (ageSeconds < 3600) {
              return Math.floor(ageSeconds / 60) + "m ago";
           }
         return Math.floor(ageSeconds / 3600) + "h ago";
    }

    /* Top bar update */

    function updateTopBar(data) {
         var statusEl = document.getElementById("overall-status");
         var freshnessEl = document.getElementById("topbar-freshness");
         if (statusEl && data) {
              statusEl.textContent = data.system
                     ? data.system.tradingPermission || "unknown"
                     : "no data";
              statusEl.className =
                     "topbar-status status-" +
                     (data.system
                          ? data.system.serverStatus?.state || "unknown"
                          : "unknown");
           }
         if (freshnessEl && data) {
              var now = Date.now() / 1000;
              var generated = data.schema
                     ? new Date(data.schema.generatedAt || now * 1000)
                     : new Date();
              freshnessEl.textContent = freshnessLabel(now - generated.getTime() / 1000);
           }
    }

    /* Fetch and render overview */

    function loadOverview() {
         fetch("/api/v1/overview")
                .then(function (res) { return res.json(); })
                .then(function (data) {
                   updateTopBar(data);
                   renderAccountLanes(data);
                })
                .catch(function () {
                   updateTopBar(null);
                });
    }

    /* Render account lanes table */

    function renderAccountLanes(data) {
         var body = document.getElementById("account-lanes-body");
         if (!body || !data || !data.accountLanes) {
              return;
           }
         var rows = "";
         var isMobile = window.innerWidth <= 768;
         data.accountLanes.forEach(function (lane, i) {
              var attrs = isMobile
                   ? ' data-label="' + lane.environment + '"'
                   : "";
              rows +=
                     "<tr" + attrs + ">" +
                     "<td" + (isMobile ? "" : " class='mono'") + ">" + lane.environment + "</td>" +
                     "<td" + (isMobile ? "" : " class='mono'") + ">" + statusBadge(lane.connection.state) + "</td>" +
                     "<td" + (isMobile ? "" : " class='mono'") + ">" + lane.permission + "</td>" +
                     "<td" + (isMobile ? "" : " class='mono'") + ">" + statusBadge(lane.reconciliation.state) + "</td>" +
                     "<td class='mono'>" + lane.openOrders + "</td>" +
                     "<td class='mono'>" + lane.positions + "</td>" +
                     "<td>" + freshnessLabel(lane.freshness.age) + "</td>" +
                     "</tr>";
           });
         body.innerHTML = rows || "<tr><td colspan='7'>No accounts configured</td></tr>";
    }

    /* Theme toggle */

    (function initTheme() {
         var STORAGE_KEY = "quantTheme";
         var html = document.documentElement;
         var toggle = document.getElementById("theme-toggle");

             /* Determine initial theme */
         var saved = sessionStorage.getItem(STORAGE_KEY);
         var prefersLight = window.matchMedia("(prefers-color-scheme: light)").matches;
         var theme = saved || (prefersLight ? "light" : "dark");

             /* Apply theme */
         html.setAttribute("data-theme", theme);

             /* Toggle handler */
         if (toggle) {
              toggle.addEventListener("click", function () {
                   var current = html.getAttribute("data-theme");
                   var next = current === "light" ? "dark" : "light";
                   html.setAttribute("data-theme", next);
                   sessionStorage.setItem(STORAGE_KEY, next);
               });
          }

             /* Listen for system theme changes */
          window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", function (e) {
               if (!sessionStorage.getItem(STORAGE_KEY)) {
                    html.setAttribute("data-theme", e.matches ? "light" : "dark");
                }
           });
      })();

    /* Boot */

    document.addEventListener("DOMContentLoaded", function () {
         loadOverview();

             /* Auto-refresh every 60 seconds */
          setInterval(loadOverview, 60_000);
        });
})();
