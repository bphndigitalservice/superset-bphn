# Polished Dashboard Card Styles Design Spec

**Date:** 2026-06-16  
**Status:** Approved  
**File Modified:** `superset/styles/custom-dashboard.css`

## Goal

Refine the dashboard styling in this Apache Superset project to make cards look more polished, premium, and visually engaging. 

This design implements **Option C (Elegant Brand-Glow)** combined with a custom deep navy/slate background to make the glassmorphism pop. It uses BPHN brand colors (`#1A2B56` primary and `#FFC107` gold secondary) as key visual anchors and incorporates smooth transitions and gradient KPI texts.

## Proposed Changes

### `superset/styles/custom-dashboard.css`

Introduce CSS variables, modern glassmorphic overrides, and BPHN branding details as follows:

1. **Brand Theme & Variables**:
   - Define `--bphn-primary` (`#1A2B56`), `--bphn-secondary` (`#FFC107`), and support variables.
   - For light mode: dashboard background `#f5f7fb`, transparent card background `rgba(255, 255, 255, 0.72)` with blur, and a gradient text representation for KPIs (`--kpi-gradient` from `#1A2B56` to `#3b82f6`).
   - For dark mode: dashboard background `#0b0f19` (dark navy slate), transparent card background `rgba(21, 32, 54, 0.65)` with blur, and a gradient text representation for KPIs (`--kpi-gradient` from gold `#FFC107` to orange `#ff8c00`).
2. **Card Structure & Interactivity**:
   - Set border-radius to `20px`.
   - Apply `backdrop-filter: blur(24px) saturate(120%)`.
   - Set double border boundaries using `border` and `outline` offset for a real glass sheen.
   - Refine translation hover effect from `-3px` to `-4px` using a smooth cubic-bezier easing.
3. **Card Header**:
   - Style headers with a very faint bottom divider.
   - Add a decorative gold dot accent next to the title using a `::before` pseudo-element.
4. **KPIs & Trends**:
   - Apply clipping and text-fill-color properties to `.big_number_total` and `.big_number` to enable gradient colors.
   - Polish trend subheaders with heavier font weight and soft sizing.

## Verification Plan

### Manual Verification
1. Open the dashboard in Apache Superset (both light and dark modes).
2. Verify that cards have rounded corners of `20px` with a subtle backdrop blur effect.
3. Check that titles are preceded by a small gold dot accent.
4. Verify that the large KPI numbers have a gradient (Navy/Blue in light mode, Gold/Orange in dark mode).
5. Hover over the cards and ensure they translate upwards smoothly with a soft shadow growth.
