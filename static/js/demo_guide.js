/**
 * STOCKSENSE - Interactive Hackathon Demo Flow Walkthrough (Section 42 Demo Guide)
 */

const demoGuide = {
  currentStep: 1,

  steps: [
    {
      step: 1,
      title: "Step 1: Role-Based Authentication",
      desc: "Logged in as Inventory Manager with full operational control.",
      action: async () => {
        const mgr = auth.usersList.find(u => u.role === 'Inventory Manager');
        if (mgr) auth.quickSwitchUser(mgr.id);
        router.navigate('dashboard');
      }
    },
    {
      step: 2,
      title: "Step 2: Real-time Dashboard Snapshot",
      desc: "Inspect live KPIs: Total Products, Stock Units, Low Stock items, Pending Operations & Valuations.",
      action: async () => {
        router.navigate('dashboard');
        dashboard.loadData();
      }
    },
    {
      step: 3,
      title: "Step 3: Inbound Receipt (ABC Metals - 100 Steel Rods)",
      desc: "Open Receipt Wizard, prefill 100 units of Steel Rods from ABC Metals, and validate to increase stock.",
      action: async () => {
        router.navigate('receipts');
        receipts.openCreateModal();
        document.getElementById('rec-form-supplier').value = 'ABC Metals Corp';
        
        // Find Steel Rods product ID
        const steelRod = products.list.find(p => p.sku.includes('STL') || p.name.includes('Steel'));
        const pId = steelRod ? steelRod.id : (products.list[0] ? products.list[0].id : 1);
        
        const linesContainer = document.getElementById('receipt-items-lines');
        linesContainer.innerHTML = '';
        receipts.addItemLine(pId, 100);
      }
    },
    {
      step: 4,
      title: "Step 4: Product Detail & Location Verification",
      desc: "Inspect Steel Rods stock on hand across multi-locations.",
      action: async () => {
        const steelRod = products.list.find(p => p.sku.includes('STL') || p.name.includes('Steel'));
        const pId = steelRod ? steelRod.id : (products.list[0] ? products.list[0].id : 1);
        router.navigate('products');
        products.openDetailModal(pId);
      }
    },
    {
      step: 5,
      title: "Step 5: Internal Transfer (Main Store → Production Floor)",
      desc: "Move 30 Steel Rods between locations. Company balance remains unchanged!",
      action: async () => {
        router.navigate('transfers');
        transfers.openCreateModal();
        const steelRod = products.list.find(p => p.sku.includes('STL') || p.name.includes('Steel'));
        const pId = steelRod ? steelRod.id : (products.list[0] ? products.list[0].id : 1);

        const linesContainer = document.getElementById('transfer-items-lines');
        linesContainer.innerHTML = '';
        transfers.addItemLine(pId, 30);
      }
    },
    {
      step: 6,
      title: "Step 6: Customer Delivery Order (Ship 20 Units)",
      desc: "Create outbound delivery for 20 units. Verify stock availability, reserve, pick, pack, and ship.",
      action: async () => {
        router.navigate('deliveries');
        deliveries.openCreateModal();
        document.getElementById('del-form-customer').value = 'LPU Mechanical Labs';
        
        const steelRod = products.list.find(p => p.sku.includes('STL') || p.name.includes('Steel'));
        const pId = steelRod ? steelRod.id : (products.list[0] ? products.list[0].id : 1);

        const linesContainer = document.getElementById('delivery-items-lines');
        linesContainer.innerHTML = '';
        deliveries.addItemLine(pId, 20);
      }
    },
    {
      step: 7,
      title: "Step 7: Physical Stock Count & Adjustment",
      desc: "Simulate physical inventory recount: System 10 vs Physical 7 (-3 discrepancy due to Damaged items).",
      action: async () => {
        router.navigate('adjustments');
        const steelRod = products.list.find(p => p.sku.includes('STL') || p.name.includes('Steel'));
        adjustments.openCreateModal(steelRod ? steelRod.id : 1);
        document.getElementById('adj-form-reason').value = 'Damaged';
        document.getElementById('adj-form-notes').value = 'Crane offloading dent damage';
        setTimeout(() => {
          const sys = parseFloat(document.getElementById('adj-form-system-qty').value) || 10;
          document.getElementById('adj-form-counted-qty').value = Math.max(0, sys - 3);
          adjustments.recalculateDiff();
        }, 300);
      }
    },
    {
      step: 8,
      title: "Step 8: Immutable Stock Ledger Audit",
      desc: "Review the permanent audit ledger proving +100 Receipt, Transfer 30, -20 Delivery, and -3 Adjustment.",
      action: async () => {
        router.navigate('ledger');
      }
    },
    {
      step: 9,
      title: "Step 9: Security Audit Trail",
      desc: "Inspect the complete digital audit log verifying user identities, timestamps, and state diffs.",
      action: async () => {
        router.navigate('audit');
      }
    },
    {
      step: 10,
      title: "Step 10: Final Re-calculated Dashboard",
      desc: "Witness updated real-time KPI metrics, charts, and smart reorder suggestions.",
      action: async () => {
        router.navigate('dashboard');
        dashboard.loadData();
        showToast('🎉 Complete Hackathon End-to-End Demonstration Successfully Concluded!', 'success');
      }
    }
  ],

  async executeStep(stepNumber) {
    this.currentStep = stepNumber;
    const target = this.steps.find(s => s.step === stepNumber);
    if (!target) return;

    sounds.click();
    this.renderBanner();
    await target.action();
  },

  nextStep() {
    if (this.currentStep < this.steps.length) {
      this.executeStep(this.currentStep + 1);
    }
  },

  prevStep() {
    if (this.currentStep > 1) {
      this.executeStep(this.currentStep - 1);
    }
  },

  renderBanner() {
    const cur = this.steps.find(s => s.step === this.currentStep) || this.steps[0];
    const bannerEl = document.getElementById('demo-guide-step-title');
    const descEl = document.getElementById('demo-guide-step-desc');
    const badgeEl = document.getElementById('demo-guide-step-badge');

    if (bannerEl) bannerEl.textContent = cur.title;
    if (descEl) descEl.textContent = cur.desc;
    if (badgeEl) badgeEl.textContent = `Step ${cur.step} of 10`;
  },

  async resetDemoData() {
    try {
      const res = await api.post('/api/demo/reset');
      showToast(res.message, 'success');
      this.currentStep = 1;
      await Promise.all([
        products.init(),
        receipts.init(),
        deliveries.init(),
        transfers.init(),
        adjustments.init(),
        ledger.init(),
        dashboard.loadData()
      ]);
      router.navigate('dashboard');
    } catch (err) {
      showToast(err.message, 'error');
    }
  }
};
