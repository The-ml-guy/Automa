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
  const valDiscovered = document.getElementById("val-discovered");
  const valRanked = document.getElementById("val-ranked");
  const modeText = document.getElementById("mode-text");
  const postsTableBody = document.getElementById("posts-table-body");
  const auditLogList = document.getElementById("audit-log-list");
  const reviewAlertSection = document.getElementById("review-alert-section");
  const reviewItemsContainer = document.getElementById("review-items-container");
  const reviewHeadline = document.getElementById("review-count-headline");

  const rankedTopicsGrid = document.getElementById("ranked-topics-grid");
  const discoveredFeedsGrid = document.getElementById("discovered-feeds-grid");
  const hubTabs = document.querySelectorAll("#hub-tabs .tab-btn");

  const btnRefresh = document.getElementById("btn-refresh-data");
  const btnTriggerPipeline = document.getElementById("btn-trigger-pipeline");
  const btnTriggerDiscover = document.getElementById("btn-trigger-discover");
  const btnTriggerGenerate = document.getElementById("btn-trigger-generate");
  const btnTriggerPublish = document.getElementById("btn-trigger-publish");
  const selectPlatform = document.getElementById("select-platform-filter");
  const filterTabs = document.querySelectorAll("#filter-tabs .tab-btn");

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
      const [resStatus, resIntel] = await Promise.all([
        fetch("/api/status"),
        fetch("/api/intelligence/stats")
      ]);
      if (!resStatus.ok) throw new Error("Failed to reach server");
      const data = await resStatus.json();
      const intel = resIntel.ok ? await resIntel.json() : {};

      valScheduled.textContent = data.queue_counts.SCHEDULED || 0;
      valPublished.textContent = data.queue_counts.PUBLISHED || 0;
      if (valDiscovered) valDiscovered.textContent = intel.total_discovered || 0;
      if (valRanked) valRanked.textContent = intel.total_ranked || 0;

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

  // Fetch and Render Intelligence Hub (Ranked Topics & Feeds)
  async function fetchIntelligence() {
    try {
      const [resRank, resDisc] = await Promise.all([
        fetch("/api/intelligence/rankings"),
        fetch("/api/intelligence/discovered")
      ]);

      if (resRank.ok) {
        const rankings = await resRank.json();
        renderRankings(rankings);
      }

      if (resDisc.ok) {
        const discovered = await resDisc.json();
        renderDiscoveredFeeds(discovered);
      }
    } catch (err) {
      console.error("Error fetching intelligence data:", err);
    }
  }

  function renderRankings(rankings) {
    if (!rankedTopicsGrid) return;
    if (!rankings || rankings.length === 0) {
      rankedTopicsGrid.innerHTML = `<div class="empty-state">No ranked topics yet. Click 'Run Full Pipeline' or 'Discover Feeds'.</div>`;
      return;
    }

    rankedTopicsGrid.innerHTML = rankings.slice(0, 8).map(r => `
      <div class="intel-card">
        <div class="intel-card-header">
          <span class="intel-source-tag ${r.source_type.toLowerCase()}">${r.source_type.toUpperCase()}</span>
          <span class="total-score-badge">${r.total_score.toFixed(1)} / 100</span>
        </div>
        <div class="intel-card-title">${escapeHtml(r.title)}</div>
        <div class="intel-meta-row">
          <span>${r.authors ? escapeHtml(r.authors.substring(0, 30)) : 'Community'}</span>
          <span>${r.ranked_at ? r.ranked_at.substring(0, 10) : ''}</span>
        </div>
        <div class="intel-abstract">${escapeHtml(r.abstract || '')}</div>
        <div class="score-breakdown-box">
          <div class="score-mini-stat">
            <span class="score-mini-label">Recency (20%)</span>
            <span class="score-mini-val">${r.score_recency}</span>
          </div>
          <div class="score-mini-stat">
            <span class="score-mini-label">Utility (20%)</span>
            <span class="score-mini-val">${r.score_usefulness}</span>
          </div>
          <div class="score-mini-stat">
            <span class="score-mini-label">Signif (20%)</span>
            <span class="score-mini-val">${r.score_significance}</span>
          </div>
          <div class="score-mini-stat">
            <span class="score-mini-label">Open-Src (15%)</span>
            <span class="score-mini-val">${r.score_accessibility}</span>
          </div>
          <div class="score-mini-stat">
            <span class="score-mini-label">Credib (15%)</span>
            <span class="score-mini-val">${r.score_credibility}</span>
          </div>
          <div class="score-mini-stat">
            <span class="score-mini-label">Novelty (10%)</span>
            <span class="score-mini-val">${r.score_novelty}</span>
          </div>
        </div>
        <div class="intel-card-footer">
          <span style="font-size: 0.7rem; color: var(--text-muted);">${escapeHtml(r.notes || 'Verified')}</span>
          <a href="${r.url}" target="_blank" rel="noopener noreferrer" class="link-btn">
            Inspect Source ↗
          </a>
        </div>
      </div>
    `).join("");
  }

  function renderDiscoveredFeeds(items) {
    if (!discoveredFeedsGrid) return;
    if (!items || items.length === 0) {
      discoveredFeedsGrid.innerHTML = `<div class="empty-state">No feed items discovered yet.</div>`;
      return;
    }

    discoveredFeedsGrid.innerHTML = items.slice(0, 12).map(item => `
      <div class="intel-card">
        <div class="intel-card-header">
          <span class="intel-source-tag ${item.source_type.toLowerCase()}">${item.source_type.toUpperCase()}</span>
          <span style="font-size: 0.7rem; color: var(--text-muted);">${item.primary_category || ''}</span>
        </div>
        <div class="intel-card-title">${escapeHtml(item.title)}</div>
        <div class="intel-meta-row">
          <span>${item.authors ? escapeHtml(item.authors.substring(0, 30)) : 'Team'}</span>
          <span>${item.published_at ? item.published_at.substring(0, 10) : ''}</span>
        </div>
        <div class="intel-abstract">${escapeHtml(item.abstract || 'No abstract.')}</div>
        <div class="intel-card-footer">
          <span style="font-size: 0.7rem; color: var(--text-muted);">Status: ${item.status}</span>
          <a href="${item.url}" target="_blank" rel="noopener noreferrer" class="link-btn">
            Open URL ↗
          </a>
        </div>
      </div>
    `).join("");
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
      const canPublish = post.status !== "PUBLISHED";
      const publishBtn = canPublish
        ? `<button class="btn btn-success btn-quick-publish" data-id="${post.id}" style="padding: 0.35rem 0.65rem; font-size: 0.75rem; margin-left: 0.35rem;" title="Publish immediately to ${post.platform.toUpperCase()}">Publish 🚀</button>`
        : `<button class="btn btn-secondary" disabled style="padding: 0.35rem 0.65rem; font-size: 0.75rem; margin-left: 0.35rem; opacity: 0.6;">Done ✓</button>`;

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
          <td style="white-space: nowrap;">
            <button class="btn btn-secondary btn-inspect" data-id="${post.id}" style="padding: 0.35rem 0.75rem; font-size: 0.75rem;">
              Inspect
            </button>
            ${publishBtn}
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

    // Attach quick publish handlers
    document.querySelectorAll(".btn-quick-publish").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        btn.disabled = true;
        btn.innerHTML = `Sending...`;
        await publishPostById(id);
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

    // Media Concept & Image Preview
    const mediaBox = document.getElementById("modal-media-box");
    const mediaSpec = document.getElementById("modal-media-spec");
    if (post.media_urls && post.media_urls.length > 0) {
      mediaBox.classList.remove("hidden");
      const localFile = post.media_urls[0];
      const filename = localFile.split(/[\\/]/).pop();
      mediaSpec.innerHTML = `
        <div style="margin-bottom: 0.5rem; font-size: 0.8rem; color: var(--text-muted);">${escapeHtml(post.media_prompt || 'Technical Graphic Card')}</div>
        <img src="/media/${encodeURIComponent(filename)}" alt="Visual Card" style="width: 100%; border-radius: 8px; border: 1px solid var(--border-color); display: block; margin-top: 0.5rem;" onerror="this.style.display='none'" />
      `;
    } else if (post.media_prompt) {
      mediaBox.classList.remove("hidden");
      mediaSpec.textContent = post.media_prompt;
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

    // Configure Modal Share to X & Copy Image Buttons
    const btnModalShareX = document.getElementById("btn-modal-share-x");
    const btnModalCopyImg = document.getElementById("btn-modal-copy-img");
    const hasImage = post.media_urls && post.media_urls.length > 0 && !post.media_urls[0].endsWith("_graphic.png");
    const imageUrl = hasImage ? `/media/${encodeURIComponent(post.media_urls[0].split(/[\\/]/).pop())}` : null;

    if (btnModalCopyImg) {
      if (imageUrl) {
        btnModalCopyImg.style.display = "inline-flex";
        btnModalCopyImg.onclick = async () => {
          btnModalCopyImg.textContent = "⏳ Copying...";
          try {
            const resp = await fetch(imageUrl);
            const blob = await resp.blob();
            await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
            showToast("✓ Image copied to clipboard! Paste into X or LinkedIn with Ctrl+V.", "success");
            btnModalCopyImg.textContent = "✓ Copied!";
          } catch (e) {
            showToast("Failed to copy image to clipboard.", "error");
            btnModalCopyImg.textContent = "📋 Copy Image";
          }
          setTimeout(() => { btnModalCopyImg.textContent = "📋 Copy Image"; }, 2000);
        };
      } else {
        btnModalCopyImg.style.display = "none";
      }
    }

    if (btnModalShareX) {
      btnModalShareX.style.display = "inline-flex";
      btnModalShareX.onclick = async () => {
        // If image exists, copy it to clipboard first
        if (imageUrl) {
          try {
            const resp = await fetch(imageUrl);
            const blob = await resp.blob();
            await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
            showToast("📋 Image copied! In Twitter, press Ctrl+V to attach the image.", "success");
          } catch (e) {
            console.warn(e);
          }
        }
        const text = encodeURIComponent(post.content.substring(0, 280));
        window.open(`https://twitter.com/intent/tweet?text=${text}`, "_blank");
      };
    }

    // Configure Modal Publish Button
    const btnModalPublish = document.getElementById("btn-modal-publish-now");
    if (btnModalPublish) {
      if (post.status === "PUBLISHED") {
        btnModalPublish.disabled = true;
        btnModalPublish.textContent = "Already Published ✓";
        btnModalPublish.className = "btn btn-secondary";
      } else {
        btnModalPublish.disabled = false;
        btnModalPublish.className = "btn btn-success";
        btnModalPublish.textContent = `Publish to ${post.platform.toUpperCase()} Now 🚀`;
        btnModalPublish.onclick = async () => {
          btnModalPublish.disabled = true;
          btnModalPublish.textContent = "Dispatching...";
          await publishPostById(post.id);
        };
      }
    }

    modal.showModal();
  }

  // Close Modal
  btnCloseModal.addEventListener("click", () => modal.close());
  btnModalDismiss.addEventListener("click", () => modal.close());
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.close();
  });

  // Hub View Tabs (Ranked vs Feeds)
  hubTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      hubTabs.forEach(t => {
        t.classList.remove("active");
        t.setAttribute("aria-selected", "false");
      });
      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
      const view = tab.getAttribute("data-intel-view");
      if (view === "rankings") {
        rankedTopicsGrid.classList.remove("hidden");
        discoveredFeedsGrid.classList.add("hidden");
      } else {
        rankedTopicsGrid.classList.add("hidden");
        discoveredFeedsGrid.classList.remove("hidden");
      }
    });
  });

  // Trigger Multi-Agent Pipeline
  if (btnTriggerPipeline) {
    btnTriggerPipeline.addEventListener("click", async () => {
      btnTriggerPipeline.disabled = true;
      btnTriggerPipeline.innerHTML = `<span class="pulse-dot"></span> Pipeline Running...`;
      showToast("Starting 6-agent intelligence pipeline (Discover -> Verify -> Rank -> Simplify -> Strategy -> Copywrite)...", "info");

      try {
        const res = await fetch("/api/intelligence/pipeline", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ discovery_limit: 5, platforms: ["linkedin", "x"] })
        });
        const data = await res.json();
        if (data.success) {
          showToast(`Pipeline Complete! Selected: "${data.topic_chosen}". Scheduled: ${data.posts_scheduled_count} post(s).`, "success");
        } else {
          showToast(`Pipeline Alert: ${data.error || 'Failed'}`, "error");
        }
        await refreshAll();
      } catch (err) {
        showToast("Error executing intelligence pipeline.", "error");
      } finally {
        btnTriggerPipeline.disabled = false;
        btnTriggerPipeline.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
          Run Full Pipeline
        `;
      }
    });
  }

  // Trigger Feed Discovery
  if (btnTriggerDiscover) {
    btnTriggerDiscover.addEventListener("click", async () => {
      btnTriggerDiscover.disabled = true;
      btnTriggerDiscover.innerHTML = `<span class="pulse-dot"></span> Fetching Feeds...`;
      showToast("Querying arXiv, Hugging Face, and Hacker News feeds...", "info");

      try {
        const res = await fetch("/api/intelligence/discover", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ limit: 5 })
        });
        const data = await res.json();
        showToast(`Discovered ${data.new_items_count || 0} fresh AI research & code items.`, "success");
        await refreshAll();
      } catch (err) {
        showToast("Error polling research feeds.", "error");
      } finally {
        btnTriggerDiscover.disabled = false;
        btnTriggerDiscover.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          Discover Feeds
        `;
      }
    });
  }

  // Filter Tabs
  filterTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      filterTabs.forEach(t => {
        t.classList.remove("active");
        t.setAttribute("aria-selected", "false");
      });
      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
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
        Draft Scheduled
      `;
    }
  });

  // Publish single post by ID
  async function publishPostById(postId) {
    showToast(`Dispatching post to network...`, "info");
    try {
      const res = await fetch("/api/posts/publish", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ post_id: postId })
      });
      const data = await res.json();
      if (data.success) {
        showToast(`Post published to ${data.platform.toUpperCase()} successfully!`, "success");
        if (modal && modal.open) modal.close();
        await refreshAll();
      } else {
        showToast(`Publishing failed: ${data.error || "Unknown error"}`, "error");
        await refreshAll();
      }
    } catch (err) {
      showToast("Network error publishing post.", "error");
    }
  }

  // Trigger Publishing
  btnTriggerPublish.addEventListener("click", async () => {
    btnTriggerPublish.disabled = true;
    btnTriggerPublish.innerHTML = `<span class="pulse-dot"></span> Dispatching...`;
    showToast("Publishing queued posts...", "info");

    try {
      const res = await fetch("/api/publish", { 
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ force: true })
      });
      const data = await res.json();
      const pubCount = data.published || 0;
      const failCount = data.failed || 0;
      showToast(`Publishing cycle complete: ${pubCount} published, ${failCount} failed.`, pubCount > 0 ? "success" : "info");
      await refreshAll();
    } catch (err) {
      showToast("Error processing publishing queue.", "error");
    } finally {
      btnTriggerPublish.disabled = false;
      btnTriggerPublish.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
        Publish Queue Now
      `;
    }
  });

  btnRefresh.addEventListener("click", refreshAll);

  async function refreshAll() {
    await fetchStatus();
    await fetchIntelligence();
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
