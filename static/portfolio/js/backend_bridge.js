(function () {
  const bootstrapElement = document.getElementById("ela-bootstrap");
  if (!bootstrapElement) {
    return;
  }

  const bootstrap = JSON.parse(bootstrapElement.textContent || "{}");
  const originalNavigate = typeof window.navigate === "function" ? window.navigate : null;
  const originalSwitchDashTab =
    typeof window.switchDashTab === "function" ? window.switchDashTab : null;
  const originalOpenAddVideoModal =
    typeof window.openAddVideoModal === "function" ? window.openAddVideoModal : null;
  const originalEditVideo = typeof window.editVideo === "function" ? window.editVideo : null;
  const originalRenderFeatured = typeof window.renderFeatured === "function" ? window.renderFeatured : null;
  const originalRenderProfile = typeof window.renderProfile === "function" ? window.renderProfile : null;
  const originalRenderProfileVideos =
    typeof window.renderProfileVideos === "function" ? window.renderProfileVideos : null;
  const originalRenderDiscoverResults =
    typeof window.renderDiscoverResults === "function" ? window.renderDiscoverResults : null;
  const originalRenderDashboard =
    typeof window.renderDashboard === "function" ? window.renderDashboard : null;
  const LIKE_META = { emoji: "\uD83D\uDC4D", label: "Like" };
  const STAR_FILLED = "\u2605";
  const STAR_EMPTY = "\u2606";

  function syncAuthGlobals(user, role) {
    window.currentUser = user || null;
    window.currentUserRole = role || null;
    try {
      currentUser = window.currentUser;
    } catch (error) {
      void error;
    }
  }

  function syncRouteGlobals() {
    try {
      window.currentPage = currentPage;
    } catch (error) {
      void error;
    }
    try {
      window.currentProfileUser = currentProfileUser;
    } catch (error) {
      void error;
    }
    try {
      window.currentProfileTab = currentProfileTab;
    } catch (error) {
      void error;
    }
    try {
      window.currentProfileCat = currentProfileCat;
    } catch (error) {
      void error;
    }
    try {
      window.currentDiscoverCat = currentDiscoverCat;
    } catch (error) {
      void error;
    }
  }

  function setDiscoverCategoryState(value) {
    window.currentDiscoverCat = value;
    try {
      currentDiscoverCat = value;
    } catch (error) {
      void error;
    }
  }

  function replaceState(payload) {
    const editors = Array.isArray(payload.editors) ? payload.editors : [];
    window.__elaBootstrap = payload;
    window.__elaEditors = editors;
    syncAuthGlobals(payload.current_user || null, payload.current_user_role || null);

    if (window.currentUser) {
      localStorage.setItem("ela_current_user", window.currentUser);
    } else {
      localStorage.removeItem("ela_current_user");
    }
    updateNavigationAuth();
    refreshActivePlayerState();
  }

  function getCsrfToken() {
    const cookie = document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith("csrftoken="));
    return cookie ? decodeURIComponent(cookie.split("=")[1]) : "";
  }

  async function postForm(url, data) {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "X-CSRFToken": getCsrfToken(),
        Accept: "application/json",
      },
      body: new URLSearchParams(data),
      credentials: "same-origin",
    });

    const payload = await response.json();
    if (!response.ok) {
      if (response.status === 401) {
        replaceState({ editors: window.__elaEditors || [], current_user: null, current_user_role: null });
        window.openModal("loginModal");
      }
      throw new Error(payload.message || "Request failed.");
    }
    return payload;
  }

  async function postMultipartForm(url, formData) {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCsrfToken(),
        Accept: "application/json",
      },
      body: formData,
      credentials: "same-origin",
    });

    const payload = await response.json();
    if (!response.ok) {
      if (response.status === 401) {
        replaceState({ editors: window.__elaEditors || [], current_user: null, current_user_role: null });
        window.openModal("loginModal");
      }
      throw new Error(payload.message || "Request failed.");
    }
    return payload;
  }

  async function getJson(url) {
    const response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      credentials: "same-origin",
    });
    const payload = await response.json();
    if (!response.ok) {
      if (response.status === 401) {
        replaceState({ editors: window.__elaEditors || [], current_user: null, current_user_role: null });
        window.openModal("loginModal");
      }
      throw new Error(payload.message || "Request failed.");
    }
    return payload;
  }

  function syncHistory(page, data) {
    let target = "/";
    if (page === "discover") {
      target = "/discover/";
    } else if (page === "dashboard") {
      target = "/dashboard/";
    } else if (page === "profile" && data) {
      target = `/${encodeURIComponent(data)}/`;
    }

    if (window.location.pathname !== target) {
      window.history.pushState({}, "", target);
    }
  }

  function isCurrentUserEditor() {
    return window.currentUserRole === "editor";
  }

  function isCurrentUserClient() {
    return window.currentUserRole === "client";
  }

  function currentViewerProfile() {
    return window.currentUser ? editorByUsername(window.currentUser) : null;
  }

  function closeMobileMenuIfOpen() {
    const mobileMenu = document.getElementById("mobileMenu");
    if (
      mobileMenu &&
      mobileMenu.classList.contains("open") &&
      typeof window.toggleMobileMenu === "function"
    ) {
      window.toggleMobileMenu();
    }
  }

  function openDashboardProfileEditor() {
    window.navigate("dashboard");
    window.__elaActiveDashboardTab = "profile";
    setTimeout(() => {
      if (typeof window.switchDashTab === "function") {
        window.switchDashTab("profile");
      }
    }, 30);
  }

  function openDashboardContactsEditor() {
    window.navigate("dashboard");
    window.__elaActiveDashboardTab = "contacts";
    setTimeout(() => {
      if (typeof window.switchDashTab === "function") {
        window.switchDashTab("contacts");
      }
    }, 30);
  }

  function openDashboardUploadModal() {
    if (!window.currentUser) {
      promptSignIn("Sign in to upload videos.");
      return;
    }
    if (!isCurrentUserEditor()) {
      window.showToast("Only editor accounts can upload videos.", "error");
      return;
    }
    window.navigate("dashboard");
    window.__elaActiveDashboardTab = "videos";
    setTimeout(() => {
      if (typeof window.switchDashTab === "function") {
        window.switchDashTab("videos");
      }
      if (typeof window.openAddVideoModal === "function") {
        window.openAddVideoModal();
      }
    }, 40);
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function promptSignIn(message) {
    window.showToast(message || "Please sign in to continue.", "error");
    window.openModal("loginModal");
  }

  function videoLikeCount(video) {
    return Number(video?.likes_count ?? video?.like_count ?? 0);
  }

  function videoAverageRating(video) {
    return Number(video?.average_rating || 0);
  }

  function videoRatingsCount(video) {
    return Number(video?.ratings_count || 0);
  }

  function videoViewerRating(video) {
    return Number(video?.viewer_rating || 0);
  }

  function videoViewerHasLiked(video) {
    return Boolean(video?.viewer_has_liked);
  }

  function ratingLabel(count) {
    return `${window.formatNumber(count)} rating${count === 1 ? "" : "s"}`;
  }

  function renderStaticStars(value, compact = false) {
    const rounded = Math.max(0, Math.min(5, Math.round(Number(value) || 0)));
    return (
      `<span style="color:#f59e0b;font-size:${compact ? "0.8rem" : "0.92rem"};letter-spacing:0.04em;">` +
      `${STAR_FILLED.repeat(rounded)}${STAR_EMPTY.repeat(5 - rounded)}` +
      `</span>`
    );
  }

  function renderAverageRatingMarkup(video, compact = false) {
    const average = videoAverageRating(video);
    const count = videoRatingsCount(video);
    if (!count) {
      return `<span style="color:var(--text-muted);font-size:${compact ? "0.76rem" : "0.82rem"};">No ratings yet</span>`;
    }

    return (
      `<span style="display:inline-flex;align-items:center;gap:${compact ? "6px" : "8px"};flex-wrap:wrap;color:var(--text-muted);font-size:${compact ? "0.76rem" : "0.82rem"};">` +
      renderStaticStars(average, compact) +
      `<span><strong style="color:var(--text-primary);">${average.toFixed(1)}</strong>/5</span>` +
      `<span>(${ratingLabel(count)})</span>` +
      `</span>`
    );
  }

  function videoCreatedAtMs(video) {
    const value = Date.parse(video?.created_at || "");
    return Number.isNaN(value) ? 0 : value;
  }

  function featuredVideoComparator(a, b) {
    return (
      videoAverageRating(b) - videoAverageRating(a) ||
      videoRatingsCount(b) - videoRatingsCount(a) ||
      videoLikeCount(b) - videoLikeCount(a) ||
      videoCreatedAtMs(b) - videoCreatedAtMs(a) ||
      (b.views || 0) - (a.views || 0)
    );
  }

  function featuredSortedVideos(videos) {
    return [...(videos || [])].sort(featuredVideoComparator);
  }

  function featuredEditorComparator(a, b) {
    const aVideos = featuredSortedVideos(a.videos || []);
    const bVideos = featuredSortedVideos(b.videos || []);
    const aTop = aVideos[0] || null;
    const bTop = bVideos[0] || null;
    const aTotals = aVideos.reduce(
      (acc, video) => {
        acc.rating += videoAverageRating(video);
        acc.ratings += videoRatingsCount(video);
        acc.likes += videoLikeCount(video);
        return acc;
      },
      { rating: 0, ratings: 0, likes: 0 }
    );
    const bTotals = bVideos.reduce(
      (acc, video) => {
        acc.rating += videoAverageRating(video);
        acc.ratings += videoRatingsCount(video);
        acc.likes += videoLikeCount(video);
        return acc;
      },
      { rating: 0, ratings: 0, likes: 0 }
    );

    return (
      featuredVideoComparator(aTop, bTop) ||
      bTotals.rating - aTotals.rating ||
      bTotals.ratings - aTotals.ratings ||
      bTotals.likes - aTotals.likes ||
      videoCreatedAtMs(bTop) - videoCreatedAtMs(aTop) ||
      (b.videos || []).length - (a.videos || []).length ||
      String(a.display_name || a.username).localeCompare(String(b.display_name || b.username))
    );
  }

  function workStatsLabel(editor) {
    return (
      editor?.work_stats_label ||
      `${Number(editor?.clients_served || 0)} clients \u2022 ${Number(editor?.completed_projects || 0)} projects`
    );
  }

  function renderWorkStatsPill(editor, compact = false) {
    const sizeClass = compact ? "btn-sm" : "";
    return (
      `<div class="btn-secondary ${sizeClass}" style="pointer-events:none;display:inline-flex;gap:8px;align-items:center;">` +
      `<i class="fas fa-briefcase"></i>${escapeHtml(workStatsLabel(editor))}</div>`
    );
  }

  function teardownPlayerModal() {
    const container = document.getElementById("playerContainer");
    if (container) {
      Array.from(container.querySelectorAll("video")).forEach((node) => {
        try {
          node.pause();
        } catch (error) {
          void error;
        }
        node.removeAttribute("src");
        node.load();
      });
      Array.from(container.querySelectorAll("iframe")).forEach((node) => {
        node.src = "about:blank";
      });
      container.innerHTML = "";
    }

    const actions = document.getElementById("playerActions");
    if (actions) {
      actions.innerHTML = "";
    }

    window.__elaActivePlayerVideoId = null;
    window.__elaActivePlayerUsername = null;
  }

  function activePlayerVideo() {
    if (!window.__elaActivePlayerVideoId || !window.__elaActivePlayerUsername) {
      return { editor: null, video: null };
    }
    const editor = editorByUsername(window.__elaActivePlayerUsername);
    const video = editor
      ? (editor.videos || []).find((item) => item.id === window.__elaActivePlayerVideoId) || null
      : null;
    return { editor, video };
  }

  async function toggleVideoLike(username, videoId) {
    if (!window.currentUser) {
      promptSignIn("Sign in to like videos.");
      return;
    }

    try {
      const payload = await postForm(
        `/api/profiles/${encodeURIComponent(username)}/videos/${encodeURIComponent(videoId)}/like/`,
        {}
      );
      replaceState(payload);
      renderCurrentContexts();
      window.showToast(payload.message, payload.liked ? "success" : "info");
    } catch (error) {
      window.showToast(error.message, "error");
    }
  }

  async function updateVideoRating(username, videoId, rating) {
    if (!window.currentUser) {
      promptSignIn("Sign in to rate videos.");
      return;
    }

    try {
      const payload = await postForm(
        `/api/profiles/${encodeURIComponent(username)}/videos/${encodeURIComponent(videoId)}/rate/`,
        { rating }
      );
      replaceState(payload);
      renderCurrentContexts();
      window.showToast(payload.message, "success");
    } catch (error) {
      window.showToast(error.message, "error");
    }
  }

  function renderLikeSummaryMarkup(video, compact = false) {
    const likes = videoLikeCount(video);
    return (
      `<span style="color:var(--text-muted);font-size:${compact ? "0.76rem" : "0.82rem"};">` +
      `${LIKE_META.emoji} ${window.formatNumber(likes)} like${likes === 1 ? "" : "s"}` +
      `</span>`
    );
  }

  function mountLikeButton(host, username, video, compact = false) {
    if (!host || !video) {
      return;
    }

    host.innerHTML = "";
    const button = document.createElement("button");
    button.type = "button";
    button.className = videoViewerHasLiked(video) ? "btn-primary" : "btn-secondary";
    if (compact) {
      button.classList.add("btn-sm");
    }
    button.style.minWidth = compact ? "auto" : "94px";
    button.innerHTML =
      `<span style="font-size:${compact ? "0.92rem" : "1rem"};">${LIKE_META.emoji}</span>` +
      `<span>${window.formatNumber(videoLikeCount(video))}</span>`;
    button.title = LIKE_META.label;
    button.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      toggleVideoLike(username, video.id);
    });
    host.appendChild(button);
  }

  function mountRatingButtons(host, username, video, compact = false, includeSummary = true) {
    if (!host || !video) {
      return;
    }

    const currentRating = videoViewerRating(video);
    host.innerHTML = "";
    host.style.display = "flex";
    host.style.flexDirection = "column";
    host.style.gap = compact ? "6px" : "8px";

    if (includeSummary) {
      const summary = document.createElement("div");
      summary.innerHTML = renderAverageRatingMarkup(video, compact);
      host.appendChild(summary);
    }

    const row = document.createElement("div");
    row.style.display = "flex";
    row.style.flexWrap = "wrap";
    row.style.gap = compact ? "4px" : "6px";
    row.style.alignItems = "center";

    for (let rating = 1; rating <= 5; rating += 1) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = compact ? "btn-icon" : "btn-secondary btn-sm";
      button.style.color = rating <= currentRating ? "#f59e0b" : "var(--text-muted)";
      button.style.padding = compact ? "6px" : "8px 10px";
      button.style.minWidth = compact ? "34px" : "46px";
      button.innerHTML = `<span style="font-size:${compact ? "1rem" : "1.05rem"};">${
        rating <= currentRating ? STAR_FILLED : STAR_EMPTY
      }</span>`;
      button.title = `Rate ${rating} star${rating === 1 ? "" : "s"}`;
      button.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        updateVideoRating(username, video.id, rating);
      });
      row.appendChild(button);
    }

    host.appendChild(row);
  }

  function renderVideoEngagement(host, username, video, compact = false, includeRatingSummary = true) {
    if (!host || !video) {
      return;
    }

    host.innerHTML = "";
    host.style.display = "flex";
    host.style.flexWrap = "wrap";
    host.style.gap = compact ? "8px" : "12px";
    host.style.alignItems = compact ? "center" : "flex-start";

    const likeHost = document.createElement("div");
    mountLikeButton(likeHost, username, video, compact);
    host.appendChild(likeHost);

    const ratingHost = document.createElement("div");
    mountRatingButtons(ratingHost, username, video, compact, includeRatingSummary);
    host.appendChild(ratingHost);
  }

  function renderPlayerActions(editor, video) {
    const host = document.getElementById("playerActions");
    if (!host) {
      return;
    }

    host.innerHTML = "";
    if (!editor || !video) {
      return;
    }

    const engagementHost = document.createElement("div");
    engagementHost.style.display = "flex";
    engagementHost.style.flexWrap = "wrap";
    engagementHost.style.gap = "12px";
    engagementHost.style.alignItems = "center";
    renderVideoEngagement(engagementHost, editor.username, video);
    host.appendChild(engagementHost);

    if (video.has_uploaded_file) {
      if (video.can_download && video.download_url) {
        const downloadButton = document.createElement("button");
        downloadButton.type = "button";
        downloadButton.className = "btn-secondary btn-sm";
        downloadButton.innerHTML = '<i class="fas fa-download"></i> Download';
        downloadButton.addEventListener("click", function () {
          window.location.assign(video.download_url);
        });
        host.appendChild(downloadButton);
      } else {
        const note = document.createElement("div");
        note.style.color = "var(--text-secondary)";
        note.style.fontSize = "0.8rem";
        note.textContent = "Download locked. Contact the editor for access.";
        host.appendChild(note);
      }
    }
  }

  function refreshActivePlayerState() {
    const modal = document.getElementById("videoPlayerModal");
    if (!modal || !modal.classList.contains("show")) {
      return;
    }

    const { editor, video } = activePlayerVideo();
    if (!editor || !video) {
      teardownPlayerModal();
      return;
    }

    const views = document.getElementById("playerViews");
    if (views) {
      views.textContent = `${window.formatNumber(video.views)} views`;
    }
    renderPlayerActions(editor, video);
  }

  function currentProfileVideos() {
    const editor = editorByUsername(window.currentProfileUser);
    if (!editor) {
      return [];
    }
    let videos = (editor.videos || []).filter((video) => video.type === window.currentProfileTab);
    if (window.currentProfileCat && window.currentProfileCat !== "all") {
      videos = videos.filter((video) => video.category === window.currentProfileCat);
    }
    return videos;
  }

  function navigateToProfileAndOpenVideo(username, videoId) {
    const editor = editorByUsername(username);
    if (!editor || !videoId) {
      if (username) {
        window.navigate("profile", username);
      }
      return;
    }

    const video = (editor.videos || []).find((item) => item.id === videoId);
    window.navigate("profile", username);
    if (!video) {
      return;
    }

    const desiredTab = video.type === "long" ? "long" : "short";
    setTimeout(() => {
      if (typeof window.switchProfileTab === "function" && window.currentProfileTab !== desiredTab) {
        window.switchProfileTab(desiredTab);
      }
      openPlayerForVideo(editorByUsername(username), video);
    }, 50);
  }

  function decorateProfileVideoCards() {
    const editor = editorByUsername(window.currentProfileUser);
    if (!editor) {
      return;
    }

    const videos = currentProfileVideos();
    const selector = window.currentProfileTab === "short" ? "#shortVideoList .short-video-card" : "#longVideoList .long-video-card";
    const cards = Array.from(document.querySelectorAll(selector));
    cards.forEach((card, index) => {
      const video = videos[index];
      const info = card.querySelector(".info");
      if (!video || !info) {
        return;
      }

      const existing = info.querySelector(".ela-video-social");
      if (existing) {
        existing.remove();
      }

      const block = document.createElement("div");
      block.className = "ela-video-social";
      block.style.display = "flex";
      block.style.flexDirection = "column";
      block.style.gap = "10px";
      block.style.marginTop = "12px";
      block.innerHTML =
        `<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;">` +
        renderAverageRatingMarkup(video, true) +
        renderLikeSummaryMarkup(video, true) +
        `</div>`;

      const engagementHost = document.createElement("div");
      renderVideoEngagement(engagementHost, editor.username, video, true, false);
      block.appendChild(engagementHost);
      info.appendChild(block);
    });
  }

  function decorateDiscoverCards(editors) {
    const container = document.getElementById("discoverResults");
    if (!container || !Array.isArray(editors)) {
      return;
    }

    Array.from(container.children).forEach((card, index) => {
      const editor = editors[index];
      if (!editor) {
        return;
      }

      const body = card.querySelector(".card-body");
      if (!body || body.querySelector(".ela-work-stats")) {
        return;
      }

      const stats = document.createElement("div");
      stats.className = "ela-work-stats";
      stats.style.marginTop = "14px";
      stats.innerHTML = renderWorkStatsPill(editor, true);
      body.appendChild(stats);
    });
  }

  function updateNavigationAuth() {
    const desktopAccountLink = document.getElementById("desktopAccountLink");
    const mobileAccountLink = document.getElementById("mobileAccountLink");
    const desktopAuthActions = document.getElementById("desktopAuthActions");
    const mobileAuthActions = document.getElementById("mobileAuthActions");
    const viewer = currentViewerProfile();
    const signedInLabel =
      viewer && viewer.display_name && viewer.display_name !== viewer.username
        ? `${viewer.display_name} (@${viewer.username})`
        : window.currentUser
          ? `@${window.currentUser}`
          : "";

    function bindClick(id, handler) {
      const element = document.getElementById(id);
      if (element) {
        element.addEventListener("click", handler);
      }
    }

    if (desktopAccountLink) {
      desktopAccountLink.textContent = window.currentUser ? "Dashboard" : "Sign In";
      desktopAccountLink.onclick = function () {
        if (window.currentUser) {
          window.navigate("dashboard");
        } else {
          window.openModal("loginModal");
        }
        return false;
      };
    }

    if (mobileAccountLink) {
      mobileAccountLink.textContent = window.currentUser ? "Dashboard" : "Sign In";
      mobileAccountLink.onclick = function () {
        closeMobileMenuIfOpen();
        if (window.currentUser) {
          window.navigate("dashboard");
        } else {
          window.openModal("loginModal");
        }
        return false;
      };
    }

    if (desktopAuthActions) {
      if (window.currentUser) {
        desktopAuthActions.innerHTML =
          `<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">` +
          `<div style="padding:8px 12px;border:1px solid var(--border);border-radius:999px;color:var(--text-secondary);font-size:0.82rem;">` +
          `Signed in as <strong style="color:var(--text-primary);">${escapeHtml(signedInLabel)}</strong>` +
          `</div>` +
          `<button type="button" class="btn-secondary btn-sm" id="desktopMyProfileBtn">` +
          `<i class="fas fa-id-badge"></i> My Profile</button>` +
          `<button type="button" class="btn-primary btn-sm" id="desktopLogoutBtn">` +
          `<i class="fas fa-sign-out-alt"></i> Logout</button>` +
          `</div>`;
        bindClick("desktopMyProfileBtn", function () {
          window.navigate("profile", window.currentUser);
        });
        bindClick("desktopLogoutBtn", function () {
          window.logout();
        });
      } else {
        desktopAuthActions.innerHTML =
          '<button type="button" class="btn-primary btn-sm" id="desktopSignupBtn">' +
          '<i class="fas fa-user-plus"></i> Sign Up</button>';
        bindClick("desktopSignupBtn", function () {
          window.openModal("signupModal");
        });
      }
    }

    if (mobileAuthActions) {
      if (window.currentUser) {
        mobileAuthActions.innerHTML =
          `<div style="display:flex;flex-direction:column;gap:12px;">` +
          `<div style="padding:12px 14px;border:1px solid var(--border);border-radius:16px;color:var(--text-secondary);font-size:0.9rem;text-align:center;">` +
          `Signed in as <strong style="color:var(--text-primary);">${escapeHtml(signedInLabel)}</strong>` +
          `</div>` +
          `<button type="button" class="btn-secondary" id="mobileMyProfileBtn" style="justify-content:center;">` +
          `<i class="fas fa-id-badge"></i> My Profile</button>` +
          `<button type="button" class="btn-primary" id="mobileLogoutBtn" style="justify-content:center;">` +
          `<i class="fas fa-sign-out-alt"></i> Logout</button>` +
          `</div>`;
        bindClick("mobileMyProfileBtn", function () {
          closeMobileMenuIfOpen();
          window.navigate("profile", window.currentUser);
        });
        bindClick("mobileLogoutBtn", function () {
          closeMobileMenuIfOpen();
          window.logout();
        });
      } else {
        mobileAuthActions.innerHTML =
          '<button type="button" class="btn-primary" id="mobileSignupBtn" style="justify-content:center;">' +
          '<i class="fas fa-user-plus"></i> Sign Up</button>';
        bindClick("mobileSignupBtn", function () {
          closeMobileMenuIfOpen();
          window.openModal("signupModal");
        });
      }
    }
  }

  function highlightSignedInDiscoverCards(editors) {
    const container = document.getElementById("discoverResults");
    if (!container || !Array.isArray(editors) || !window.currentUser) {
      return;
    }

    Array.from(container.children).forEach((card, index) => {
      const editor = editors[index];
      if (!editor || editor.username !== window.currentUser) {
        return;
      }

      card.style.outline = "2px solid var(--accent)";
      card.style.outlineOffset = "2px";
      const metaBlock = card.querySelector(".editor-meta");
      if (!metaBlock) {
        return;
      }

      const marker = document.createElement("div");
      marker.className = "own-account-badge";
      marker.innerHTML =
        '<span class="badge" style="margin-top:8px;font-size:0.68rem;">Signed in account</span>';
      metaBlock.insertAdjacentElement("afterend", marker);
    });
  }

  function renderCurrentContexts() {
    if (window.currentPage === "dashboard" && typeof window.renderDashboard === "function") {
      const activeTab = window.__elaActiveDashboardTab || "videos";
      window.renderDashboard();
      if (activeTab !== "videos" && typeof window.switchDashTab === "function") {
        window.switchDashTab(activeTab);
      }
    }
    if (
      window.currentPage === "profile" &&
      window.currentProfileUser &&
      typeof window.renderProfile === "function"
    ) {
      window.renderProfile(window.currentProfileUser);
    }
    if (window.currentPage === "discover" && typeof window.renderDiscover === "function") {
      window.renderDiscover();
    }
    if (window.currentPage === "home" && typeof window.renderFeatured === "function") {
      window.renderFeatured();
    }
    ensureFloatingUploadButton();
  }

  function openPlayerForVideo(editor, video) {
    if (!editor || !video) {
      return;
    }

    teardownPlayerModal();
    window.__elaActivePlayerVideoId = video.id;
    window.__elaActivePlayerUsername = editor.username;
    document.getElementById("playerTitle").textContent = video.title;
    document.getElementById("playerCategory").textContent = video.category;
    document.getElementById("playerType").textContent =
      video.type === "short" ? "Short Content" : "Long Content";
    document.getElementById("playerViews").textContent = `${window.formatNumber(video.views)} views`;

    if (video.has_uploaded_file && video.playback_url) {
      document.getElementById("playerContainer").innerHTML =
        `<video src="${video.playback_url}" controls controlsList="nodownload" disablepictureinpicture autoplay ` +
        'style="width:100%;height:100%;background:#000;" playsinline oncontextmenu="return false;"></video>';
    } else {
      const embedUrl = window.getEmbedUrl(video.url);
      document.getElementById("playerContainer").innerHTML =
        `<iframe src="${embedUrl}" style="width:100%;height:100%;border:none;" ` +
        'allow="accelerometer;autoplay;clipboard-write;encrypted-media;gyroscope;picture-in-picture" ' +
        "allowfullscreen></iframe>";
    }

    renderPlayerActions(editor, video);
    window.openModal("videoPlayerModal");
  }

  function videoUrlGroup() {
    const input = document.getElementById("videoUrl");
    return input ? input.closest("div") : null;
  }

  function uploadStatusText(fileName, hasExistingFile) {
    if (fileName) {
      return fileName;
    }
    if (hasExistingFile) {
      return "Current local upload is saved. Choose another file to replace it.";
    }
    return "Choose a local video file to upload.";
  }

  function videoUploadFeedbackElement() {
    return document.getElementById("videoUploadFeedback");
  }

  function setVideoUploadFeedback(message, tone = "muted") {
    const feedback = videoUploadFeedbackElement();
    if (!feedback) {
      return;
    }

    feedback.textContent = message || "";
    feedback.style.display = message ? "block" : "none";
    feedback.style.color =
      tone === "error" ? "var(--accent)" : tone === "success" ? "#16a34a" : "var(--text-muted)";
  }

  function setVideoSaveButtonLoading(isLoading) {
    const button = document.getElementById("videoSaveAction");
    if (!button) {
      return;
    }

    const isEditing = Boolean(document.getElementById("editVideoId")?.value);
    button.disabled = isLoading;
    button.style.opacity = isLoading ? "0.7" : "";
    button.style.cursor = isLoading ? "wait" : "";
    button.innerHTML = isLoading
      ? `<i class="fas fa-spinner fa-spin"></i> <span id="videoSaveBtn">${
          isEditing ? "Saving..." : "Uploading..."
        }</span>`
      : `<i class="fas fa-save"></i> <span id="videoSaveBtn">${isEditing ? "Update Video" : "Save Video"}</span>`;
  }

  function updateVideoSourceUi(mode) {
    const urlGroup = videoUrlGroup();
    const uploadBlock = document.getElementById("videoUploadBlock");
    const status = document.getElementById("videoFileStatus");
    if (!urlGroup || !uploadBlock || !status) {
      return;
    }

    urlGroup.style.display = mode === "upload" ? "none" : "";
    uploadBlock.style.display = mode === "link" ? "none" : "";
    status.textContent = uploadStatusText(
      window.__elaPendingVideoFileName || "",
      Boolean(window.__elaExistingUploadedFileName)
    );
  }

  function clearPendingUploadSelection() {
    const fileInput = document.getElementById("videoFile");
    if (fileInput) {
      fileInput.value = "";
    }
    window.__elaPendingVideoFileName = "";
  }

  function setVideoSourceMode(mode, uploadedFileName) {
    const selector = document.getElementById("videoSourceMode");
    if (!selector) {
      return;
    }
    selector.value = mode || "link";
    window.__elaExistingUploadedFileName = uploadedFileName || "";
    updateVideoSourceUi(selector.value);
  }

  function ensureVideoSourceControls() {
    const urlGroup = videoUrlGroup();
    if (!urlGroup) {
      return;
    }

    if (!document.getElementById("videoSourceMode")) {
      const sourceBlock = document.createElement("div");
      sourceBlock.id = "videoSourceBlock";
      sourceBlock.innerHTML =
        `<label style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:6px;display:block;">` +
        `Video Source <span style="color:var(--accent);">*</span></label>` +
        `<select class="input-field" id="videoSourceMode">` +
        `<option value="link">Link</option>` +
        `<option value="upload">Upload</option>` +
        `<option value="both">Both</option>` +
        `</select>`;
      urlGroup.parentNode.insertBefore(sourceBlock, urlGroup);

      const uploadBlock = document.createElement("div");
      uploadBlock.id = "videoUploadBlock";
      uploadBlock.innerHTML =
        `<label style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:6px;display:block;">` +
        `Local Video File</label>` +
        `<input type="file" class="input-field" id="videoFile" accept=".mp4,.mov,.webm,.m4v,.avi,video/*">` +
        `<p id="videoFileStatus" style="font-size:0.75rem;color:var(--text-muted);margin-top:4px;">` +
        `Choose a local video file to upload.</p>`;
      urlGroup.parentNode.insertBefore(uploadBlock, urlGroup.nextSibling);

      document.getElementById("videoSourceMode").addEventListener("change", function () {
        if (this.value === "link") {
          clearPendingUploadSelection();
        }
        updateVideoSourceUi(this.value);
      });

      document.getElementById("videoFile").addEventListener("change", function () {
        const selected = this.files && this.files[0] ? this.files[0].name : "";
        window.__elaPendingVideoFileName = selected;
        updateVideoSourceUi(document.getElementById("videoSourceMode").value);
      });
    }

    updateVideoSourceUi(document.getElementById("videoSourceMode").value || "link");
  }

  function resetVideoSourceControls(mode) {
    ensureVideoSourceControls();
    clearPendingUploadSelection();
    window.__elaExistingUploadedFileName = "";
    setVideoSourceMode(mode || "link", "");
  }

  function copyTextToClipboard(value) {
    const text = String(value || "").trim();
    if (!text) {
      return Promise.resolve();
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    const fallback = document.createElement("textarea");
    fallback.value = text;
    fallback.setAttribute("readonly", "");
    fallback.style.position = "fixed";
    fallback.style.left = "-9999px";
    document.body.appendChild(fallback);
    fallback.select();
    document.execCommand("copy");
    document.body.removeChild(fallback);
    return Promise.resolve();
  }

  function ensureSignupEnhancements() {
    const usernameGroup = document.getElementById("signupUsername")?.closest("div");
    const bioGroup = document.getElementById("signupBio")?.closest("div");
    if (!usernameGroup || !bioGroup) {
      return;
    }

    if (!document.getElementById("signupRole")) {
      const roleBlock = document.createElement("div");
      roleBlock.innerHTML =
        `<label style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:6px;display:block;">Account Type</label>` +
        `<select class="input-field" id="signupRole">` +
        `<option value="editor">Editor</option>` +
        `<option value="client">Client</option>` +
        `</select>`;
      usernameGroup.parentNode.insertBefore(roleBlock, usernameGroup);

      const cnameBlock = document.createElement("div");
      cnameBlock.innerHTML =
        `<label style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:6px;display:block;">Display Name / cname</label>` +
        `<input type="text" class="input-field" id="signupCname" placeholder="How you want to appear publicly">`;
      usernameGroup.parentNode.insertBefore(cnameBlock, usernameGroup.nextSibling);

      const avatarBlock = document.createElement("div");
      avatarBlock.innerHTML =
        `<label style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:6px;display:block;">Profile Image</label>` +
        `<input type="file" class="input-field" id="signupAvatarFile" accept=".jpg,.jpeg,.png,.webp,.gif,image/*">` +
        `<p style="font-size:0.75rem;color:var(--text-muted);margin-top:4px;">Upload a local profile image for your account.</p>`;
      bioGroup.parentNode.insertBefore(avatarBlock, bioGroup);
    }
  }

  function ensureDashboardEnhancements() {
    const usernameInput = document.getElementById("editUsername");
    const avatarGroup = document.getElementById("editAvatar")?.closest("div");
    const profileCard = document.querySelector("#dashProfileTab .dashboard-card");
    const contactsButton = document.querySelector('#dashContactsTab button[onclick="saveContacts()"]');
    if (!usernameInput || !avatarGroup || !profileCard || !contactsButton) {
      return;
    }

    usernameInput.disabled = false;
    usernameInput.style.opacity = "1";
    const usernameLabel = usernameInput.closest("div")?.querySelector("label");
    if (usernameLabel) {
      usernameLabel.textContent = "Username";
    }

    if (!document.getElementById("editCname")) {
      const cnameBlock = document.createElement("div");
      cnameBlock.innerHTML =
        `<label style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:6px;display:block;">Display Name / cname</label>` +
        `<input type="text" class="input-field" id="editCname" placeholder="Public display name">`;
      usernameInput.closest("div").insertAdjacentElement("afterend", cnameBlock);
    }

    if (!document.getElementById("editClientsServed")) {
      const statsBlock = document.createElement("div");
      statsBlock.id = "editWorkStatsBlock";
      statsBlock.style.display = "grid";
      statsBlock.style.gridTemplateColumns = "1fr 1fr";
      statsBlock.style.gap = "16px";
      statsBlock.innerHTML =
        `<div>` +
        `<label style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:6px;display:block;">Clients Worked With</label>` +
        `<input type="number" min="0" class="input-field" id="editClientsServed" placeholder="0">` +
        `</div>` +
        `<div>` +
        `<label style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:6px;display:block;">Completed Projects</label>` +
        `<input type="number" min="0" class="input-field" id="editCompletedProjects" placeholder="0">` +
        `</div>`;
      document.getElementById("editCname")
        ?.closest("div")
        ?.insertAdjacentElement("afterend", statsBlock);
    }

    if (!document.getElementById("editAvatarFile")) {
      const avatarFileBlock = document.createElement("div");
      avatarFileBlock.innerHTML =
        `<label style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:6px;display:block;">Profile Image Upload</label>` +
        `<input type="file" class="input-field" id="editAvatarFile" accept=".jpg,.jpeg,.png,.webp,.gif,image/*">` +
        `<p id="editAvatarFileStatus" style="font-size:0.75rem;color:var(--text-muted);margin-top:4px;">Upload a local image to replace the current profile image.</p>`;
      avatarGroup.insertAdjacentElement("afterend", avatarFileBlock);
    }

    if (!document.getElementById("portfolioSetupNotice")) {
      const setupBlock = document.createElement("div");
      setupBlock.id = "portfolioSetupNotice";
      setupBlock.className = "card";
      setupBlock.style.padding = "18px";
      setupBlock.style.marginBottom = "18px";
      profileCard.insertBefore(setupBlock, profileCard.firstChild.nextSibling);
    }

    if (!document.getElementById("otherContactsManager")) {
      const manager = document.createElement("div");
      manager.id = "otherContactsManager";
      manager.innerHTML =
        `<div style="display:flex;justify-content:space-between;align-items:center;gap:12px;margin:8px 0 12px;">` +
        `<div>` +
        `<div style="font-weight:700;font-size:0.95rem;">Other Social / Contact Links</div>` +
        `<div style="color:var(--text-secondary);font-size:0.8rem;">Add portfolio-friendly links such as Instagram, LinkedIn, Behance, or a booking page.</div>` +
        `</div>` +
        `<button type="button" class="btn-secondary btn-sm" id="addOtherContactBtn">Add Link</button>` +
        `</div>` +
        `<div id="otherContactsRows" style="display:flex;flex-direction:column;gap:12px;"></div>`;
      contactsButton.insertAdjacentElement("beforebegin", manager);
      document.getElementById("addOtherContactBtn").addEventListener("click", function () {
        addOtherContactRow();
      });
    }
  }

  function createOtherContactRow(contact = {}) {
    const row = document.createElement("div");
    row.className = "other-contact-row";
    row.style.display = "grid";
    row.style.gridTemplateColumns = "1fr 1.3fr auto";
    row.style.gap = "10px";
    row.innerHTML =
      `<input type="text" class="input-field other-contact-label" placeholder="Label" value="${escapeHtml(
        contact.label || ""
      )}">` +
      `<input type="text" class="input-field other-contact-value" placeholder="https://example.com" value="${escapeHtml(
        contact.value || ""
      )}">` +
      `<button type="button" class="btn-icon other-contact-remove" title="Remove"><i class="fas fa-times"></i></button>`;
    row.querySelector(".other-contact-remove").addEventListener("click", function () {
      row.remove();
    });
    return row;
  }

  function addOtherContactRow(contact = {}) {
    const rows = document.getElementById("otherContactsRows");
    if (!rows) {
      return;
    }
    rows.appendChild(createOtherContactRow(contact));
  }

  function populateOtherContactsRows(contacts) {
    const rows = document.getElementById("otherContactsRows");
    if (!rows) {
      return;
    }
    rows.innerHTML = "";
    (contacts || []).forEach((contact) => addOtherContactRow(contact));
  }

  function collectOtherContacts() {
    return Array.from(document.querySelectorAll(".other-contact-row"))
      .map((row) => {
        const label = row.querySelector(".other-contact-label")?.value.trim() || "";
        const value = row.querySelector(".other-contact-value")?.value.trim() || "";
        return { label, value };
      })
      .filter((item) => item.label || item.value);
  }

  function renderSetupNotice(editor) {
    const setupNotice = document.getElementById("portfolioSetupNotice");
    if (!setupNotice || !editor) {
      return;
    }

    if (!editor.setup || editor.setup.is_complete) {
      setupNotice.style.display = "none";
      return;
    }

    const items = [];
    if (editor.setup.needs_avatar) {
      items.push("Upload a profile image");
    }
    if (editor.setup.needs_contact) {
      items.push("Add contact methods clients can use");
    }
    if (editor.setup.needs_video && editor.role === "editor") {
      items.push("Upload or link your first portfolio video");
    }

    setupNotice.style.display = "block";
    setupNotice.innerHTML =
      `<div style="font-weight:700;font-size:1rem;margin-bottom:8px;">Finish your setup</div>` +
      `<p style="color:var(--text-secondary);font-size:0.9rem;line-height:1.6;margin-bottom:12px;">Complete the remaining steps so your profile feels polished and ready to share.</p>` +
      `<div style="display:flex;flex-direction:column;gap:8px;margin-bottom:14px;">${items
        .map(
          (item) =>
            `<div style="display:flex;align-items:center;gap:8px;color:var(--text-primary);font-size:0.9rem;"><i class="fas fa-check-circle" style="color:var(--accent);"></i>${item}</div>`
        )
        .join("")}</div>` +
      `<div style="display:flex;gap:10px;flex-wrap:wrap;">` +
      `<button type="button" class="btn-secondary btn-sm" id="setupContactsBtn">Contacts</button>` +
      `${
        editor.role === "editor"
          ? `<button type="button" class="btn-primary btn-sm" id="setupUploadBtn"><i class="fas fa-upload"></i> Upload Video</button>`
          : ""
      }` +
      `</div>`;

    document.getElementById("setupContactsBtn")?.addEventListener("click", openDashboardContactsEditor);
    document.getElementById("setupUploadBtn")?.addEventListener("click", openDashboardUploadModal);
  }

  function renderProfileActionButtons(editor) {
    const contactBtn = document.getElementById("contactBtn");
    if (!contactBtn || !editor) {
      return;
    }

    const parent = contactBtn.parentElement;
    parent.style.display = "flex";
    parent.style.gap = "12px";
    parent.style.flexWrap = "wrap";
    parent.style.alignItems = "center";

    let actionHost = document.getElementById("profileActionHost");
    if (!actionHost) {
      actionHost = document.createElement("div");
      actionHost.id = "profileActionHost";
      actionHost.style.display = "flex";
      actionHost.style.gap = "12px";
      actionHost.style.flexWrap = "wrap";
      parent.appendChild(actionHost);
    }

    actionHost.innerHTML = "";

    if (editor.role === "editor") {
      const statsButton = document.createElement("button");
      statsButton.type = "button";
      statsButton.className = "btn-secondary";
      statsButton.innerHTML = `<i class="fas fa-briefcase"></i> ${escapeHtml(workStatsLabel(editor))}`;
      actionHost.appendChild(statsButton);
    }

    if (editor.can_edit) {
      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.className = "btn-secondary";
      editBtn.innerHTML = '<i class="fas fa-pen"></i> Edit Portfolio';
      editBtn.addEventListener("click", openDashboardProfileEditor);
      actionHost.appendChild(editBtn);

      if (editor.role === "editor") {
        const uploadBtn = document.createElement("button");
        uploadBtn.type = "button";
        uploadBtn.className = "btn-primary";
        uploadBtn.innerHTML = '<i class="fas fa-upload"></i> Upload';
        uploadBtn.addEventListener("click", openDashboardUploadModal);
        actionHost.appendChild(uploadBtn);
      }

      const logoutBtn = document.createElement("button");
      logoutBtn.type = "button";
      logoutBtn.className = "btn-secondary";
      logoutBtn.innerHTML = '<i class="fas fa-sign-out-alt"></i> Logout';
      logoutBtn.addEventListener("click", function () {
        window.logout();
      });
      actionHost.appendChild(logoutBtn);
    } else {
      const followBtn = document.createElement("button");
      followBtn.type = "button";
      followBtn.className = editor.is_following ? "btn-secondary" : "btn-primary";
      followBtn.innerHTML = editor.is_following
        ? '<i class="fas fa-user-check"></i> Following'
        : '<i class="fas fa-user-plus"></i> Follow';
      followBtn.addEventListener("click", async function () {
        if (!window.currentUser) {
          window.openModal("loginModal");
          return;
        }
        try {
          const payload = await postForm(
            `/api/follow/${encodeURIComponent(editor.username)}/toggle/`,
            {}
          );
          replaceState(payload);
          renderCurrentContexts();
          window.showToast(payload.message, "success");
        } catch (error) {
          window.showToast(error.message, "error");
        }
      });
      actionHost.appendChild(followBtn);
    }
  }

  function ensureFloatingUploadButton() {
    let button = document.getElementById("floatingUploadAction");
    if (!button) {
      button = document.createElement("button");
      button.id = "floatingUploadAction";
      button.className = "btn-primary";
      button.style.position = "fixed";
      button.style.right = "24px";
      button.style.bottom = "24px";
      button.style.zIndex = "1200";
      button.style.padding = "14px 20px";
      button.style.display = "none";
      button.innerHTML = '<i class="fas fa-upload"></i> Upload Video';
      button.addEventListener("click", openDashboardUploadModal);
      document.body.appendChild(button);
    }

    const shouldShow =
      Boolean(window.currentUser) &&
      isCurrentUserEditor() &&
      (window.currentPage === "home" || window.currentPage === "discover");
    button.style.display = shouldShow ? "inline-flex" : "none";
  }

  function editorByUsername(username) {
    return (window.__elaEditors || []).find((editor) => editor.username === username) || null;
  }

  window.getEditors = function () {
    return window.__elaEditors || [];
  };

  window.saveEditors = function (editors) {
    window.__elaEditors = Array.isArray(editors) ? editors : [];
    return window.__elaEditors;
  };

  window.getEditor = editorByUsername;

  window.updateEditor = function (username, updates) {
    const editors = window.__elaEditors || [];
    const index = editors.findIndex((editor) => editor.username === username);
    if (index === -1) {
      return null;
    }
    editors[index] = { ...editors[index], ...updates };
    return editors[index];
  };

  window.handleSignup = async function () {
    try {
      const formData = new FormData();
      formData.append("role", document.getElementById("signupRole")?.value || "editor");
      formData.append("cname", document.getElementById("signupCname")?.value.trim() || "");
      formData.append("username", document.getElementById("signupUsername").value.trim());
      formData.append("password", document.getElementById("signupPassword").value);
      formData.append("email", document.getElementById("signupEmail").value.trim());
      formData.append("bio", document.getElementById("signupBio").value.trim());
      const avatarFile = document.getElementById("signupAvatarFile");
      if (avatarFile && avatarFile.files && avatarFile.files[0]) {
        formData.append("avatar_file", avatarFile.files[0]);
      }

      const payload = await postMultipartForm("/auth/signup/", formData);

      replaceState(payload);
      if (document.getElementById("signupRole")) {
        document.getElementById("signupRole").value = "editor";
      }
      if (document.getElementById("signupCname")) {
        document.getElementById("signupCname").value = "";
      }
      document.getElementById("signupUsername").value = "";
      document.getElementById("signupPassword").value = "";
      document.getElementById("signupEmail").value = "";
      document.getElementById("signupBio").value = "";
      if (document.getElementById("signupAvatarFile")) {
        document.getElementById("signupAvatarFile").value = "";
      }
      window.closeModal("signupModal");
      window.showToast(payload.message, "success");
      window.navigate("profile", window.currentUser);
    } catch (error) {
      window.showToast(error.message, "error");
    }
  };

  window.handleLogin = async function () {
    try {
      const payload = await postForm("/auth/login/", {
        username: document.getElementById("loginUsername").value.trim(),
        password: document.getElementById("loginPassword").value,
      });

      replaceState(payload);
      document.getElementById("loginUsername").value = "";
      document.getElementById("loginPassword").value = "";
      window.closeModal("loginModal");
      window.showToast(payload.message, "success");
      window.navigate("profile", window.currentUser);
    } catch (error) {
      window.showToast(error.message, "error");
    }
  };

  window.logout = async function () {
    try {
      const payload = await postForm("/auth/logout/", {});
      replaceState(payload);
      window.showToast(payload.message, "info");
      window.navigate("home");
    } catch (error) {
      window.showToast(error.message, "error");
    }
  };

  window.saveProfile = async function () {
    try {
      const oldUsername = window.currentUser;
      const formData = new FormData();
      formData.append("username", document.getElementById("editUsername").value.trim());
      formData.append("cname", document.getElementById("editCname")?.value.trim() || "");
      formData.append("clients_served", document.getElementById("editClientsServed")?.value || "0");
      formData.append(
        "completed_projects",
        document.getElementById("editCompletedProjects")?.value || "0"
      );
      formData.append("bio", document.getElementById("editBio").value.trim());
      formData.append("avatar_url", document.getElementById("editAvatar").value.trim());
      const avatarInput = document.getElementById("editAvatarFile");
      if (avatarInput && avatarInput.files && avatarInput.files[0]) {
        formData.append("avatar_file", avatarInput.files[0]);
      }

      const payload = await postMultipartForm("/api/profile/", formData);

      replaceState(payload);
      if (
        oldUsername &&
        window.currentProfileUser === oldUsername &&
        window.currentUser === payload.updated_username
      ) {
        window.currentProfileUser = payload.updated_username;
        syncHistory("profile", payload.updated_username);
      }
      if (document.getElementById("editAvatarFile")) {
        document.getElementById("editAvatarFile").value = "";
      }
      renderCurrentContexts();
      window.showToast(payload.message, "success");
      window.navigate("profile", payload.updated_username || window.currentUser);
    } catch (error) {
      window.showToast(error.message, "error");
    }
  };

  window.saveContacts = async function () {
    try {
      const payload = await postForm("/api/contacts/", {
        email: document.getElementById("contactEmail").value.trim(),
        telegram: document.getElementById("contactTelegram").value.trim(),
        whatsapp: document.getElementById("contactWhatsapp").value.trim(),
        phone: document.getElementById("contactPhone").value.trim(),
        other_contacts_json: JSON.stringify(collectOtherContacts()),
      });

      replaceState(payload);
      renderCurrentContexts();
      window.showToast(payload.message, "success");
      window.navigate("profile", payload.updated_username || window.currentUser);
    } catch (error) {
      window.showToast(error.message, "error");
    }
  };

  window.saveVideo = async function () {
    if (!window.currentUser) {
      promptSignIn("Sign in to upload videos.");
      return;
    }
    if (!isCurrentUserEditor()) {
      window.showToast("Only editor accounts can upload videos.", "error");
      return;
    }

    const editId = document.getElementById("editVideoId").value;
    const endpoint = editId
      ? `/api/videos/${encodeURIComponent(editId)}/update/`
      : "/api/videos/create/";
    const fileInput = document.getElementById("videoFile");
    const sourceMode = document.getElementById("videoSourceMode")
      ? document.getElementById("videoSourceMode").value
      : "link";

    setVideoSaveButtonLoading(true);
    setVideoUploadFeedback(editId ? "Saving your video details..." : "Uploading your video...", "muted");

    try {
      const formData = new FormData();
      formData.append("title", document.getElementById("videoTitle").value.trim());
      formData.append("url", document.getElementById("videoUrl").value.trim());
      formData.append("video_source", sourceMode);
      formData.append("thumbnail_url", document.getElementById("videoThumb").value.trim());
      formData.append("content_type", document.getElementById("videoType").value);
      formData.append("category", document.getElementById("videoCategory").value);
      formData.append("duration", document.getElementById("videoDuration").value.trim());
      if (fileInput && fileInput.files && fileInput.files[0]) {
        formData.append("uploaded_file", fileInput.files[0]);
      }

      const payload = await postMultipartForm(endpoint, formData);

      replaceState(payload);
      setVideoUploadFeedback(payload.message || "Video uploaded successfully.", "success");
      window.closeModal("addVideoModal");
      resetVideoSourceControls("link");
      renderCurrentContexts();
      window.showToast(payload.message, "success");
      navigateToProfileAndOpenVideo(
        payload.profile_username || window.currentUser,
        payload.video_id || editId
      );
    } catch (error) {
      const message = error.message || "Upload failed.";
      setVideoUploadFeedback(message, "error");
      window.showToast(message, "error");
    } finally {
      setVideoSaveButtonLoading(false);
      if (!document.getElementById("addVideoModal")?.classList.contains("show")) {
        setVideoUploadFeedback("", "muted");
      }
    }
  };

  window.deleteVideo = async function (videoId) {
    try {
      const payload = await postForm(`/api/videos/${encodeURIComponent(videoId)}/delete/`, {});
      replaceState(payload);
      renderCurrentContexts();
      window.showToast(payload.message, "info");
    } catch (error) {
      window.showToast(error.message, "error");
    }
  };

  window.moveVideo = async function (videoId, index) {
    const direction = index > 0 ? "up" : "down";
    try {
      const payload = await postForm(`/api/videos/${encodeURIComponent(videoId)}/move/`, {
        direction,
      });
      replaceState(payload);
      renderCurrentContexts();
      window.showToast(payload.message, "success");
    } catch (error) {
      window.showToast(error.message, "error");
    }
  };

  window.playVideo = async function (username, videoId) {
    try {
      const payload = await postForm(
        `/api/profiles/${encodeURIComponent(username)}/videos/${encodeURIComponent(videoId)}/play/`,
        {}
      );
      replaceState(payload);
      const editor = editorByUsername(username);
      const video = editor ? editor.videos.find((item) => item.id === videoId) : null;
      openPlayerForVideo(editor, video);
    } catch (error) {
      window.showToast(error.message, "error");
    }
  };

  window.filterDiscover = async function () {
    const searchInput = document.getElementById("searchInput");
    const typeFilter = document.getElementById("typeFilter");
    const catFilter = document.getElementById("catFilter");
    if (!searchInput || !typeFilter || !catFilter || typeof window.renderDiscoverResults !== "function") {
      return;
    }

    const query = searchInput.value.trim();
    const selectedType = typeFilter.value || "all";
    const selectedCategory = catFilter.value || "all";

    if (selectedCategory !== "all") {
      setDiscoverCategoryState(selectedCategory);
      document.querySelectorAll("#filterChips .filter-chip").forEach((chip) => {
        chip.classList.toggle("active", chip.dataset.cat === selectedCategory);
      });
    } else {
      setDiscoverCategoryState("all");
      document.querySelectorAll("#filterChips .filter-chip").forEach((chip) => {
        chip.classList.toggle("active", chip.dataset.cat === "all");
      });
    }

    const params = new URLSearchParams({
      q: query,
      type: selectedType,
      category: selectedCategory,
    });

    try {
      const payload = await getJson(`/api/search/?${params.toString()}`);
      window.renderDiscoverResults(payload.editors || []);
    } catch (error) {
      window.showToast(error.message, "error");
    }
  };

  window.renderContactMethods = function (editor) {
    const container = document.getElementById("contactMethods");
    if (!container || !editor) {
      return;
    }

    const methods = [];
    if (editor.email) {
      methods.push({
        label: "Email",
        value: editor.email,
        href: `mailto:${editor.email}`,
        icon: "fas fa-envelope",
        bg: "rgba(234,67,53,0.15)",
        color: "#ea4335",
      });
    }
    if (editor.telegram) {
      methods.push({
        label: "Telegram",
        value: editor.telegram,
        href: `https://t.me/${editor.telegram.replace("@", "")}`,
        icon: "fab fa-telegram",
        bg: "rgba(0,136,204,0.15)",
        color: "#0088cc",
      });
    }
    if (editor.whatsapp) {
      methods.push({
        label: "WhatsApp",
        value: editor.whatsapp,
        href: `https://wa.me/${editor.whatsapp.replace(/[^0-9]/g, "")}`,
        icon: "fab fa-whatsapp",
        bg: "rgba(37,211,102,0.15)",
        color: "#25d366",
      });
    }
    if (editor.phone) {
      methods.push({
        label: "Phone",
        value: editor.phone,
        href: `tel:${editor.phone}`,
        icon: "fas fa-phone",
        bg: "var(--accent-glow)",
        color: "var(--accent)",
      });
    }
    (editor.other_contacts || []).forEach((contact) => {
      methods.push({
        label: contact.label,
        value: contact.value,
        href: contact.value,
        icon: "fas fa-link",
        bg: "rgba(255,140,66,0.15)",
        color: "#ff8c42",
      });
    });

    if (!methods.length) {
      container.innerHTML = '<p style="color:var(--text-muted);">No contact methods available</p>';
      return;
    }

    container.innerHTML = methods
      .map(
        (method, index) =>
          `<div style="display:flex;gap:10px;align-items:stretch;">` +
          `<a href="${escapeHtml(method.href)}" ${
            method.href.startsWith("http") ? 'target="_blank" rel="noopener noreferrer"' : ""
          } class="contact-method" style="flex:1;">` +
          `<div class="icon-wrap" style="background:${method.bg};color:${method.color};"><i class="${method.icon}"></i></div>` +
          `<div>` +
          `<div style="font-weight:600;font-size:0.9rem;">${escapeHtml(method.label)}</div>` +
          `<div style="color:var(--text-secondary);font-size:0.85rem;word-break:break-word;">${escapeHtml(method.value)}</div>` +
          `</div>` +
          `<i class="fas fa-external-link-alt" style="margin-left:auto;color:var(--text-muted);font-size:0.8rem;"></i>` +
          `</a>` +
          `<button type="button" class="btn-icon contact-copy-btn" data-copy-index="${index}" title="Copy ${method.label}">` +
          `<i class="fas fa-copy"></i>` +
          `</button>` +
          `</div>`
      )
      .join("");

    Array.from(container.querySelectorAll(".contact-copy-btn")).forEach((button) => {
      button.addEventListener("click", async function () {
        const method = methods[Number(this.dataset.copyIndex)];
        try {
          await copyTextToClipboard(method.value);
          window.showToast(`${method.label} copied`, "success");
        } catch (error) {
          window.showToast("Unable to copy that contact value.", "error");
        }
      });
    });
  };

  if (originalRenderFeatured) {
    window.renderFeatured = function () {
      const grid = document.getElementById("featuredGrid");
      if (!grid) {
        return;
      }

      const featured = (window.getEditors() || [])
        .filter((editor) => editor.role === "editor" && Array.isArray(editor.videos) && editor.videos.length)
        .sort(featuredEditorComparator)
        .slice(0, 6);

      grid.innerHTML = featured
        .map((editor) => {
          const rankedVideos = featuredSortedVideos(editor.videos || []);
          const topVideo = rankedVideos[0] || editor.videos[0];
          const totalViews = (editor.videos || []).reduce((sum, video) => sum + (video.views || 0), 0);
          const displayName = editor.display_name || editor.username;

          return (
            `<div class="editor-card card" onclick="navigate('profile','${editor.username}')">` +
            `<div class="card-thumb">` +
            `<img src="${escapeHtml(topVideo ? topVideo.thumb : editor.avatar)}" alt="${escapeHtml(displayName)}" loading="lazy">` +
            `<div class="play-icon"><i class="fas fa-play" style="margin-left:2px;"></i></div>` +
            `</div>` +
            `<div class="card-body">` +
            `<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">` +
            `<img src="${escapeHtml(editor.avatar)}" alt="" style="width:32px;height:32px;border-radius:50%;object-fit:cover;border:2px solid var(--accent);">` +
            `<div>` +
            `<div class="editor-name">${escapeHtml(displayName)}</div>` +
            `${
              displayName !== editor.username
                ? `<div class="editor-meta">@${escapeHtml(editor.username)}</div>`
                : ""
            }` +
            `</div>` +
            `</div>` +
            `<p style="color:var(--text-secondary);font-size:0.85rem;line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">${escapeHtml(editor.bio)}</p>` +
            `<div style="display:flex;gap:16px;margin-top:12px;flex-wrap:wrap;">` +
            `<span style="color:var(--text-muted);font-size:0.8rem;"><i class="fas fa-video" style="margin-right:4px;"></i>${editor.videos.length} videos</span>` +
            `<span style="color:var(--text-muted);font-size:0.8rem;"><i class="fas fa-eye" style="margin-right:4px;"></i>${window.formatNumber(totalViews)}</span>` +
            renderLikeSummaryMarkup(topVideo, true) +
            `</div>` +
            `<div style="margin-top:10px;">${renderAverageRatingMarkup(topVideo, true)}</div>` +
            `<div style="margin-top:12px;">${renderWorkStatsPill(editor, true)}</div>` +
            `${
              topVideo
                ? `<span class="badge" style="margin-top:12px;font-size:0.7rem;">${escapeHtml(topVideo.category)}</span>`
                : ""
            }` +
            `</div>` +
            `</div>`
          );
        })
        .join("");
    };
  }

  if (originalRenderDiscoverResults) {
    window.renderDiscoverResults = function (editors) {
      originalRenderDiscoverResults(editors);
      decorateDiscoverCards(editors);
      highlightSignedInDiscoverCards(editors);
    };
  }

  if (originalRenderProfileVideos) {
    window.renderProfileVideos = function () {
      originalRenderProfileVideos();
      decorateProfileVideoCards();
    };
  }

  if (originalRenderProfile) {
    window.renderProfile = function (username) {
      originalRenderProfile(username);
      const editor = editorByUsername(username);
      if (!editor) {
        return;
      }

      const profileName = document.getElementById("profileName");
      if (profileName) {
        profileName.textContent = editor.display_name || editor.username;
        let handle = document.getElementById("profileUsernameHandle");
        if (!handle) {
          handle = document.createElement("div");
          handle.id = "profileUsernameHandle";
          handle.style.color = "var(--text-secondary)";
          handle.style.marginTop = "6px";
          handle.style.fontSize = "0.95rem";
          profileName.insertAdjacentElement("afterend", handle);
        }
        handle.textContent =
          editor.display_name && editor.display_name !== editor.username ? `@${editor.username}` : "";
      }

      const badge = document.getElementById("profileBadge");
      if (badge) {
        badge.textContent =
          editor.role === "editor"
            ? `${editor.role_label} \u00B7 ${editor.videos.length} video${editor.videos.length === 1 ? "" : "s"}`
            : `${editor.role_label} Account`;
      }

      const stats = document.getElementById("profileStats");
      if (stats) {
        const shortCount = editor.videos.filter((video) => video.type === "short").length;
        const longCount = editor.videos.filter((video) => video.type === "long").length;
        const totalViews = editor.videos.reduce((sum, video) => sum + (video.views || 0), 0);
        const contactCount =
          [editor.email, editor.telegram, editor.whatsapp, editor.phone].filter(Boolean).length +
          (editor.other_contacts || []).length;
        if (editor.role === "editor") {
          stats.innerHTML =
            `<div class="profile-stat"><div class="num">${shortCount}</div><div class="label">Short</div></div>` +
            `<div class="profile-stat"><div class="num">${longCount}</div><div class="label">Long</div></div>` +
            `<div class="profile-stat"><div class="num">${window.formatNumber(totalViews)}</div><div class="label">Views</div></div>` +
            `<div class="profile-stat"><div class="num">${editor.followers_count || 0}</div><div class="label">Followers</div></div>`;
        } else {
          stats.innerHTML =
            `<div class="profile-stat"><div class="num">${editor.followers_count || 0}</div><div class="label">Followers</div></div>` +
            `<div class="profile-stat"><div class="num">${editor.following_count || 0}</div><div class="label">Following</div></div>` +
            `<div class="profile-stat"><div class="num">${contactCount}</div><div class="label">Contacts</div></div>`;
        }
      }

      const tabs = document.getElementById("profileTabs");
      const filters = document.getElementById("profileCatFilters");
      if (tabs && filters) {
        const showPortfolio = editor.role === "editor";
        tabs.style.display = showPortfolio ? "" : "none";
        filters.style.display = showPortfolio ? "" : "none";
        if (!showPortfolio) {
          const shortEmpty = document.getElementById("shortEmpty");
          if (shortEmpty) {
            shortEmpty.style.display = "block";
            shortEmpty.textContent = "This client account is here to connect and collaborate.";
          }
          document.getElementById("shortVideoList").innerHTML = "";
          document.getElementById("longVideoList").innerHTML = "";
          document.getElementById("longContent").style.display = "none";
          document.getElementById("shortContent").style.display = "block";
        }
      }

      renderProfileActionButtons(editor);
      window.renderContactMethods(editor);
      ensureFloatingUploadButton();
    };
  }

  if (originalRenderDashboard) {
    window.renderDashboard = function () {
      originalRenderDashboard();
      ensureDashboardEnhancements();
      const editor = currentViewerProfile();
      if (!editor) {
        return;
      }

      document.getElementById("dashUsername").textContent = editor.display_name || editor.username;
      document.getElementById("dashProfileUrl").textContent = `${window.location.origin}/${editor.username}`;
      document.getElementById("editUsername").value = editor.username;
      document.getElementById("editBio").value = editor.bio || "";
      document.getElementById("editAvatar").value = editor.avatar_url || "";
      if (document.getElementById("editCname")) {
        document.getElementById("editCname").value = editor.cname || "";
      }
      if (document.getElementById("editClientsServed")) {
        document.getElementById("editClientsServed").value = editor.clients_served || 0;
      }
      if (document.getElementById("editCompletedProjects")) {
        document.getElementById("editCompletedProjects").value = editor.completed_projects || 0;
      }
      if (document.getElementById("editAvatarFileStatus")) {
        document.getElementById("editAvatarFileStatus").textContent = editor.has_custom_avatar
          ? "A profile image is already saved. Upload a new file to replace it."
          : "Upload a local image to replace the generated profile image.";
      }

      populateOtherContactsRows(editor.other_contacts || []);
      renderSetupNotice(editor);

      const videosTabButton = document.querySelector('[data-dtab="videos"]');
      const dashVideosTab = document.getElementById("dashVideosTab");
      const addVideoButtons = document.querySelectorAll(
        '[onclick*="openAddVideoModal"], [onclick*="addVideoModal"]'
      );
      if (editor.role === "client") {
        if (videosTabButton) {
          videosTabButton.style.display = "none";
        }
        if (dashVideosTab) {
          dashVideosTab.style.display = "none";
        }
        addVideoButtons.forEach((button) => {
          button.style.display = "none";
        });
        if ((window.__elaActiveDashboardTab || "videos") === "videos") {
          window.__elaActiveDashboardTab = "profile";
          if (typeof window.switchDashTab === "function") {
            window.switchDashTab("profile");
          }
        }
      } else {
        if (videosTabButton) {
          videosTabButton.style.display = "";
        }
        addVideoButtons.forEach((button) => {
          button.style.display = "";
        });
      }

      ensureFloatingUploadButton();
    };
  }

  if (originalSwitchDashTab) {
    window.switchDashTab = function (tab) {
      window.__elaActiveDashboardTab = tab;
      return originalSwitchDashTab(tab);
    };
  }

  if (typeof window.switchProfileTab === "function") {
    const originalSwitchProfileTab = window.switchProfileTab;
    window.switchProfileTab = function (tab) {
      const result = originalSwitchProfileTab(tab);
      syncRouteGlobals();
      return result;
    };
  }

  if (typeof window.setProfileCatFilter === "function") {
    const originalSetProfileCatFilter = window.setProfileCatFilter;
    window.setProfileCatFilter = function (el) {
      const result = originalSetProfileCatFilter(el);
      syncRouteGlobals();
      return result;
    };
  }

  if (originalOpenAddVideoModal) {
    window.openAddVideoModal = function () {
      originalOpenAddVideoModal();
      resetVideoSourceControls("link");
      setVideoSaveButtonLoading(false);
      setVideoUploadFeedback("", "muted");
    };
  }

  if (originalEditVideo) {
    window.editVideo = function (videoId) {
      originalEditVideo(videoId);
      ensureVideoSourceControls();
      setVideoSaveButtonLoading(false);
      setVideoUploadFeedback("", "muted");
      const editor = editorByUsername(window.currentUser);
      const video = editor ? editor.videos.find((item) => item.id === videoId) : null;
      if (!video) {
        return;
      }
      clearPendingUploadSelection();
      setVideoSourceMode(video.video_source || "link", video.uploaded_file_name || "");
    };
  }

  if (originalNavigate) {
    window.navigate = function (page, data) {
      originalNavigate(page, data);
      syncRouteGlobals();
      syncHistory(page, data);
    };

    function routeFromPath() {
      const path = window.location.pathname.replace(/^\/+|\/+$/g, "");
      if (!path) {
        originalNavigate("home");
        return;
      }

      if (path === "discover") {
        originalNavigate("discover");
        return;
      }

      if (path === "dashboard") {
        if (window.currentUser) {
          originalNavigate("dashboard");
        } else {
          originalNavigate("home");
          window.openModal("loginModal");
        }
        return;
      }

      if (editorByUsername(path)) {
        originalNavigate("profile", path);
        return;
      }

      originalNavigate("home");
    }

    document.addEventListener("DOMContentLoaded", routeFromPath);
    window.addEventListener("popstate", routeFromPath);
  }

  document.getElementById("videoPlayerModal")?.addEventListener("ela:before-close", function () {
    teardownPlayerModal();
  });

  replaceState(bootstrap);
  syncRouteGlobals();
  if (!window.__elaActiveDashboardTab) {
    window.__elaActiveDashboardTab = "videos";
  }
  ensureSignupEnhancements();
  ensureDashboardEnhancements();
  ensureVideoSourceControls();
  ensureFloatingUploadButton();
})();
