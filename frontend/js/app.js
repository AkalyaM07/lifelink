/**
 * LIFE-LINK Frontend API Client & State Management
 * Clean vanilla JS communicating with FastAPI backend.
 * Phase 6: Polished Error Handling, Privacy-Safe Formatting, and Seamless State Management.
 */

// ====================================================
// CENTRAL API CONFIGURATION
// ====================================================
// Production deployed backend URL on Render:
const API_BASE = "https://lifelink-2ldt.onrender.com";

// Helper for friendly network error messages
function handleFetchError(err, actionDescription) {
  console.error(`API Error (${actionDescription}):`, err);
  if (err instanceof TypeError && err.message.toLowerCase().includes("fetch")) {
    throw new Error("Unable to connect to the Life-Link server. Please try again in a moment.");
  }
  throw err;
}

const LifeLinkAPI = {
  // 1. Health check & Seeding
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

  async seedDemoData() {
    try {
      const res = await fetch(`${API_BASE}/seed-demo-data`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to seed demo data");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "seedDemoData");
    }
  },

  // 2. Donors
  async getDonors(bloodGroup = null, availability = null) {
    try {
      let url = `${API_BASE}/donors`;
      const params = new URLSearchParams();
      if (bloodGroup) params.append("blood_group", bloodGroup);
      if (availability) params.append("availability", availability);
      if (params.toString()) url += `?${params.toString()}`;

      const res = await fetch(url);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to fetch donors list");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "getDonors");
    }
  },

  async getDonor(donorId) {
    try {
      const res = await fetch(`${API_BASE}/donors/${donorId}`);
      if (!res.ok) {
        throw new Error(`Donor #${donorId} not found`);
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, `getDonor ${donorId}`);
    }
  },

  async registerDonor(donorData) {
    try {
      const res = await fetch(`${API_BASE}/donors`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(donorData)
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Donor registration failed. Please check input values.");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "registerDonor");
    }
  },

  async updateDonorAvailability(donorId, status) {
    try {
      const res = await fetch(`${API_BASE}/donors/${donorId}/availability`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ availability: status })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to update availability status");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "updateDonorAvailability");
    }
  },

  // 3. Emergency Requests
  async getEmergencyRequests(statusFilter = null) {
    try {
      let url = `${API_BASE}/emergency-requests`;
      if (statusFilter) url += `?status_filter=${encodeURIComponent(statusFilter)}`;
      const res = await fetch(url);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to fetch emergency requests");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "getEmergencyRequests");
    }
  },

  async getEmergencyRequest(requestId) {
    try {
      const res = await fetch(`${API_BASE}/emergency-requests/${requestId}`);
      if (!res.ok) {
        throw new Error(`Emergency request #${requestId} not found`);
      }
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

  // 4. AI Request Understanding & Text Creation
  async parseAIRequest(message, autoCreate = false, contactPhone = "+91 94433 00000") {
    try {
      const res = await fetch(`${API_BASE}/ai/parse-request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: message,
          auto_create: autoCreate,
          contact_phone: contactPhone
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

  async createEmergencyFromText(message, contactPhone = "+91 94433 00000") {
    try {
      const res = await fetch(`${API_BASE}/ai/create-emergency-from-text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: message,
          contact_phone: contactPhone
        })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail?.message || err.detail || "Failed to create emergency from text");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "createEmergencyFromText");
    }
  },

  // 5. Phase 2 Matching & Phase 3 Cascade
  async getMatches(requestId, maxDistanceKm = null) {
    try {
      let url = `${API_BASE}/emergency-requests/${requestId}/matches`;
      if (maxDistanceKm) url += `?max_distance_km=${maxDistanceKm}`;
      const res = await fetch(url);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to fetch compatible matches");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "getMatches");
    }
  },

  async getCascade(requestId) {
    try {
      const res = await fetch(`${API_BASE}/emergency-requests/${requestId}/cascade`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to execute cascade search");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "getCascade");
    }
  },

  // 6. Phase 5 Donor Interaction Response
  async respondToEmergency(requestId, donorId, action = "ACCEPT") {
    try {
      const res = await fetch(`${API_BASE}/emergency-requests/${requestId}/respond`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          donor_id: donorId,
          action: action
        })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to register donor response");
      }
      return await res.json();
    } catch (err) {
      handleFetchError(err, "respondToEmergency");
    }
  }
};


// Simple browser speech recognition helper
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
    this.recognition.lang = 'en-IN'; // Indian English / Tanglish friendly
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


// Toast notification helper with smooth animation
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

  // Trigger smooth entrance
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
