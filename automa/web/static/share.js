/**
 * AUTOMA SHARE CENTER — One-Click Social Publishing
 * High-resolution visual cards, clipboard image injection, and seamless X/LinkedIn workflows.
 */

document.addEventListener("DOMContentLoaded", () => {
  let allPosts = [];
  let currentPlatform = "all";
  let currentStatus = "all";
  let activeModalPost = null;

  // DOM Elements
  const shareGrid = document.getElementById("share-grid");
  const emptyState = document.getElementById("empty-state");
  const btnRefresh = document.getElementById("btn-refresh");
  const btnGenerateNew = document.getElementById("btn-generate-new");

  const statTotal = document.getElementById("stat-total");
  const statReady = document.getElementById("stat-ready");
  const statPublished = document.getElementById("stat-published");
  const statWithImages = document.getElementById("stat-with-images");

  // Share Assistant Modal Elements
  const shareModal = document.getElementById("share-modal");
  const btnCloseShareModal = document.getElementById("btn-close-share-modal");
  const btnModalDone = document.getElementById("btn-modal-done");
  const btnModalCopyImg = document.getElementById("btn-modal-copy-img");
  const btnModalDlImg = document.getElementById("btn-modal-dl-img");
  const btnModalReopen = document.getElementById("btn-modal-reopen");
  const modalImg = document.getElementById("share-modal-img");

  // ── Toast Notifications ──
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

  // ── Copy Feedback Overlay ──
  function showCopyFeedback(msg) {
    const el = document.createElement("div");
    el.className = "copy-feedback";
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => {
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 300);
    }, 1800);
  }

  // ── Helper: Copy Image to System Clipboard ──
  async function copyImageToClipboard(imageUrl) {
    try {
      const response = await fetch(imageUrl);
      const blob = await response.blob();
      await navigator.clipboard.write([
        new ClipboardItem({ "image/png": blob })
      ]);
      return true;
    } catch (err) {
      console.warn("Direct image clipboard write failed:", err);
      return false;
    }
  }

  // ── Helper: Download Image File ──
  function downloadImage(imageUrl, filename) {
    try {
      const link = document.createElement("a");
      link.href = imageUrl;
      link.download = filename || "automa-post-card.png";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      return true;
    } catch (err) {
      console.error("Download error:", err);
      return false;
    }
  }

  // ── Fetch All Posts ──
  async function fetchPosts() {
    try {
      const res = await fetch("/api/posts");
      if (!res.ok) throw new Error("Failed to load posts");
      allPosts = await res.json();
      updateStats();
      renderPosts();
    } catch (err) {
      console.error("Error fetching posts:", err);
      showToast("Failed to load posts from storage.", "error");
    }
  }

  // ── Update Dashboard Stats ──
  function updateStats() {
    const total = allPosts.length;
    const ready = allPosts.filter(p => p.status === "SCHEDULED").length;
    const published = allPosts.filter(p => p.status === "PUBLISHED").length;
    const withImages = allPosts.filter(p => p.media_urls && p.media_urls.length > 0 && !p.media_urls[0].endsWith("_graphic.png")).length;

    statTotal.textContent = total;
    statReady.textContent = ready;
    statPublished.textContent = published;
    statWithImages.textContent = withImages;
  }

  // ── Render Posts Grid ──
  function renderPosts() {
    let filtered = allPosts;

    if (currentPlatform !== "all") {
      filtered = filtered.filter(p => p.platform === currentPlatform);
    }
    if (currentStatus !== "all") {
      filtered = filtered.filter(p => p.status === currentStatus);
    }

    if (filtered.length === 0) {
      shareGrid.innerHTML = "";
      emptyState.classList.remove("hidden");
      return;
    }

    emptyState.classList.add("hidden");

    shareGrid.innerHTML = filtered.map(post => {
      const hasImage = post.media_urls && post.media_urls.length > 0;
      const isRealImage = hasImage && !post.media_urls[0].endsWith("_graphic.png");
      const filename = hasImage ? post.media_urls[0].split(/[\\/]/).pop() : "";
      const imageUrl = isRealImage ? `/media/${encodeURIComponent(filename)}` : "";

      const platformBadgeClass = `badge-${post.platform}`;
      const statusBadgeClass = `status-${post.status}`;
      const isSquare = post.platform === "instagram";
      const scoreClass = post.quality_score >= 85 ? "score-high" : "score-low";
      const isPublished = post.status === "PUBLISHED";

      return `
        <article class="post-card" data-id="${post.id}">
          <div class="card-image-wrap ${isSquare ? 'square' : ''}">
            ${isRealImage ? `
              <img src="${imageUrl}" alt="Post visual for ${esc(post.topic)}" class="card-image" loading="lazy" />
              <div class="card-image-overlay-actions">
                <button class="btn-overlay btn-card-copy-img" data-url="${imageUrl}" title="Copy image to clipboard">
                  📋 Copy Image
                </button>
                <button class="btn-overlay btn-card-dl-img" data-url="${imageUrl}" data-filename="${filename}" title="Download image file">
                  ⬇️ Save
                </button>
              </div>
            ` : `
              <div class="card-no-image">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                  <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                  <circle cx="8.5" cy="8.5" r="1.5"></circle>
                  <polyline points="21 15 16 10 5 21"></polyline>
                </svg>
                <button class="btn-gen-image" data-id="${post.id}">⚡ Generate High-Res Image</button>
              </div>
            `}
            <span class="card-platform-badge ${platformBadgeClass}">${post.platform.toUpperCase()}</span>
            <span class="card-status-badge ${statusBadgeClass}">${post.status.replace(/_/g, " ")}</span>
          </div>

          <div class="card-body">
            <div class="card-topic">${esc(post.topic)}</div>
            <div class="card-content">${esc(post.content)}</div>
            <div class="card-meta">
              <span class="meta-score ${scoreClass}">${post.quality_score}/100</span>
              <span class="meta-tag">${post.scheduled_at ? post.scheduled_at.replace("T", " ").substring(0, 16) + " UTC" : "—"}</span>
              ${isRealImage ? `<span class="meta-tag" style="color:var(--accent-cyan);">✓ Image Ready</span>` : ""}
            </div>
          </div>

          <div class="card-actions">
            <!-- Share to X Button -->
            <button class="btn btn-x btn-sm btn-share-x" data-id="${post.id}" title="One-Click Share to X with Image">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
              Share to X
            </button>

            <!-- Copy for LinkedIn Button -->
            <button class="btn btn-linkedin btn-sm btn-copy-linkedin" data-id="${post.id}" title="Copy text & image and open LinkedIn">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M20.5 2h-17A1.5 1.5 0 002 3.5v17A1.5 1.5 0 003.5 22h17a1.5 1.5 0 001.5-1.5v-17A1.5 1.5 0 0020.5 2zM8 19H5v-9h3zM6.5 8.25A1.75 1.75 0 118.3 6.5a1.78 1.78 0 01-1.8 1.75zM19 19h-3v-4.74c0-1.42-.6-1.93-1.38-1.93A1.74 1.74 0 0013 14.19a.66.66 0 000 .14V19h-3v-9h2.9v1.3a3.11 3.11 0 012.7-1.4c1.55 0 3.36.86 3.36 3.66z"/></svg>
              Share to LinkedIn
            </button>

            <!-- Share to Instagram Button -->
            <button class="btn btn-instagram btn-sm btn-share-instagram" data-id="${post.id}" title="Copy caption & image and open Instagram">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect><path d="M16 11.37A4 4 0 1112.63 8 4 4 0 0116 11.37z"></path><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line></svg>
              Share to IG
            </button>

            <!-- Copy text only -->
            <button class="btn btn-secondary btn-sm btn-copy-text" data-id="${post.id}" title="Copy post text only">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
              Text
            </button>

            <!-- Direct Publish via API -->
            ${!isPublished ? `
              <button class="btn btn-success btn-sm btn-publish-now" data-id="${post.id}" title="Publish via Direct API">
                🚀
              </button>
            ` : `
              <span class="btn btn-secondary btn-sm" style="opacity:0.6; cursor:default;" title="Published">✓</span>
            `}
          </div>
        </article>
      `;
    }).join("");

    attachCardHandlers();
  }

  // ── Attach Event Handlers ──
  function attachCardHandlers() {

    // 1. One-Click Share to X (Copies Image to Clipboard + Downloads + Opens X Composer)
    document.querySelectorAll(".btn-share-x").forEach(btn => {
      btn.addEventListener("click", async () => {
        const postId = btn.dataset.id;
        let post = allPosts.find(p => p.id === postId);
        if (!post) return;

        btn.disabled = true;
        const originalText = btn.innerHTML;
        btn.innerHTML = `⏳ Preparing...`;

        try {
          // If no real image exists, generate one on the fly first
          const hasImage = post.media_urls && post.media_urls.length > 0 && !post.media_urls[0].endsWith("_graphic.png");
          let imageUrl = hasImage ? `/media/${encodeURIComponent(post.media_urls[0].split(/[\\/]/).pop())}` : null;
          let filename = hasImage ? post.media_urls[0].split(/[\\/]/).pop() : `${post.id}.png`;

          if (!imageUrl) {
            btn.innerHTML = `🎨 Creating Image...`;
            const genRes = await fetch("/api/posts/generate-image", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ post_id: postId }),
            });
            const genData = await genRes.json();
            if (genData.success) {
              imageUrl = genData.image_url;
              filename = genData.image_url.split("/").pop();
              post.media_urls = [genData.path];
            }
          }

          // Copy image to clipboard
          let imageCopied = false;
          if (imageUrl) {
            imageCopied = await copyImageToClipboard(imageUrl);
            // Also trigger file download so it's ready in browser downloads
            downloadImage(imageUrl, filename);
          }

          // Build Twitter Web Intent URL
          const tweetText = encodeURIComponent(post.content.substring(0, 280));
          const xIntentUrl = `https://twitter.com/intent/tweet?text=${tweetText}`;

          // Open X in a new tab
          window.open(xIntentUrl, "_blank");

          // Show Assistant Modal
          activeModalPost = { post, imageUrl, filename, xIntentUrl };
          showShareAssistantModal(post, imageUrl, "x", imageCopied);

        } catch (err) {
          console.error("Error in Share to X:", err);
          showToast("Error preparing share to X.", "error");
        } finally {
          btn.disabled = false;
          btn.innerHTML = originalText;
        }
      });
    });

    // 2. Share to LinkedIn (Copy Image + Copy Text + Open LinkedIn)
    document.querySelectorAll(".btn-copy-linkedin").forEach(btn => {
      btn.addEventListener("click", async () => {
        const postId = btn.dataset.id;
        let post = allPosts.find(p => p.id === postId);
        if (!post) return;

        btn.disabled = true;
        const originalText = btn.innerHTML;
        btn.innerHTML = `⏳ Preparing...`;

        try {
          const hasImage = post.media_urls && post.media_urls.length > 0 && !post.media_urls[0].endsWith("_graphic.png");
          let imageUrl = hasImage ? `/media/${encodeURIComponent(post.media_urls[0].split(/[\\/]/).pop())}` : null;
          let filename = hasImage ? post.media_urls[0].split(/[\\/]/).pop() : `${post.id}.png`;

          if (!imageUrl) {
            const genRes = await fetch("/api/posts/generate-image", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ post_id: postId }),
            });
            const genData = await genRes.json();
            if (genData.success) {
              imageUrl = genData.image_url;
              filename = genData.image_url.split("/").pop();
              post.media_urls = [genData.path];
            }
          }

          if (imageUrl) {
            downloadImage(imageUrl, filename);
          }

          // Copy post content to clipboard
          await navigator.clipboard.writeText(post.content);

          // Open LinkedIn
          const linkedinUrl = "https://www.linkedin.com/feed/?shareActive=true";
          window.open(linkedinUrl, "_blank");

          activeModalPost = { post, imageUrl, filename, xIntentUrl: linkedinUrl };
          showShareAssistantModal(post, imageUrl, "linkedin", true);

        } catch (err) {
          showToast("Error preparing LinkedIn share.", "error");
        } finally {
          btn.disabled = false;
          btn.innerHTML = originalText;
        }
      });
    });

    // 2b. Share to Instagram (Download Image + Copy Caption + Open Instagram)
    document.querySelectorAll(".btn-share-instagram").forEach(btn => {
      btn.addEventListener("click", async () => {
        const postId = btn.dataset.id;
        let post = allPosts.find(p => p.id === postId);
        if (!post) return;

        btn.disabled = true;
        const originalText = btn.innerHTML;
        btn.innerHTML = `⏳ Preparing...`;

        try {
          const hasImage = post.media_urls && post.media_urls.length > 0 && !post.media_urls[0].endsWith("_graphic.png");
          let imageUrl = hasImage ? `/media/${encodeURIComponent(post.media_urls[0].split(/[\\/]/).pop())}` : null;
          let filename = hasImage ? post.media_urls[0].split(/[\\/]/).pop() : `${post.id}.png`;

          if (!imageUrl) {
            btn.innerHTML = `🎨 Creating Image...`;
            const genRes = await fetch("/api/posts/generate-image", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ post_id: postId }),
            });
            const genData = await genRes.json();
            if (genData.success) {
              imageUrl = genData.image_url;
              filename = genData.image_url.split("/").pop();
              post.media_urls = [genData.path];
            }
          }

          if (imageUrl) {
            downloadImage(imageUrl, filename);
          }

          // Copy caption to clipboard
          await navigator.clipboard.writeText(post.content);

          // Open Instagram Web
          const instagramUrl = "https://www.instagram.com/";
          window.open(instagramUrl, "_blank");

          activeModalPost = { post, imageUrl, filename, xIntentUrl: instagramUrl };
          showShareAssistantModal(post, imageUrl, "instagram", true);

        } catch (err) {
          showToast("Error preparing Instagram share.", "error");
        } finally {
          btn.disabled = false;
          btn.innerHTML = originalText;
        }
      });
    });

    // 3. Quick Copy Image overlay button
    document.querySelectorAll(".btn-card-copy-img").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const url = btn.dataset.url;
        btn.textContent = "⏳ Copying...";
        const ok = await copyImageToClipboard(url);
        if (ok) {
          showCopyFeedback("✓ Image copied! Press Ctrl+V in X or LinkedIn to paste.");
          btn.textContent = "✓ Copied!";
        } else {
          showToast("Failed to copy image directly. Use download button.", "error");
          btn.textContent = "📋 Copy Image";
        }
        setTimeout(() => { btn.textContent = "📋 Copy Image"; }, 2000);
      });
    });

    // 4. Quick Download Image overlay button
    document.querySelectorAll(".btn-card-dl-img").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const url = btn.dataset.url;
        const filename = btn.dataset.filename || "post-card.png";
        downloadImage(url, filename);
        showToast("✓ Image downloaded to your device!", "success");
      });
    });

    // 5. Generate Image button (on card with missing image)
    document.querySelectorAll(".btn-gen-image").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const postId = btn.dataset.id;
        btn.disabled = true;
        btn.textContent = "⏳ Generating...";
        try {
          const res = await fetch("/api/posts/generate-image", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ post_id: postId }),
          });
          const data = await res.json();
          if (data.success) {
            showToast("Visual card generated successfully!", "success");
            await fetchPosts();
          } else {
            showToast(`Image generation failed: ${data.error}`, "error");
            btn.disabled = false;
            btn.textContent = "⚡ Generate Image";
          }
        } catch (err) {
          showToast("Network error generating image.", "error");
          btn.disabled = false;
          btn.textContent = "⚡ Generate Image";
        }
      });
    });

    // 6. Copy text only
    document.querySelectorAll(".btn-copy-text").forEach(btn => {
      btn.addEventListener("click", () => {
        const postId = btn.dataset.id;
        const post = allPosts.find(p => p.id === postId);
        if (post) {
          navigator.clipboard.writeText(post.content).then(() => {
            showCopyFeedback("✓ Post text copied to clipboard!");
          });
        }
      });
    });

    // 7. Publish Now via API
    document.querySelectorAll(".btn-publish-now").forEach(btn => {
      btn.addEventListener("click", async () => {
        const postId = btn.dataset.id;
        btn.disabled = true;
        btn.innerHTML = "⏳";
        try {
          const res = await fetch("/api/posts/publish", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ post_id: postId }),
          });
          const data = await res.json();
          if (data.success) {
            showToast(`Published to ${data.platform.toUpperCase()} successfully! 🎉`, "success");
            await fetchPosts();
          } else {
            showToast(`API publish: ${data.error || "Check API credentials"}`, "error");
            btn.disabled = false;
            btn.innerHTML = "🚀";
          }
        } catch (err) {
          showToast("Network error publishing post.", "error");
          btn.disabled = false;
          btn.innerHTML = "🚀";
        }
      });
    });
  }

  // ── Show Share Assistant Modal ──
  function showShareAssistantModal(post, imageUrl, network, imageCopied) {
    const isX = network === "x";
    const isIG = network === "instagram";
    
    document.getElementById("modal-network-icon").textContent = isX ? "𝕏" : (isIG ? "📷" : "in");
    document.getElementById("modal-share-title").textContent = isX 
      ? "Sharing to X (Twitter)" 
      : (isIG ? "Sharing to Instagram" : "Sharing to LinkedIn");
      
    document.getElementById("modal-step1-desc").textContent = isX
      ? "X compose window opened in a new tab with your tweet text pre-filled."
      : (isIG 
        ? "Instagram opened in your browser. Your caption is copied to clipboard."
        : "LinkedIn composer opened in a new tab. Your post copy is copied to clipboard.");

    document.getElementById("modal-step2-title").textContent = imageCopied
      ? "Image Copied to Clipboard & Downloaded!"
      : "Image Downloaded to Your Computer!";

    document.getElementById("modal-step2-desc").innerHTML = isX
      ? `Click into the tweet box on X and press <kbd>Ctrl</kbd> + <kbd>V</kbd> to paste the image directly! (Or click the photo icon and select the downloaded file).`
      : (isIG
        ? `Click 'Create' on Instagram (+), select the downloaded high-res card image, then paste your caption (<kbd>Ctrl</kbd> + <kbd>V</kbd>).`
        : `Click 'Start a post' on LinkedIn, press <kbd>Ctrl</kbd> + <kbd>V</kbd> to paste text, then attach the downloaded image.`);

    if (imageUrl) {
      modalImg.src = imageUrl;
      modalImg.style.display = "block";
    } else {
      modalImg.style.display = "none";
    }

    shareModal.showModal();
  }

  // ── Modal Actions ──
  btnCloseShareModal.addEventListener("click", () => shareModal.close());
  btnModalDone.addEventListener("click", () => shareModal.close());
  shareModal.addEventListener("click", (e) => {
    if (e.target === shareModal) shareModal.close();
  });

  btnModalCopyImg.addEventListener("click", async () => {
    if (activeModalPost && activeModalPost.imageUrl) {
      const ok = await copyImageToClipboard(activeModalPost.imageUrl);
      if (ok) {
        showCopyFeedback("✓ Image re-copied to clipboard! Press Ctrl+V in X.");
      } else {
        showToast("Could not copy directly. Use Download button instead.", "error");
      }
    }
  });

  btnModalDlImg.addEventListener("click", () => {
    if (activeModalPost && activeModalPost.imageUrl) {
      downloadImage(activeModalPost.imageUrl, activeModalPost.filename);
      showToast("✓ Image downloaded!", "success");
    }
  });

  btnModalReopen.addEventListener("click", () => {
    if (activeModalPost && activeModalPost.xIntentUrl) {
      window.open(activeModalPost.xIntentUrl, "_blank");
    }
  });

  // ── Platform Filter Tabs ──
  document.querySelectorAll("#platform-tabs .filter-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#platform-tabs .filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentPlatform = btn.dataset.platform;
      renderPosts();
    });
  });

  // ── Status Filter Tabs ──
  document.querySelectorAll("#status-tabs .status-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#status-tabs .status-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentStatus = btn.dataset.status;
      renderPosts();
    });
  });

  // ── Refresh Button ──
  btnRefresh.addEventListener("click", fetchPosts);

  // ── Generate New Posts Button ──
  btnGenerateNew.addEventListener("click", async () => {
    btnGenerateNew.disabled = true;
    btnGenerateNew.innerHTML = `<span class="spinner" style="width:14px;height:14px;border-width:2px;margin:0;display:inline-block;vertical-align:middle;"></span> Generating...`;
    showToast("Generating new posts with visual cards...", "info");

    try {
      const res = await fetch("/api/generate", { method: "POST" });
      const data = await res.json();
      if (data.status === "SKIPPED") {
        showToast(`Run skipped: ${data.reason}`, "info");
      } else {
        showToast(`Created ${data.generated_count || 0} drafts with visual cards!`, "success");
      }
      await fetchPosts();
    } catch (err) {
      showToast("Error generating posts.", "error");
    } finally {
      btnGenerateNew.disabled = false;
      btnGenerateNew.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>
        Generate New Posts`;
    }
  });

  // ── HTML Escaper ──
  function esc(str) {
    if (!str) return "";
    return str.replace(/[&<>'"]/g, tag => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
    }[tag] || tag));
  }

  // Initial Load
  fetchPosts();
  setInterval(fetchPosts, 30000);
});
