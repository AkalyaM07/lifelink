/**
 * LIFE-LINK Frontend API Client & Central User Session Management
 * Clean vanilla JS communicating with FastAPI backend.
 * Supports:
 * - Single Normal User Account (Requester, Donor, Notifications, History)
 * - Multilingual AI Chat & Confirmation
 * - Intelligent Proximity Matching & Adaptive Cascade
 * - Real Backend State Tracking (No Hallucinations)
 * - 3 Separate States: DONOR WILLING -> HOSPITAL CONFIRMED -> DONATION COMPLETED
 * - Blood Requests You Can Help With Feed
 * - Configurable Eligibility Reminders
 */

// ====================================================
// 1. CENTRAL API CONFIGURATION
// ====================================================
// Automatically switches to local server during local testing, or deployed backend on Render
// ====================================================
// 1. CENTRAL API CONFIGURATION
// ====================================================
// Automatically switches to local server during local testing, or deployed backend on Render
const API_BASE = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ? 'http://127.0.0.1:8000'
  : 'https://lifelink-backend-qrk8.onrender.com';
function handleFetchError(err, actionDescription) {
  console.error(`API Error (${actionDescription}):`, err);
  if (err instanceof TypeError && err.message.toLowerCase().includes("fetch")) {
    throw new Error("Unable to connect to the Life-Link server. Please verify backend is running.");
  }
  throw err;
}

// ====================================================
// 2. CENTRAL API CLIENT
// ====================================================
const LifeLinkAPI = {
  // --- Health & Demo Seeding ---
  async checkHealth() {
    try {
      const res = await fetch(`${API_BASE}/`, { method: "GET" });
      if (!res.ok) return null;
      return await res.json();
    } catch (err) {
      console.warn("Backend offline or unreachable:", err);
      return null;
    }
  },

  async seedDemoData(force = false) {
    try {
      const url = force ? `${API_BASE}/seed-demo-data?force=true` : `${API_BASE}/seed-demo-data`;
      const res = await fetch(url, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to seed demo data");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "seedDemoData");
    }
  },

  // --- Single Normal User Account (Auth & Profile) ---
  async registerUser(userData) {
    try {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(userData)
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Registration failed");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "registerUser");
    }
  },

  async loginUser(email, password) {
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Invalid email or password");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "loginUser");
    }
  },

  async getUsers() {
    try {
      const res = await fetch(`${API_BASE}/users`);
      if (!res.ok) throw new Error("Failed to fetch users");
      return await res.json();
    } catch (err) {
      handleFetchError(err, "getUsers");
    }
  },

  async getUser(userId) {
    try {
      const res = await fetch(`${API_BASE}/users/${userId}`);
      if (!res.ok) throw new Error(`User #${userId} not found`);
      return await res.json();
    } catch (err) {
      handleFetchError(err, `getUser ${userId}`);
    }
  },

  async updateUserProfile(userId, profileData) {
    try {
      const res = await fetch(`${API_BASE}/users/${userId}/profile`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profileData)
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to update profile");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "updateUserProfile");
    }
  },

  async updateUserAvailability(userId, availability) {
    try {
      const res = await fetch(`${API_BASE}/users/${userId}/availability`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ availability })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to update availability");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "updateUserAvailability");
    }
  },

  async getUserEmergencies(userId) {
    try {
      const res = await fetch(`${API_BASE}/users/${userId}/emergency-requests`);
      if (!res.ok) return [];
      return await res.json();
    } catch (err) {
      handleFetchError(err, "getUserEmergencies");
    }
  },

  async getUserDonorResponses(userId) {
    try {
      const res = await fetch(`${API_BASE}/users/${userId}/donor-responses`);
      if (!res.ok) return [];
      return await res.json();
    } catch (err) {
      handleFetchError(err, "getUserDonorResponses");
    }
  },

  async getUserNotifications(userId) {
    try {
      const res = await fetch(`${API_BASE}/users/${userId}/notifications`);
      if (!res.ok) return [];
      return await res.json();
    } catch (err) {
      handleFetchError(err, "getUserNotifications");
    }
  },

  async markNotificationRead(userId, notifId) {
    try {
      const res = await fetch(`${API_BASE}/users/${userId}/notifications/${notifId}/read`, {
        method: "PATCH"
      });
      if (!res.ok) throw new Error("Failed to mark notification read");
      return await res.json();
    } catch (err) {
      handleFetchError(err, "markNotificationRead");
    }
  },

  async markAllNotificationsRead(userId) {
    try {
      const res = await fetch(`${API_BASE}/users/${userId}/notifications/read-all`, {
        method: "POST"
      });
      if (!res.ok) throw new Error("Failed to mark all notifications read");
      return await res.json();
    } catch (err) {
      handleFetchError(err, "markAllNotificationsRead");
    }
  },

  async getUserDonations(userId) {
    try {
      const res = await fetch(`${API_BASE}/users/${userId}/donations`);
      if (!res.ok) return [];
      return await res.json();
    } catch (err) {
      handleFetchError(err, "getUserDonations");
    }
  },

  // --- Blood Requests You Can Help With Feed (Discovery Path 2) ---
  async getMatchedRequestsForUser(userId) {
    try {
      const res = await fetch(`${API_BASE}/users/${userId}/matched-requests`);
      if (!res.ok) return [];
      return await res.json();
    } catch (err) {
      handleFetchError(err, "getMatchedRequestsForUser");
    }
  },

  // --- Interactive AI Bot & Confirmation ---
  async aiChat(payload) {
    try {
      const res = await fetch(`${API_BASE}/ai/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "AI Chat failed to respond");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "aiChat");
    }
  },

  async confirmEmergency(payload) {
    try {
      const res = await fetch(`${API_BASE}/ai/confirm-emergency`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to confirm emergency request");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "confirmEmergency");
    }
  },

  async parseAIRequest(message, autoCreate = false, contactPhone = "+91 94433 00000", userId = null, requesterName = null) {
    try {
      const res = await fetch(`${API_BASE}/ai/parse-request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          auto_create: autoCreate,
          contact_phone: contactPhone,
          user_id: userId,
          requester_name: requesterName
        })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail?.message || err.detail || "AI parser failed to process request");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "parseAIRequest");
    }
  },

  // --- Emergency Requests & Matching ---
  async getEmergencyRequests(statusFilter = null) {
    try {
      let url = `${API_BASE}/emergency-requests`;
      if (statusFilter) url += `?status_filter=${encodeURIComponent(statusFilter)}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to fetch emergency requests");
      return await res.json();
    } catch (err) {
      handleFetchError(err, "getEmergencyRequests");
    }
  },

  async getEmergencyRequest(requestId) {
    try {
      const res = await fetch(`${API_BASE}/emergency-requests/${requestId}`);
      if (!res.ok) throw new Error(`Emergency request #${requestId} not found`);
      return await res.json();
    } catch (err) {
      handleFetchError(err, `getEmergencyRequest ${requestId}`);
    }
  },

  async createEmergencyRequest(requestData) {
    try {
      const res = await fetch(`${API_BASE}/emergency-requests`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestData)
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const msg = typeof err.detail === "string" ? err.detail : (err.detail?.message || "Failed to create emergency request");
        throw new Error(msg);
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "createEmergencyRequest");
    }
  },

  async getMatches(requestId, maxDistanceKm = null) {
    try {
      let url = `${API_BASE}/emergency-requests/${requestId}/matches`;
      if (maxDistanceKm) url += `?max_distance_km=${maxDistanceKm}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to fetch compatible matches");
      return await res.json();
    } catch (err) {
      handleFetchError(err, "getMatches");
    }
  },

  async getCascade(requestId) {
    try {
      const res = await fetch(`${API_BASE}/emergency-requests/${requestId}/cascade`);
      if (!res.ok) throw new Error("Failed to execute cascade search");
      return await res.json();
    } catch (err) {
      handleFetchError(err, "getCascade");
    }
  },

  // --- State 1: Donor Response ---
  async respondToEmergency(requestId, payload) {
    try {
      const res = await fetch(`${API_BASE}/emergency-requests/${requestId}/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to register donor response");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "respondToEmergency");
    }
  },

  // --- State 2: Hospital Confirmation ---
  async hospitalConfirm(requestId, notes = null) {
    try {
      const res = await fetch(`${API_BASE}/emergency-requests/${requestId}/hospital-confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to confirm hospital verification");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "hospitalConfirm");
    }
  },

  // --- State 3: Screening & Complete Donation ---
  async screeningUpdate(requestId, payload) {
    try {
      const res = await fetch(`${API_BASE}/emergency-requests/${requestId}/screening-update`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to record screening outcome");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "screeningUpdate");
    }
  },

  async completeDonation(requestId, payload) {
    try {
      const res = await fetch(`${API_BASE}/emergency-requests/${requestId}/complete-donation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to complete donation record");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "completeDonation");
    }
  },

  // --- Backward Compatible Donor Endpoints ---
  async getDonors(bloodGroup = null, availability = null) {
    try {
      let url = `${API_BASE}/donors`;
      const params = new URLSearchParams();
      if (bloodGroup) params.append("blood_group", bloodGroup);
      if (availability) params.append("availability", availability);
      if (params.toString()) url += `?${params.toString()}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to fetch donors list");
      return await res.json();
    } catch (err) {
      handleFetchError(err, "getDonors");
    }
  },

  async getDonor(donorId) {
    try {
      const res = await fetch(`${API_BASE}/donors/${donorId}`);
      if (!res.ok) throw new Error(`Donor #${donorId} not found`);
      return await res.json();
    } catch (err) {
      handleFetchError(err, `getDonor ${donorId}`);
    }
  },

  async updateDonorAvailability(donorId, status) {
    try {
      const res = await fetch(`${API_BASE}/donors/${donorId}/availability`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ availability: status })
      });
      if (!res.ok) throw new Error("Failed to update donor availability");
      return await res.json();
    } catch (err) {
      handleFetchError(err, "updateDonorAvailability");
    }
  }
};


// ====================================================
// 3. SINGLE CENTRAL USER SESSION MANAGEMENT
// ====================================================
const LifeLinkAuth = {
  USER_STORAGE_KEY: "lifelink_current_user",
  AUTH_FLAG_KEY: "lifelink_auth_verified",  // Only set on explicit login/signup

  async getCurrentUser() {
    // Require auth flag — must have been set by login or signup
    const authFlag = localStorage.getItem(this.AUTH_FLAG_KEY);
    if (!authFlag) {
      // No authenticated session — clear any stale user data and return null
      localStorage.removeItem(this.USER_STORAGE_KEY);
      return null;
    }

    const saved = localStorage.getItem(this.USER_STORAGE_KEY);
    if (!saved) {
      localStorage.removeItem(this.AUTH_FLAG_KEY);
      return null;
    }
    try {
      const parsed = JSON.parse(saved);
      if (!parsed || !parsed.id) {
        this._clearSession();
        return null;
      }
      // Refresh latest state from server if reachable
      try {
        const fresh = await LifeLinkAPI.getUser(parsed.id);
        if (fresh) {
          // Update user data but keep auth flag intact
          localStorage.setItem(this.USER_STORAGE_KEY, JSON.stringify(fresh));
          window.dispatchEvent(new CustomEvent("lifelink_user_changed", { detail: fresh }));
          return fresh;
        }
      } catch (e) {
        // If offline or fetch error, return cached session
      }
      return parsed;
    } catch (e) {
      this._clearSession();
      return null;
    }
  },

  _clearSession() {
    localStorage.removeItem(this.USER_STORAGE_KEY);
    localStorage.removeItem(this.AUTH_FLAG_KEY);
  },

  setCurrentUser(user) {
    if (user) {
      localStorage.setItem(this.USER_STORAGE_KEY, JSON.stringify(user));
      // Set auth flag — marks this as an explicitly authenticated session
      localStorage.setItem(this.AUTH_FLAG_KEY, "1");
    } else {
      this._clearSession();
    }
    window.dispatchEvent(new CustomEvent("lifelink_user_changed", { detail: user }));
  },

  logout() {
    this._clearSession();
    window.dispatchEvent(new CustomEvent("lifelink_user_changed", { detail: null }));
    window.location.href = "login.html";
  },

  async requireAuth() {
    const user = await this.getCurrentUser();
    if (!user) {
      window.location.href = "login.html";
      return null;
    }
    return user;
  },

  async switchUser(userId) {
    // switchUser switches the active profile but requires an existing authenticated session
    const authFlag = localStorage.getItem(this.AUTH_FLAG_KEY);
    if (!authFlag) {
      window.location.href = "login.html";
      return null;
    }
    const user = await LifeLinkAPI.getUser(userId);
    if (user) {
      localStorage.setItem(this.USER_STORAGE_KEY, JSON.stringify(user));
      window.dispatchEvent(new CustomEvent("lifelink_user_changed", { detail: user }));
      showToast(`Switched active account to ${user.name} (${user.blood_group})`, "info");
      return user;
    }
  },

  async initNavbarUser(containerElement) {
    if (!containerElement) return;
    try {
      const currentUser = await this.getCurrentUser();
      if (!currentUser) {
        containerElement.innerHTML = `
          <div style="display: flex; align-items: center; gap: 0.6rem;">
            <a href="login.html" class="btn btn-primary btn-sm" style="text-decoration: none; padding: 4px 12px; font-weight: 700;">Login / Sign Up</a>
          </div>
        `;
        return;
      }

      let unreadCount = 0;
      try {
        const notifs = await LifeLinkAPI.getUserNotifications(currentUser.id);
        unreadCount = notifs.filter(n => !n.is_read).length;
      } catch (e) {}

      const availBadgeColor = currentUser.availability === "AVAILABLE" ? "badge-green" : currentUser.availability === "REVIEW_NEEDED" ? "badge-amber" : "badge-red";

      containerElement.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.6rem;">
          <a href="account.html" class="nav-user-pill" title="View Central User Account">
            <span>👤</span>
            <span><strong>${escapeHtml(currentUser.name)}</strong> (${escapeHtml(currentUser.blood_group)})</span>
            <span class="badge ${availBadgeColor}" style="font-size: 0.68rem; padding: 2px 6px;">${escapeHtml(currentUser.availability)}</span>
          </a>
          <a href="notifications.html" style="position: relative; text-decoration: none; font-size: 1.15rem;" title="Notifications">
            🔔
            ${unreadCount > 0 ? `<span style="position: absolute; top: -6px; right: -6px; background: #ef4444; color: white; font-size: 0.68rem; font-weight: 800; border-radius: 999px; padding: 1px 5px;">${unreadCount}</span>` : ""}
          </a>
          <button type="button" onclick="LifeLinkAuth.logout()" class="btn btn-secondary btn-sm" style="padding: 4px 10px; font-size: 0.78rem;" title="Logout">Logout</button>
        </div>
      `;
    } catch (err) {
      console.warn("Could not init navbar user pill:", err);
    }
  }
};


// ====================================================
// 4. SPEECH RECOGNITION HELPER
// ====================================================
const SpeechHelper = {
  recognition: null,
  isSupported() {
    return 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
  },
  start(onResult, onError, onEnd) {
    if (!this.isSupported()) {
      onError("Voice input is not supported in this browser. Please type your emergency request.");
      return;
    }
    const SpeechClass = window.SpeechRecognition || window.webkitSpeechRecognition;
    this.recognition = new SpeechClass();
    this.recognition.lang = 'en-IN'; // Tanglish & Indian English friendly
    this.recognition.interimResults = false;
    this.recognition.maxAlternatives = 1;

    this.recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      onResult(transcript);
    };

    this.recognition.onerror = (event) => {
      onError("Speech recognition error: " + event.error);
    };

    this.recognition.onend = () => {
      if (onEnd) onEnd();
    };

    try {
      this.recognition.start();
    } catch (err) {
      onError("Could not start microphone: " + err.message);
    }
  },
  stop() {
    if (this.recognition) {
      try { this.recognition.stop(); } catch (e) {}
    }
  }
};


// ====================================================
// 5. TOAST NOTIFICATION UTILITY
// ====================================================
function showToast(message, type = "info") {
  let toastContainer = document.getElementById("toast-container");
  if (!toastContainer) {
    toastContainer = document.createElement("div");
    toastContainer.id = "toast-container";
    toastContainer.style.position = "fixed";
    toastContainer.style.bottom = "24px";
    toastContainer.style.right = "24px";
    toastContainer.style.zIndex = "9999";
    toastContainer.style.display = "flex";
    toastContainer.style.flexDirection = "column";
    toastContainer.style.gap = "8px";
    toastContainer.style.pointerEvents = "none";
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement("div");
  toast.style.pointerEvents = "auto";
  toast.style.background = type === "error" ? "#ef4444" : type === "success" ? "#10b981" : type === "warning" ? "#f59e0b" : "#0284c7";
  toast.style.color = "white";
  toast.style.padding = "12px 18px";
  toast.style.borderRadius = "10px";
  toast.style.boxShadow = "0 8px 24px rgba(0,0,0,0.18)";
  toast.style.fontWeight = "600";
  toast.style.fontSize = "0.92rem";
  toast.style.display = "flex";
  toast.style.alignItems = "center";
  toast.style.gap = "10px";
  toast.style.maxWidth = "420px";
  toast.style.transition = "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)";
  toast.style.opacity = "0";
  toast.style.transform = "translateY(12px)";

  const icon = type === "error" ? "⚠️" : type === "success" ? "✅" : type === "warning" ? "🔔" : "ℹ️";
  toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;

  toastContainer.appendChild(toast);

  requestAnimationFrame(() => {
    toast.style.opacity = "1";
    toast.style.transform = "translateY(0)";
  });

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
    setTimeout(() => toast.remove(), 300);
  }, 4500);
}

function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.innerText = text;
  return div.innerHTML;
}
window.escapeHtml = escapeHtml;

