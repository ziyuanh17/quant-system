/* Quant System Web Console — Client-side logic */

(function () {
     "use strict";

     /* Status badge rendering */

     function statusBadge(state) {
          var cls = "badge badge-" + state.replace(/\s+/g, "_");
          return '<span class="' + cls + '">' + state + "</span>";
     }

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
          data.accountLanes.forEach(function (lane) {
               rows +=
                    "<tr>" +
                    "<td>" + lane.environment + "</td>" +
                    "<td>" + statusBadge(lane.connection.state) + "</td>" +
                    "<td>" + lane.permission + "</td>" +
                    "<td>" + statusBadge(lane.reconciliation.state) + "</td>" +
                    "<td class='mono'>" + lane.openOrders + "</td>" +
                    "<td class='mono'>" + lane.positions + "</td>" +
                    "<td>" + freshnessLabel(lane.freshness.age) + "</td>" +
                    "</tr>";
          });
          body.innerHTML = rows || "<tr><td colspan='7'>No accounts configured</td></tr>";
     }

     /* Boot */

     document.addEventListener("DOMContentLoaded", function () {
          loadOverview();

          /* Auto-refresh every 60 seconds */
          setInterval(loadOverview, 60_000);
     });
})();
