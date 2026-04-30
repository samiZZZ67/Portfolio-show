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

  function replaceState(payload) {
    const editors = Array.isArray(payload.editors) ? payload.editors : [];
    window.__elaBootstrap = payload;
    window.__elaEditors = editors;
    window.currentUser = payload.current_user || null;

    if (window.currentUser) {
      localStorage.setItem("ela_current_user", window.currentUser);
    } else {
      localStorage.removeItem("ela_current_user");
    }
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
  }

  function openPlayerForVideo(editor, video) {
    if (!editor || !video) {
      return;
    }

    document.getElementById("playerTitle").textContent = video.title;
    document.getElementById("playerCategory").textContent = video.category;
    document.getElementById("playerType").textContent =
      video.type === "short" ? "Short Content" : "Long Content";
    document.getElementById("playerViews").textContent = `${window.formatNumber(video.views)} views`;

    if (video.has_uploaded_file && video.playback_url) {
      document.getElementById("playerContainer").innerHTML =
        `<video src="${video.playback_url}" controls autoplay ` +
        'style="width:100%;height:100%;background:#000;" playsinline></video>';
    } else {
      const embedUrl = window.getEmbedUrl(video.url);
      document.getElementById("playerContainer").innerHTML =
        `<iframe src="${embedUrl}" style="width:100%;height:100%;border:none;" ` +
        'allow="accelerometer;autoplay;clipboard-write;encrypted-media;gyroscope;picture-in-picture" ' +
        "allowfullscreen></iframe>";
    }

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
      const payload = await postForm("/auth/signup/", {
        username: document.getElementById("signupUsername").value.trim(),
        password: document.getElementById("signupPassword").value,
        email: document.getElementById("signupEmail").value.trim(),
        bio: document.getElementById("signupBio").value.trim(),
      });

      replaceState(payload);
      document.getElementById("signupUsername").value = "";
      document.getElementById("signupPassword").value = "";
      document.getElementById("signupEmail").value = "";
      document.getElementById("signupBio").value = "";
      window.closeModal("signupModal");
      window.showToast(payload.message, "success");
      window.navigate("dashboard");
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
      window.navigate("dashboard");
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
      const payload = await postForm("/api/profile/", {
        bio: document.getElementById("editBio").value.trim(),
        avatar_url: document.getElementById("editAvatar").value.trim(),
      });

      replaceState(payload);
      renderCurrentContexts();
      window.showToast(payload.message, "success");
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
      });

      replaceState(payload);
      renderCurrentContexts();
      window.showToast(payload.message, "success");
    } catch (error) {
      window.showToast(error.message, "error");
    }
  };

  window.saveVideo = async function () {
    const editId = document.getElementById("editVideoId").value;
    const endpoint = editId
      ? `/api/videos/${encodeURIComponent(editId)}/update/`
      : "/api/videos/create/";
    const fileInput = document.getElementById("videoFile");
    const sourceMode = document.getElementById("videoSourceMode")
      ? document.getElementById("videoSourceMode").value
      : "link";

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
      window.closeModal("addVideoModal");
      resetVideoSourceControls("link");
      renderCurrentContexts();
      window.showToast(payload.message, "success");
    } catch (error) {
      window.showToast(error.message, "error");
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
      window.currentDiscoverCat = selectedCategory;
      document.querySelectorAll("#filterChips .filter-chip").forEach((chip) => {
        chip.classList.toggle("active", chip.dataset.cat === selectedCategory);
      });
    } else {
      window.currentDiscoverCat = "all";
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

  if (originalSwitchDashTab) {
    window.switchDashTab = function (tab) {
      window.__elaActiveDashboardTab = tab;
      return originalSwitchDashTab(tab);
    };
  }

  if (originalOpenAddVideoModal) {
    window.openAddVideoModal = function () {
      originalOpenAddVideoModal();
      resetVideoSourceControls("link");
    };
  }

  if (originalEditVideo) {
    window.editVideo = function (videoId) {
      originalEditVideo(videoId);
      ensureVideoSourceControls();
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

  replaceState(bootstrap);
  if (!window.__elaActiveDashboardTab) {
    window.__elaActiveDashboardTab = "videos";
  }
  ensureVideoSourceControls();
})();
