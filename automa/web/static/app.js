/**
 * AUTOMA DASHBOARD CLIENT LOGIC
 * Interacts with localhost REST API and renders real-time queue states.
 */

document.addEventListener("DOMContentLoaded", () => {
  let allPosts = [];
  let currentFilter = "all";
  let currentPlatform = "";

  // DOM Elements
  const valScheduled = document.getElementById("val-scheduled");
  const valPublished = document.getElementById("val-published");
  const valReview = document.getElementById("val-review");
  const valRejected = document.getElementById("val-rejected");
  const modeText = document.getElementById("mode-text");
  const postsTableBody = document.getElementById("posts-table-body");
  const auditLogList = document.getElementById("audit-log-list");
  const reviewAlertSection = document.getElementById("review-alert-section");
  const reviewItemsContainer = document.getElementById("review-items-container");
  const reviewHeadline = document.getElementById("review-count-headline");

  const btnRefresh = document.getElementById("btn-refresh-data");
  const btnTriggerGenerate = document.getElementById("btn-trigger-generate");
  const btnTriggerPublish = document.getElementById("btn-trigger-publish");
  const selectPlatform = document.getElementById("select-platform-filter");
  const filterTabs = document.querySelectorAll(".tab-btn");

  const modal = document.getElementById("post-detail-modal");
  const btnCloseModal = document.getElementById("btn-close-modal");
  const btnModalDismiss = document.getElementById("btn-modal-dismiss");

  // Show Toast
  function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // Fetch Status and Metrics
  async function fetchStatus() {
    try {
      const res = await fetch("/api/status");
      if (!res.ok) throw new Error("Failed to reach server");
      const data = await res.json();

      valScheduled.textContent = data.queue_counts.SCHEDULED || 0;
      valPublished.textContent = data.queue_counts.PUBLISHED || 0;
      valReview.textContent = data.queue_counts.MANUAL_REVIEW_REQUIRED || 0;
      valRejected.textContent = data.queue_counts.REJECTED || 0;

      modeText.textContent = data.dry_run ? "DRY RUN ACTIVE" : `LIVE (${data.publisher_type.toUpperCase()})`;

      // Render recent audit logs
      if (data.recent_audit && data.recent_audit.length > 0) {
        auditLogList.innerHTML = data.recent_audit.map(item => `
          <div class="audit-item">
            <span class="audit-timestamp">${item.timestamp ? item.timestamp.substring(11, 19) : ''} UTC</span>
            <span class="audit-type">${item.event_type}</span>
            <span class="audit-details">${escapeHtml(item.details)}</span>
          </div>
        `).join("");
      } else {
        auditLogList.innerHTML = `<div class="audit-item"><span class="audit-details">No recent audit events.</span></div>`;
      }
    } catch (err) {
      console.error("Error fetching status:", err);
    }
  }

  // Fetch Posts
  async function fetchPosts() {
    try {
      const res = await fetch("/api/posts");
      if (!res.ok) throw new Error("Failed to load posts");
      allPosts = await res.json();
      renderFilteredPosts();
      checkManualReviews();
    } catch (err) {
      postsTableBody.innerHTML = `<tr><td colspan="6" class="empty-state">Failed to load posts from storage.</td></tr>`;
    }
  }

  // Filter and Render Posts
  function renderFilteredPosts() {
    let filtered = allPosts;
    if (currentFilter !== "all") {
      filtered = filtered.filter(p => p.status === currentFilter);
    }
    if (currentPlatform) {
      filtered = filtered.filter(p => p.platform === currentPlatform);
    }

    if (filtered.length === 0) {
      postsTableBody.innerHTML = `<tr><td colspan="6" class="empty-state">No posts found matching the current filter.</td></tr>`;
      return;
    }

    postsTableBody.innerHTML = filtered.map(post => {
      const dateDisplay = post.scheduled_at ? post.scheduled_at.replace("T", " ").substring(0, 16) : "—";
      const scoreClass = post.quality_score >= 85 ? "score-pass" : "score-fail";
      const preview = escapeHtml(post.content ? post.content.substring(0, 120) : "");

      return `
        <tr>
          <td><span class="badge badge-${post.platform}">${post.platform.toUpperCase()}</span></td>
          <td>
            <strong>${escapeHtml(post.topic)}</strong>
            <div class="content-preview">${preview}...</div>
          </td>
          <td><span class="score-badge ${scoreClass}">${post.quality_score}/100</span></td>
          <td><span class="status-badge status-${post.status}">${post.status}</span></td>
          <td style="font-family: var(--font-mono); font-size: 0.8rem; color: var(--text-muted);">${dateDisplay}</td>
          <td>
            <button class="btn btn-secondary btn-inspect" data-id="${post.id}" style="padding: 0.35rem 0.75rem; font-size: 0.75rem;">
              Inspect
            </button>
          </td>
        </tr>
      `;
    }).join("");

    // Attach inspect handlers
    document.querySelectorAll(".btn-inspect").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-id");
        const post = allPosts.find(p => p.id === id);
        if (post) openPostModal(post);
      });
    });
  }

  // Check and Render Manual Reviews
  function checkManualReviews() {
    const reviews = allPosts.filter(p => p.status === "MANUAL_REVIEW_REQUIRED");
    if (reviews.length > 0) {
      reviewAlertSection.classList.remove("hidden");
      reviewHeadline.textContent = `${reviews.length} draft${reviews.length > 1 ? 's' : ''} flagged by autonomous safety policy`;
      reviewItemsContainer.innerHTML = reviews.map(p => `
        <div class="review-card">
          <div class="review-card-details">
            <span class="badge badge-${p.platform}">${p.platform.toUpperCase()}</span>
            <h4>${escapeHtml(p.topic)}</h4>
            <div class="review-card-reason">Reason: ${escapeHtml(p.manual_review_reason || 'High-stakes safety threshold')}</div>
          </div>
          <div class="review-actions">
            <button class="btn btn-secondary btn-inspect" data-id="${p.id}">Inspect</button>
            <button class="btn btn-success btn-approve-review" data-id="${p.id}">Approve</button>
            <button class="btn btn-secondary btn-reject-review" data-id="${p.id}">Reject</button>
          </div>
        </div>
      `).join("");

      // Action buttons for review
      document.querySelectorAll(".btn-approve-review").forEach(btn => {
        btn.addEventListener("click", () => handleReviewDecision(btn.getAttribute("data-id"), "approve"));
      });
      document.querySelectorAll(".btn-reject-review").forEach(btn => {
        btn.addEventListener("click", () => handleReviewDecision(btn.getAttribute("data-id"), "reject"));
      });
    } else {
      reviewAlertSection.classList.add("hidden");
    }
  }

  async function handleReviewDecision(postId, action) {
    try {
      const res = await fetch("/api/review/decision", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ post_id: postId, action }),
      });
      if (res.ok) {
        showToast(`Draft ${action === 'approve' ? 'approved and queued' : 'rejected'}.`, "success");
        await refreshAll();
      } else {
        showToast("Failed to process decision.", "error");
      }
    } catch (err) {
      showToast("Network error submitting review decision.", "error");
    }
  }

  // Open Modal Details
  function openPostModal(post) {
    document.getElementById("modal-platform-badge").textContent = post.platform.toUpperCase();
    document.getElementById("modal-platform-badge").className = `badge badge-${post.platform}`;
    document.getElementById("modal-post-topic").textContent = post.topic;
    document.getElementById("modal-post-content").textContent = post.content;
    document.getElementById("modal-score-number").textContent = post.quality_score;
    document.getElementById("modal-fingerprint").textContent = post.fingerprint;

    const verdictText = document.getElementById("modal-verdict-text");
    const scoreNum = document.getElementById("modal-score-number");
    if (post.quality_score >= 85) {
      scoreNum.style.color = "#34D399";
      verdictText.textContent = "PASSED QUALITY GATE (Threshold: 85)";
    } else {
      scoreNum.style.color = "#F87171";
      verdictText.textContent = "REVISE OR REJECT (Score below 85)";
    }

    // Media Concept
    const mediaBox = document.getElementById("modal-media-box");
    if (post.media_prompt || (post.media_urls && post.media_urls.length > 0)) {
      mediaBox.classList.remove("hidden");
      document.getElementById("modal-media-spec").textContent = post.media_prompt || post.media_urls.join("\n");
    } else {
      mediaBox.classList.add("hidden");
    }

    // Quality Report Breakdown
    const rep = post.quality_report || {};
    const reportBox = document.getElementById("modal-report-box");
    let reportHtml = `<div><strong>Gate Status:</strong> ${post.status}</div>`;
    reportHtml += `<div><strong>Revision Count:</strong> ${post.revision_count}</div>`;
    reportHtml += `<div><strong>Emojis Found:</strong> ${rep.emoji_count || 0}</div>`;
    reportHtml += `<div><strong>Hashtags Found:</strong> ${rep.hashtag_count || 0}</div>`;

    if (rep.hard_failures && rep.hard_failures.length > 0) {
      reportHtml += `<div style="color: #F87171; margin-top: 0.5rem;"><strong>Hard Failures:</strong><ul>${rep.hard_failures.map(e => `<li>${escapeHtml(e)}</li>`).join('')}</ul></div>`;
    }
    if (rep.warnings && rep.warnings.length > 0) {
      reportHtml += `<div style="color: #FBBF24; margin-top: 0.5rem;"><strong>Warnings:</strong><ul>${rep.warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('')}</ul></div>`;
    }
    reportBox.innerHTML = reportHtml;

    modal.showModal();
  }

  // Close Modal
  btnCloseModal.addEventListener("click", () => modal.close());
  btnModalDismiss.addEventListener("click", () => modal.close());
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.close();
  });

  // Filter Tabs
  filterTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      filterTabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      currentFilter = tab.getAttribute("data-filter");
      renderFilteredPosts();
    });
  });

  // Platform Dropdown
  selectPlatform.addEventListener("change", (e) => {
    currentPlatform = e.target.value;
    renderFilteredPosts();
  });

  // Trigger Generation
  btnTriggerGenerate.addEventListener("click", async () => {
    btnTriggerGenerate.disabled = true;
    btnTriggerGenerate.innerHTML = `<span class="pulse-dot"></span> Generating...`;
    showToast("Triggering content generation run...", "info");

    try {
      const res = await fetch("/api/generate", { method: "POST" });
      const data = await res.json();
      if (data.status === "SKIPPED") {
        showToast(`Run skipped: ${data.reason}`, "info");
      } else {
        showToast(`Success: Generated ${data.generated_count || 0} drafts, scheduled ${data.scheduled_count || 0}.`, "success");
      }
      await refreshAll();
    } catch (err) {
      showToast("Generation run error.", "error");
    } finally {
      btnTriggerGenerate.disabled = false;
      btnTriggerGenerate.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
        Generate New Posts
      `;
    }
  });

  // Trigger Publishing
  btnTriggerPublish.addEventListener("click", async () => {
    btnTriggerPublish.disabled = true;
    btnTriggerPublish.innerHTML = `<span class="pulse-dot"></span> Dispatching...`;
    showToast("Publishing due posts...", "info");

    try {
      const res = await fetch("/api/publish", { method: "POST" });
      const data = await res.json();
      showToast(`Publishing cycle complete: ${data.published || 0} published, ${data.failed || 0} failed.`, "success");
      await refreshAll();
    } catch (err) {
      showToast("Error processing publishing queue.", "error");
    } finally {
      btnTriggerPublish.disabled = false;
      btnTriggerPublish.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
        Publish Due Queue
      `;
    }
  });

  btnRefresh.addEventListener("click", refreshAll);

  async function refreshAll() {
    await fetchStatus();
    await fetchPosts();
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/[&<>'"]/g, tag => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;'
    }[tag] || tag));
  }

  // Initial Load
  refreshAll();
  // Auto-refresh every 30 seconds
  setInterval(refreshAll, 30000);
});
