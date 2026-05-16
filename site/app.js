async function loadProgress() {
  const response = await fetch("progress.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Could not load progress.json: ${response.status}`);
  }
  return response.json();
}

async function loadStatus() {
  const response = await fetch("status.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Could not load status.json: ${response.status}`);
  }
  return response.json();
}

function setText(id, value) {
  document.getElementById(id).textContent = value;
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  return String(value).replaceAll("_", " ");
}

function renderSummary(progress) {
  setText("project-name", progress.project.name);
  setText("project-description", progress.project.description);
  setText("updated", `Updated ${progress.project.updated}`);
  setText("done-count", progress.summary.done);
  setText("review-count", progress.summary.in_review);
  setText("planned-count", progress.summary.planned);
  setText("next-step", progress.summary.next);
}

function renderMilestones(progress) {
  const timeline = document.getElementById("timeline");
  timeline.innerHTML = "";

  for (const milestone of progress.milestones) {
    const row = document.createElement("article");
    row.className = "milestone";

    const order = document.createElement("div");
    order.className = "order";
    order.textContent = `#${milestone.order}`;

    const summary = document.createElement("div");
    const name = document.createElement("div");
    name.className = "name";
    name.textContent = milestone.name;
    const badge = document.createElement("span");
    badge.className = `badge ${milestone.status}`;
    badge.textContent = formatValue(milestone.status);
    summary.appendChild(name);
    summary.appendChild(badge);

    const purpose = document.createElement("p");
    purpose.className = "purpose";
    purpose.textContent = milestone.purpose;

    row.appendChild(order);
    row.appendChild(summary);
    row.appendChild(purpose);

    timeline.appendChild(row);
  }
}

function renderFutureMetrics(progress) {
  const list = document.getElementById("future-metrics");
  list.innerHTML = "";
  for (const item of progress.futureMetrics) {
    const li = document.createElement("li");
    li.textContent = item;
    list.appendChild(li);
  }
}

function renderStatus(status) {
  const panel = document.getElementById("status-panel");
  panel.className = `status-panel ${status.status}`;
  setText("status-generated", `Generated ${formatValue(status.generated_at)}`);
  setText("health-status", formatValue(status.status));
  setText("latest-run-status", formatValue(status.latest_run_status));
  setText("lock-status", formatValue(status.lock_status));
  setText(
    "reconciliation-status",
    formatValue(status.reconciliation_status),
  );
  setText("comparison-status", formatValue(status.comparison_status));

  const issues = document.getElementById("status-issues");
  issues.innerHTML = "";
  if (!status.issues || status.issues.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "No current issues.";
    issues.appendChild(empty);
    return;
  }

  for (const issue of status.issues) {
    const item = document.createElement("article");
    item.className = `issue ${issue.severity}`;
    const code = document.createElement("strong");
    code.textContent = issue.code;
    const severity = document.createElement("span");
    severity.textContent = formatValue(issue.severity);
    const message = document.createElement("p");
    message.textContent = issue.message;
    item.appendChild(code);
    item.appendChild(severity);
    item.appendChild(message);
    issues.appendChild(item);
  }
}

function renderStatusError(error) {
  setText("status-generated", error.message);
  setText("health-status", "unknown");
  setText("latest-run-status", "n/a");
  setText("lock-status", "n/a");
  setText("reconciliation-status", "n/a");
  setText("comparison-status", "n/a");
}

loadProgress()
  .then((progress) => {
    renderSummary(progress);
    renderMilestones(progress);
    renderFutureMetrics(progress);
  })
  .catch((error) => {
    setText("project-name", "Quant System");
    setText("project-description", error.message);
  });

loadStatus().then(renderStatus).catch(renderStatusError);
