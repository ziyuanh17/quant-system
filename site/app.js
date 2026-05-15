async function loadProgress() {
  const response = await fetch("progress.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Could not load progress.json: ${response.status}`);
  }
  return response.json();
}

function setText(id, value) {
  document.getElementById(id).textContent = value;
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

    row.innerHTML = `
      <div class="order">#${milestone.order}</div>
      <div>
        <div class="name">${milestone.name}</div>
        <span class="badge ${milestone.status}">${milestone.status.replace("_", " ")}</span>
      </div>
      <p class="purpose">${milestone.purpose}</p>
    `;

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
