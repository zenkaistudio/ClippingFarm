const STAGE_LABELS = {
  transcribe: "Transcribe",
  detect_moments: "Detect Moments",
  cut: "Cut",
  reframe: "Reframe",
  captions: "Captions",
};

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const numClipsInput = document.getElementById("num-clips");
const uploadFlash = document.getElementById("upload-flash");
const tally = document.getElementById("tally");

const processingEmpty = document.getElementById("processing-empty");
const processingActive = document.getElementById("processing-active");
const processingFilename = document.getElementById("processing-filename");
const tapeBar = document.getElementById("tape-bar");
const stageStatusLabel = document.getElementById("stage-status-label");
const stageTrack = document.getElementById("stage-track");
const errorLog = document.getElementById("error-log");
const errorLogMsg = document.getElementById("error-log-msg");

const queueList = document.getElementById("queue-list");
const galleryEmpty = document.getElementById("gallery-empty");
const gallery = document.getElementById("gallery");

let renderedCompletedIds = "";

document.getElementById("clips-dec").addEventListener("click", () => {
  numClipsInput.value = Math.max(1, parseInt(numClipsInput.value || "1", 10) - 1);
});
document.getElementById("clips-inc").addEventListener("click", () => {
  numClipsInput.value = Math.min(20, parseInt(numClipsInput.value || "1", 10) + 1);
});

dropzone.addEventListener("click", () => fileInput.click());

["dragenter", "dragover"].forEach((evt) => {
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("is-dragover");
  });
});

["dragleave", "dragend", "drop"].forEach((evt) => {
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("is-dragover");
  });
});

dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files && e.dataTransfer.files[0];
  if (file) uploadFile(file);
});

fileInput.addEventListener("change", () => {
  const file = fileInput.files && fileInput.files[0];
  if (file) uploadFile(file);
  fileInput.value = "";
});

function flash(message, isError) {
  uploadFlash.textContent = message;
  uploadFlash.classList.toggle("error", !!isError);
  uploadFlash.classList.add("show");
  setTimeout(() => uploadFlash.classList.remove("show"), 3200);
}

function uploadFile(file) {
  const form = new FormData();
  form.append("video", file);
  form.append("num_clips", numClipsInput.value || "6");

  flash(`Uploading ${file.name}…`, false);

  fetch("/api/upload", { method: "POST", body: form })
    .then((res) => res.json().then((data) => ({ ok: res.ok, data })))
    .then(({ ok, data }) => {
      if (!ok) throw new Error(data.error || "Upload failed");
      flash(`Queued: ${file.name} (position ${data.position})`, false);
      poll();
    })
    .catch((err) => flash(err.message, true));
}

function renderTally(current) {
  tally.classList.remove("is-live", "is-idle");
  const label = tally.querySelector(".deck__tally-label");
  if (current && current.status === "in_progress") {
    tally.classList.add("is-live");
    label.textContent = "ON AIR";
  } else if (current) {
    tally.classList.add("is-idle");
    label.textContent = current.status === "error" ? "FAULT" : "IDLE";
  } else {
    label.textContent = "STANDBY";
  }
}

function renderProcessing(stages, current) {
  if (!current) {
    processingEmpty.classList.remove("hidden");
    processingActive.classList.add("hidden");
    return;
  }

  processingEmpty.classList.add("hidden");
  processingActive.classList.remove("hidden");
  processingFilename.textContent = current.filename;

  const activeIndex = stages.indexOf(current.stage);

  // tape bar: fills proportionally as stages complete
  const pct = current.status === "done"
    ? 100
    : current.status === "error"
      ? Math.round(((activeIndex) / stages.length) * 100)
      : Math.round(((activeIndex + 0.5) / stages.length) * 100);
  tapeBar.style.width = pct + "%";

  // status label
  if (current.status === "done") {
    stageStatusLabel.textContent = "all stages complete";
  } else if (current.status === "error") {
    stageStatusLabel.textContent = "stage fault — see error below";
  } else if (current.stage) {
    const stageMessages = {
      transcribe: "transcribing audio…",
      detect_moments: "detecting viral moments…",
      cut: "cutting clips…",
      reframe: "reframing to vertical…",
      captions: "burning captions…",
    };
    stageStatusLabel.textContent = stageMessages[current.stage] || current.stage + "…";
  }

  stageTrack.innerHTML = stages
    .map((stage, i) => {
      let cls = "";
      if (current.status === "error" && i === activeIndex) cls = "is-error";
      else if (i < activeIndex || (i === activeIndex && current.status === "done")) cls = "is-done";
      else if (i === activeIndex) cls = "is-active";
      else if (current.status === "done") cls = "is-done";
      return `<div class="track-step ${cls}">
                <div class="track-step__dot"></div>
                <div class="track-step__label">${STAGE_LABELS[stage] || stage}</div>
              </div>`;
    })
    .join("");

  if (current.status === "error" && current.error) {
    errorLog.classList.remove("hidden");
    errorLogMsg.textContent = current.error;
  } else {
    errorLog.classList.add("hidden");
  }
}

function renderQueue(queued) {
  if (!queued.length) {
    queueList.innerHTML = '<li class="queue-empty">Queue is clear.</li>';
    return;
  }
  queueList.innerHTML = queued
    .map(
      (job, i) => `<li><span class="queue-pos">${String(i + 1).padStart(2, "0")}</span>${job.filename}</li>`
    )
    .join("");
}

function renderGallery(completed) {
  const withClips = completed.filter((job) => job.clips && job.clips.length);
  const idSignature = withClips.map((j) => j.video_id).join(",");

  if (!withClips.length) {
    galleryEmpty.classList.remove("hidden");
    gallery.innerHTML = "";
    renderedCompletedIds = "";
    return;
  }
  galleryEmpty.classList.add("hidden");

  if (idSignature === renderedCompletedIds) return; // avoid re-render flicker/reload of <video>
  renderedCompletedIds = idSignature;

  gallery.innerHTML = withClips
    .map((job) => {
      const cards = job.clips
        .map(
          (clip) => `
        <div class="clip-card">
          <video src="/clips/${encodeURIComponent(clip.filename)}" muted loop playsinline preload="metadata"
                 onmouseover="this.play()" onmouseout="this.pause()"></video>
          <div class="clip-card__top">
            <span class="clip-badge badge-${clip.category || "other"}">${(clip.category || "other").replace(/_/g, " ")}</span>
            <span class="clip-score">${clip.virality_score ?? "—"}</span>
          </div>
          <div class="clip-card__bottom">
            <p class="clip-hook">${clip.hook_title || ""}</p>
            <div class="clip-actions">
              <a class="clip-download" href="/clips/${encodeURIComponent(clip.filename)}" download title="Download">&darr;</a>
              <button class="clip-schedule btn-schedule" data-filename="${clip.filename}" data-hook="${(clip.hook_title||"").replace(/"/g,"&quot;")}" data-category="${clip.category||"highlight"}">Schedule</button>
            </div>
          </div>
        </div>`
        )
        .join("");
      return `<div class="gallery-group">
                <div class="gallery-group__header">${job.filename}</div>
                <div class="gallery-row">${cards}</div>
              </div>`;
    })
    .join("");
}

function poll() {
  fetch("/api/status")
    .then((res) => res.json())
    .then((data) => {
      renderTally(data.current);
      renderProcessing(data.stages, data.current);
      renderQueue(data.queued);
      renderGallery(data.completed);
    })
    .catch(() => {});
}

poll();
setInterval(poll, 1500);

// Schedule button — event delegation so it works after gallery re-renders
document.addEventListener("click", (e) => {
  const btn = e.target.closest(".btn-schedule");
  if (!btn) return;

  const filename = btn.dataset.filename;
  const hookTitle = btn.dataset.hook;
  const category = btn.dataset.category;

  btn.disabled = true;
  btn.textContent = "Uploading…";

  fetch("/api/schedule", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename, hook_title: hookTitle, category }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.error) {
        btn.textContent = "Error";
        btn.title = data.error;
        btn.style.background = "#c0392b";
      } else {
        btn.textContent = "Scheduled ✓";
        btn.style.background = "#27ae60";
        btn.title = data.caption || "";
      }
    })
    .catch(() => {
      btn.textContent = "Failed";
      btn.style.background = "#c0392b";
    });
});
