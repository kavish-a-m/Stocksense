/**
 * STOCKSENSE - Barcode & QR Code Integration Module
 */

const barcodeScanner = {
  activeStream: null,

  openScannerModal() {
    modals.open('modal-barcode-scanner');
    this.startCamera();
  },

  async startCamera() {
    const video = document.getElementById('camera-feed');
    const fallbackBox = document.getElementById('scanner-fallback-box');

    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      try {
        this.activeStream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment' }
        });
        if (video) {
          video.srcObject = this.activeStream;
          video.play();
          video.style.display = 'block';
          if (fallbackBox) fallbackBox.style.display = 'none';
        }
      } catch (err) {
        console.warn('Camera access denied or unavailable, showing simulated scanner:', err);
        this.showSimulatedFallback();
      }
    } else {
      this.showSimulatedFallback();
    }
  },

  showSimulatedFallback() {
    const video = document.getElementById('camera-feed');
    const fallbackBox = document.getElementById('scanner-fallback-box');
    if (video) video.style.display = 'none';
    if (fallbackBox) fallbackBox.style.display = 'block';
  },

  stopCamera() {
    if (this.activeStream) {
      this.activeStream.getTracks().forEach(track => track.stop());
      this.activeStream = null;
    }
  },

  handleScan(code) {
    if (!code) return;
    sounds.scan();
    this.stopCamera();
    modals.close('modal-barcode-scanner');

    // Search for product with this barcode or SKU
    const match = products.list.find(p => p.barcode === code || p.sku.toUpperCase() === code.toUpperCase() || p.id.toString() === code);

    if (match) {
      showToast(`Scanned: ${match.name} (${match.sku})`, 'success');
      products.openDetailModal(match.id);
    } else {
      showToast(`Barcode '${code}' not found in product database.`, 'warning');
    }
  },

  simulateQuickScan() {
    const input = document.getElementById('simulated-barcode-input');
    if (!input || !input.value) {
      // Pick a random product from the list for effortless demo testing
      if (products.list.length) {
        const randomP = products.list[Math.floor(Math.random() * products.list.length)];
        this.handleScan(randomP.barcode);
      }
    } else {
      this.handleScan(input.value.trim());
    }
  }
};
