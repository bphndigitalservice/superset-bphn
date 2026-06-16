# Polished Dashboard Card Styles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine the dashboard stylesheet to make Superset cards look premium, glassmorphic, and branded with BPHN colors (navy primary and gold secondary).

**Architecture:** We will modify `superset/styles/custom-dashboard.css` in four incremental phases: variables declaration, card wrapper updates, header polishing, and KPI styling.

**Tech Stack:** CSS (Vanilla CSS variables, selectors, and nested attributes compatible with Superset's CSS insertion).

---

### Task 1: Update Design Variables

**Files:**
- Modify: `superset/styles/custom-dashboard.css:1-49`

- [ ] **Step 1: Declare BPHN theme and glass variables in `:root` and dark mode override**
  Replace lines 1 to 49 with the following CSS variables.
  
  ```css
  /* =========================================
     THEME VARIABLES (Light & Dark Mode)
     ========================================= */
  :root {
    /* BPHN Brand Palette */
    --bphn-primary: #1A2B56;
    --bphn-secondary: #FFC107;
    --bphn-blue-accent: #3b82f6;

    /* Light Mode Defaults */
    --bg-dashboard: #f5f7fb;
    --bg-navbar: rgba(255, 255, 255, 0.78);
    --bg-card: rgba(255, 255, 255, 0.72);
    --bg-section: rgba(255, 255, 255, 0.8);

    --text-main: #1d1d1f;
    --text-muted: #6e6e73;

    --border-light: rgba(26, 43, 86, 0.04);
    --border-card: rgba(255, 255, 255, 0.5);
    --border-card-outer: rgba(26, 43, 86, 0.08);

    --shadow-nav: 0 8px 28px rgba(26, 43, 86, 0.03);
    --shadow-card: 0 10px 30px rgba(26, 43, 86, 0.04), 0 1px 3px rgba(26, 43, 86, 0.02);
    --shadow-card-hover: 0 20px 45px rgba(26, 43, 86, 0.08), 0 1px 5px rgba(26, 43, 86, 0.03);

    --inset-card: inset 0 1px 1px rgba(255, 255, 255, 0.8);
    --inset-card-hover: inset 0 1px 1px rgba(255, 255, 255, 0.95);

    --kpi-gradient: linear-gradient(135deg, var(--bphn-primary) 0%, var(--bphn-blue-accent) 100%);
  }

  @media (prefers-color-scheme: dark) {
    :root {
      /* Dark Mode Overrides (Navy/Slate Glass) */
      --bg-dashboard: #0b0f19;
      --bg-navbar: rgba(15, 23, 42, 0.78);
      --bg-card: rgba(21, 32, 54, 0.65);
      --bg-section: rgba(21, 32, 54, 0.7);

      --text-main: #f3f4f6;
      --text-muted: #9ca3af;

      --border-light: rgba(255, 255, 255, 0.05);
      --border-card: rgba(255, 255, 255, 0.06);
      --border-card-outer: rgba(0, 0, 0, 0.25);

      --shadow-nav: 0 8px 28px rgba(0, 0, 0, 0.4);
      --shadow-card: 0 12px 32px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.05);
      --shadow-card-hover: 0 24px 50px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1);

      --inset-card: inset 0 1px 1px rgba(255, 255, 255, 0.05);
      --inset-card-hover: inset 0 1px 1px rgba(255, 255, 255, 0.12);

      --kpi-gradient: linear-gradient(135deg, var(--bphn-secondary) 0%, #ff8c00 100%);
    }
  }
  ```

- [ ] **Step 2: Verify code structure**
  Open the file and check that variables are correctly defined and formatted.

- [ ] **Step 3: Commit**
  ```bash
  git add superset/styles/custom-dashboard.css
  git commit -m "style: introduce bphn branding & glassmorphic css variables"
  ```

---

### Task 2: Polish Card Wrappers & Transitions

**Files:**
- Modify: `superset/styles/custom-dashboard.css:70-89`

- [ ] **Step 1: Set glass background, borders, radius, and cubic-bezier transition curves**
  Replace lines 70 to 89 with the following CSS blocks.
  
  ```css
  /* Semua Card Chart */
  .dashboard-component-chart-holder,
  .dashboard-chart-id-206,
  .dashboard-chart-id-197 {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-card-outer) !important;
    outline: 1px solid var(--border-card) !important;
    outline-offset: -1px;
    border-radius: 20px !important;
    box-shadow: var(--shadow-card), var(--inset-card) !important;
    overflow: hidden !important;
    backdrop-filter: blur(24px) saturate(120%);
    -webkit-backdrop-filter: blur(24px) saturate(120%);
    transition: transform 0.35s cubic-bezier(0.16, 1, 0.3, 1), 
                box-shadow 0.35s cubic-bezier(0.16, 1, 0.3, 1), 
                border-color 0.35s cubic-bezier(0.16, 1, 0.3, 1) !important;
  }

  /* Hover Card */
  .dashboard-component-chart-holder:hover,
  .dashboard-chart-id-206:hover,
  .dashboard-chart-id-197:hover {
    transform: translateY(-4px);
    box-shadow: var(--shadow-card-hover), var(--inset-card-hover) !important;
    border-color: rgba(26, 43, 86, 0.15) !important;
  }
  ```

- [ ] **Step 2: Commit**
  ```bash
  git commit -am "style: update card wrapper structure, double-border, blur and cubic easing"
  ```

---

### Task 3: Refine Card Headers & Gold Accent Dot

**Files:**
- Modify: `superset/styles/custom-dashboard.css:90-105`

- [ ] **Step 1: Format card header titles with a preceding gold accent dot**
  Replace lines 90 to 105 with the following card header styles.
  
  ```css
  /* Header Chart */
  .chart-header {
    background: transparent !important;
    border-bottom: 1px solid var(--border-light) !important;
    padding: 16px 20px !important;
  }

  .chart-header .header,
  .header-title,
  .editable-title {
    font-size: 14px !important;
    font-weight: 700 !important;
    color: var(--text-main) !important;
    letter-spacing: -0.01em;
    display: flex !important;
    align-items: center !important;
  }

  /* Gold Dot Accent */
  .chart-header .header::before,
  .header-title::before,
  .editable-title::before {
    content: '';
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--bphn-secondary) !important;
    margin-right: 8px;
    flex-shrink: 0;
  }
  ```

- [ ] **Step 2: Commit**
  ```bash
  git commit -am "style: add decorative gold brand dot to card headers"
  ```

---

### Task 4: Enhance KPIs, Gradients & Subheaders

**Files:**
- Modify: `superset/styles/custom-dashboard.css:106-143`

- [ ] **Step 1: Set text background gradients on big numbers and style subtitles**
  Replace lines 106 to 143 with the following block.
  
  ```css
  /* Isi Chart */
  .slice_container {
    padding: 16px 20px 20px !important;
  }

  /* Angka KPI */
  .big_number_total,
  .big_number,
  .header-line {
    font-weight: 900 !important;
    background: var(--kpi-gradient) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    letter-spacing: -0.05em !important;
    line-height: 1.1 !important;
  }

  /* Subtitle */
  .subheader-line,
  div[class*="subheader"] {
    color: var(--text-muted) !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    margin-top: 4px !important;
    display: inline-block !important;
  }

  /* Section Title */
  .dashboard-component-header {
    background: var(--bg-section) !important;
    border: 1px solid var(--border-light) !important;
    border-radius: 20px !important;
    box-shadow: var(--shadow-section) !important;
    padding: 16px 22px !important;
    transition: all 0.25s ease !important;
  }

  .dashboard-component-header h1,
  .dashboard-component-header h2,
  .dashboard-component-header h3 {
    color: var(--text-main) !important;
    font-weight: 800 !important;
    letter-spacing: -0.04em;
  }
  ```

- [ ] **Step 2: Commit**
  ```bash
  git commit -am "style: set kpi text background gradient clipping and style subheaders"
  ```
