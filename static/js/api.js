/**
 * STOCKSENSE - REST API Client & Audio Feedback Engine
 */

const API_BASE = window.location.origin;

// Audio Feedback System using Web Audio API
class SoundFX {
  constructor() {
    this.ctx = null;
  }

  init() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) this.ctx = new AudioCtx();
    }
  }

  playBeep(freq = 600, duration = 0.08, type = 'sine') {
    try {
      this.init();
      if (!this.ctx) return;
      if (this.ctx.state === 'suspended') this.ctx.resume();

      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = type;
      osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
      gain.gain.setValueAtTime(0.12, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + duration);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start();
      osc.stop(this.ctx.currentTime + duration);
    } catch (e) {
      // Ignore audio failure
    }
  }

  click() {
    this.playBeep(800, 0.04, 'triangle');
  }

  success() {
    this.playBeep(587.33, 0.08); // D5
    setTimeout(() => this.playBeep(880, 0.15), 80); // A5
  }

  warning() {
    this.playBeep(330, 0.12, 'sawtooth');
    setTimeout(() => this.playBeep(290, 0.15, 'sawtooth'), 100);
  }

  scan() {
    this.playBeep(1200, 0.06);
    setTimeout(() => this.playBeep(1800, 0.09), 60);
  }
}

const sounds = new SoundFX();

// API Helper
const api = {
  async request(endpoint, method = 'GET', body = null) {
    const headers = {
      'Content-Type': 'application/json',
      'Accept': 'application/json'
    };

    const token = localStorage.getItem('stocksense_token');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const options = {
      method,
      headers
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, options);
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        const errorMsg = data.error || `HTTP error ${response.status}`;
        sounds.warning();
        throw new Error(errorMsg);
      }

      return data;
    } catch (err) {
      console.error(`API Error [${method} ${endpoint}]:`, err);
      throw err;
    }
  },

  get(endpoint) {
    return this.request(endpoint, 'GET');
  },

  post(endpoint, body) {
    return this.request(endpoint, 'POST', body);
  },

  put(endpoint, body) {
    return this.request(endpoint, 'PUT', body);
  },

  delete(endpoint) {
    return this.request(endpoint, 'DELETE');
  }
};

// Toast notification helper
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  let iconName = 'info';
  if (type === 'success') {
    iconName = 'check-circle';
    sounds.success();
  } else if (type === 'error') {
    iconName = 'alert-triangle';
    sounds.warning();
  } else if (type === 'warning') {
    iconName = 'alert-circle';
    sounds.warning();
  }

  toast.innerHTML = `
    <i data-lucide="${iconName}"></i>
    <div style="flex:1;">${message}</div>
    <button onclick="this.parentElement.remove()" style="background:none;border:none;color:inherit;cursor:pointer;opacity:0.6;">&times;</button>
  `;

  container.appendChild(toast);
  if (window.lucide) lucide.createIcons();

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
