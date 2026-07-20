# Wind History Axis and Hover Symbol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make wind monthly history show sparse date-only labels and hide line symbols until hover.

**Architecture:** Keep the existing ECharts category axis and extract its label formatting and visibility rules into testable pure helpers in `windHistory.js`. The Vue view consumes those helpers and disables persistent symbols without changing tooltip data or other chart modes.

**Tech Stack:** Vue 3, Apache ECharts 5, Node.js built-in test runner

## Global Constraints

- Monthly labels are exactly `1日、5日、9日、13日、17日、21日、25日、29日` when those dates exist.
- Calendar year labels remain month based.
- Recent 24-hour labels and tooltip wind direction remain unchanged.
- Data symbols are hidden at rest and visible through ECharts emphasis on hover.
- Do not modify unrelated dirty worktree files.

---

### Task 1: Testable Wind Axis Rules

**Files:**
- Modify: `dam-frontend/src/utils/windHistory.js`
- Test: `dam-frontend/src/utils/windHistory.test.mjs`

**Interfaces:**
- Consumes: ISO calendar date strings (`YYYY-MM-DD`), monthly-mode boolean, chart width, first-month index.
- Produces: `formatWindCalendarAxisLabel(value, monthly): string` and `shouldShowWindCalendarLabel(index, value, monthly, chartWidth, firstMonthIndex): boolean`.

- [ ] **Step 1: Write the failing tests**

Add tests asserting that monthly formatting returns `1日` and `29日`, monthly visibility accepts days 1/5/29 but rejects 2/6/30, and annual formatting/visibility retains the month-first behavior.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `node --test src/utils/windHistory.test.mjs`

Expected: FAIL because the two helper exports do not exist.

- [ ] **Step 3: Implement the minimal helpers**

Implement date parsing once, return `${day}日` for monthly labels and `${month}月` for annual labels, use `(day - 1) % 4 === 0` for monthly visibility, and retain the existing annual month-first/narrow-width rule.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `node --test src/utils/windHistory.test.mjs`

Expected: all wind-history tests pass.

### Task 2: Wire Axis Rules and Hover-Only Symbols

**Files:**
- Modify: `dam-frontend/src/views/Monitor/SensorWind.vue`
- Test: `dam-frontend/src/utils/windHistory.test.mjs`

**Interfaces:**
- Consumes: `formatWindCalendarAxisLabel` and `shouldShowWindCalendarLabel` from Task 1.
- Produces: ECharts axis labels with no wind direction and a line series with `showSymbol: false`.

- [ ] **Step 1: Write the failing source-contract test**

Read `SensorWind.vue` in the Node test and assert that the wind-speed series contains `showSymbol: false`, with no observed-max conditional.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `node --test src/utils/windHistory.test.mjs`

Expected: FAIL because the view still uses `showSymbol: !recent && observedMax <= 1`.

- [ ] **Step 3: Make the minimal Vue changes**

Remove the direction lookup from axis formatting, call the two helpers for labels and interval selection, reduce the monthly bottom grid padding to the single-line layout, and set `showSymbol: false`.

- [ ] **Step 4: Run focused and full verification**

Run: `npm test`

Expected: all Node tests pass.

Run: `npm run build`

Expected: Vite exits with code 0.
