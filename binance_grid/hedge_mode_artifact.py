from __future__ import annotations

from pathlib import Path


def render_hedge_mode_grid_demo_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hedge Mode Futures Grid Bot</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #071017;
      --bg-deep: #04090d;
      --panel: rgba(10, 20, 30, 0.86);
      --panel-strong: rgba(16, 28, 41, 0.94);
      --line: rgba(120, 147, 173, 0.16);
      --line-strong: rgba(120, 147, 173, 0.34);
      --text: #e3eef8;
      --muted: #86a0b8;
      --accent: #69d4ff;
      --accent-soft: rgba(105, 212, 255, 0.18);
      --long: #41dc91;
      --short: #ff916b;
      --up-flash: #4be39b;
      --down-flash: #ff7f7f;
      --good: #72f1af;
      --bad: #ff8d8d;
      --shadow: 0 22px 70px rgba(0, 0, 0, 0.34);
      --radius: 24px;
      font-family: "IBM Plex Mono", "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      font-variant-numeric: tabular-nums;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at 15% 18%, rgba(105, 212, 255, 0.18), transparent 36%),
        radial-gradient(circle at 82% 12%, rgba(255, 145, 107, 0.18), transparent 30%),
        linear-gradient(180deg, #08131b 0%, #05090e 100%);
      color: var(--text);
    }

    .shell {
      max-width: 1520px;
      margin: 0 auto;
      padding: 28px;
      display: grid;
      gap: 22px;
    }

    .hero {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 20px;
      padding: 22px 24px;
      border: 1px solid rgba(105, 212, 255, 0.14);
      border-radius: var(--radius);
      background: linear-gradient(180deg, rgba(14, 25, 37, 0.92), rgba(8, 15, 22, 0.88));
      box-shadow: var(--shadow);
    }

    .eyebrow {
      margin: 0 0 10px;
      color: var(--accent);
      letter-spacing: 0.18em;
      font-size: 0.72rem;
      text-transform: uppercase;
    }

    h1 {
      margin: 0;
      font-size: clamp(1.7rem, 2.6vw, 2.8rem);
      line-height: 1.08;
    }

    .lede {
      margin: 12px 0 0;
      max-width: 860px;
      color: var(--muted);
      line-height: 1.6;
      font-size: 0.96rem;
    }

    .hero-meta {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 10px;
    }

    .hero-chip,
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 9px 12px;
      border-radius: 999px;
      border: 1px solid rgba(255, 255, 255, 0.09);
      background: rgba(255, 255, 255, 0.03);
      color: var(--text);
      font-size: 0.76rem;
      white-space: nowrap;
    }

    .dashboard {
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(330px, 0.82fr);
      gap: 22px;
      align-items: stretch;
    }

    .panel {
      border-radius: var(--radius);
      background: linear-gradient(180deg, rgba(10, 18, 26, 0.92), rgba(9, 15, 22, 0.86));
      border: 1px solid rgba(130, 154, 180, 0.12);
      box-shadow: var(--shadow);
      overflow: hidden;
    }

    .chart-panel {
      display: grid;
      gap: 16px;
      padding: 18px;
    }

    .side-panel {
      display: grid;
      gap: 22px;
      min-height: 0;
    }

    .panel-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 16px;
      padding: 2px 2px 0;
    }

    .panel-title {
      margin: 0;
      font-size: 0.95rem;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--accent);
    }

    .panel-copy {
      margin: 8px 0 0;
      color: var(--muted);
      line-height: 1.55;
      font-size: 0.84rem;
    }

    .panel-badges {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px;
    }

    .chart-frame {
      border-radius: 22px;
      border: 1px solid rgba(105, 212, 255, 0.1);
      background:
        linear-gradient(180deg, rgba(14, 23, 33, 0.96), rgba(7, 12, 18, 0.96));
      overflow: hidden;
    }

    svg {
      display: block;
      width: 100%;
      height: auto;
    }

    .chart-note {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      color: var(--muted);
      font-size: 0.77rem;
      line-height: 1.5;
      padding: 0 2px 2px;
    }

    .stats-panel,
    .log-panel {
      padding: 18px;
      display: grid;
      gap: 16px;
      min-height: 0;
    }

    .stats-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }

    .stat-card {
      position: relative;
      padding: 16px;
      border-radius: 18px;
      border: 1px solid rgba(136, 160, 186, 0.12);
      background: linear-gradient(180deg, rgba(14, 24, 35, 0.98), rgba(10, 18, 26, 0.96));
      overflow: hidden;
    }

    .stat-card::after {
      content: "";
      position: absolute;
      inset: auto -10% -40% 35%;
      height: 70px;
      background: radial-gradient(circle, rgba(255, 255, 255, 0.09), transparent 65%);
      pointer-events: none;
    }

    .stat-card.long-card {
      border-color: rgba(65, 220, 145, 0.24);
    }

    .stat-card.short-card {
      border-color: rgba(255, 145, 107, 0.24);
    }

    .stat-card.price-card {
      background: linear-gradient(180deg, rgba(13, 30, 42, 0.98), rgba(10, 21, 30, 0.96));
      border-color: rgba(105, 212, 255, 0.22);
    }

    .stat-label {
      display: block;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.12em;
      font-size: 0.68rem;
    }

    .stat-value {
      display: block;
      margin-top: 12px;
      font-size: clamp(1.25rem, 2vw, 1.95rem);
      line-height: 1;
      color: var(--text);
    }

    .stat-value.positive {
      color: var(--good);
    }

    .stat-value.negative {
      color: var(--bad);
    }

    .stat-meta {
      display: block;
      margin-top: 10px;
      color: var(--muted);
      font-size: 0.76rem;
      line-height: 1.45;
    }

    .trade-log {
      min-height: 220px;
      max-height: 562px;
      overflow: auto;
      display: grid;
      gap: 10px;
      padding-right: 4px;
    }

    .trade-log::-webkit-scrollbar {
      width: 10px;
    }

    .trade-log::-webkit-scrollbar-thumb {
      background: rgba(128, 152, 176, 0.2);
      border-radius: 999px;
    }

    .log-entry,
    .log-empty {
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid rgba(122, 146, 171, 0.1);
      background: rgba(255, 255, 255, 0.025);
      line-height: 1.55;
      font-size: 0.82rem;
    }

    .log-entry.up {
      border-left: 3px solid rgba(75, 227, 155, 0.95);
    }

    .log-entry.down {
      border-left: 3px solid rgba(255, 127, 127, 0.95);
    }

    .log-empty {
      color: var(--muted);
    }

    .controls-panel {
      padding: 18px;
      display: grid;
      gap: 18px;
    }

    .controls-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }

    .button-strip {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .control-button {
      appearance: none;
      border: 1px solid rgba(125, 149, 174, 0.18);
      background: rgba(255, 255, 255, 0.04);
      color: var(--text);
      padding: 11px 16px;
      border-radius: 12px;
      font: inherit;
      cursor: pointer;
      transition: transform 120ms ease, border-color 120ms ease, background 120ms ease;
    }

    .control-button:hover:not(:disabled) {
      transform: translateY(-1px);
      border-color: rgba(105, 212, 255, 0.34);
      background: rgba(105, 212, 255, 0.08);
    }

    .control-button:disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }

    .control-button.primary {
      border-color: rgba(105, 212, 255, 0.35);
      background: linear-gradient(180deg, rgba(28, 73, 96, 0.86), rgba(16, 45, 61, 0.94));
    }

    .mode-group {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 12px;
    }

    .mode-label {
      color: var(--muted);
      font-size: 0.76rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      white-space: nowrap;
    }

    .mode-toggle {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .mode-button {
      min-width: 126px;
    }

    .mode-button.active.neutral,
    .mode-badge.neutral {
      border-color: rgba(105, 212, 255, 0.34);
      background: rgba(105, 212, 255, 0.1);
      color: var(--accent);
    }

    .mode-button.active.long,
    .mode-badge.long {
      border-color: rgba(65, 220, 145, 0.34);
      background: rgba(65, 220, 145, 0.1);
      color: var(--long);
    }

    .mode-button.active.short,
    .mode-badge.short {
      border-color: rgba(255, 145, 107, 0.34);
      background: rgba(255, 145, 107, 0.1);
      color: var(--short);
    }

    .mode-button.active.trailing,
    .mode-badge.trailing {
      border-color: rgba(255, 208, 102, 0.34);
      background: rgba(255, 208, 102, 0.1);
      color: #ffd066;
    }

    .speed-group,
    .field {
      display: grid;
      gap: 8px;
      color: var(--muted);
      font-size: 0.76rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }

    .speed-group {
      min-width: min(360px, 100%);
      align-items: center;
      grid-template-columns: auto minmax(150px, 1fr) auto;
      column-gap: 14px;
    }

    .speed-group span,
    .field span {
      white-space: nowrap;
    }

    .inputs-grid {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 14px;
    }

    input[type="number"],
    input[type="range"] {
      width: 100%;
    }

    input[type="number"] {
      border: 1px solid rgba(125, 149, 174, 0.18);
      background: rgba(255, 255, 255, 0.04);
      color: var(--text);
      border-radius: 12px;
      padding: 11px 12px;
      font: inherit;
      min-width: 0;
    }

    input[type="number"]:focus,
    input[type="range"]:focus {
      outline: none;
      border-color: rgba(105, 212, 255, 0.36);
      box-shadow: 0 0 0 3px rgba(105, 212, 255, 0.1);
    }

    input[type="range"] {
      accent-color: var(--accent);
    }

    output {
      color: var(--text);
      font-size: 0.82rem;
    }

    .controls-footnote {
      color: var(--muted);
      font-size: 0.8rem;
      line-height: 1.55;
    }

    .plot-shell {
      fill: rgba(6, 10, 15, 0.48);
    }

    .plot-surface {
      fill: rgba(8, 14, 21, 0.86);
      stroke: rgba(105, 212, 255, 0.08);
      stroke-width: 1;
    }

    .grid-line {
      stroke: var(--line);
      stroke-width: 1;
    }

    .grid-line.center {
      stroke: rgba(105, 212, 255, 0.34);
      stroke-width: 1.4;
    }

    .grid-line.flash-up {
      stroke: var(--up-flash);
      stroke-width: 2.2;
    }

    .grid-line.flash-down {
      stroke: var(--down-flash);
      stroke-width: 2.2;
    }

    .axis-label {
      fill: var(--muted);
      font-size: 12px;
    }

    .axis-label.center {
      fill: var(--accent);
    }

    .axis-time.current {
      fill: var(--text);
    }

    .price-path {
      fill: none;
      stroke: var(--accent);
      stroke-width: 2.75;
      stroke-linecap: round;
      stroke-linejoin: round;
      filter: drop-shadow(0 0 18px rgba(105, 212, 255, 0.22));
    }

    .area-path {
      fill: url(#priceAreaGradient);
      opacity: 0.9;
    }

    .price-guide {
      stroke: rgba(105, 212, 255, 0.24);
      stroke-width: 1;
      stroke-dasharray: 4 5;
    }

    .price-cursor {
      pointer-events: none;
    }

    .price-halo {
      fill: rgba(105, 212, 255, 0.16);
    }

    .price-dot {
      fill: #d8f8ff;
      stroke: var(--accent);
      stroke-width: 1.6;
    }

    .price-tag {
      fill: var(--text);
      font-size: 12px;
      font-weight: 600;
      filter: drop-shadow(0 0 14px rgba(0, 0, 0, 0.48));
    }

    .position-tether {
      stroke-width: 1.2;
      opacity: 0.34;
    }

    .position-tether.long {
      stroke: rgba(65, 220, 145, 0.85);
    }

    .position-tether.short {
      stroke: rgba(255, 145, 107, 0.85);
    }

    .position-marker.long {
      fill: rgba(65, 220, 145, 0.95);
      stroke: rgba(214, 255, 236, 0.9);
      stroke-width: 1;
    }

    .position-marker.short {
      fill: rgba(255, 145, 107, 0.95);
      stroke: rgba(255, 232, 223, 0.9);
      stroke-width: 1;
    }

    .flash-badge {
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.02em;
      filter: drop-shadow(0 0 10px rgba(0, 0, 0, 0.4));
    }

    .flash-badge.up {
      fill: var(--up-flash);
    }

    .flash-badge.down {
      fill: var(--down-flash);
    }

    @media (max-width: 1120px) {
      .dashboard {
        grid-template-columns: 1fr;
      }

      .inputs-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }

    @media (max-width: 760px) {
      .shell {
        padding: 16px;
      }

      .hero,
      .controls-row,
      .panel-header,
      .chart-note {
        flex-direction: column;
      }

      .hero-meta,
      .panel-badges {
        justify-content: flex-start;
      }

      .stats-grid,
      .inputs-grid {
        grid-template-columns: 1fr;
      }

      .speed-group {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header class="hero">
      <div>
        <p class="eyebrow">Generated Artifact</p>
        <h1>Hedge Mode Futures Grid Bot</h1>
        <p class="lede">Synthetic oscillation drives a live hedge ladder so you can step through every upper-grid short fill, every lower-grid long fill, and every paired take-profit close in sequence.</p>
      </div>
      <div class="hero-meta">
        <span class="hero-chip">Vanilla JS</span>
        <span class="hero-chip">SVG Chart</span>
        <span class="hero-chip">Step Accurate</span>
      </div>
    </header>

    <main class="dashboard">
      <section class="panel chart-panel">
        <div class="panel-header">
          <div>
            <p class="panel-title">Synthetic Ladder</p>
            <p class="panel-copy">Short entries live above the center line, long entries live below it. Each crossing fills that side and looks for the nearest open opposite leg that has cleared the take-profit threshold.</p>
          </div>
          <div class="panel-badges">
            <span id="modeBadge" class="badge mode-badge neutral">Neutral mode</span>
            <span id="runStatus" class="badge">Paused</span>
            <span id="tickCounter" class="badge">Tick 000 / 000</span>
          </div>
        </div>

        <div class="chart-frame">
          <svg id="chart" viewBox="0 0 900 560" role="img" aria-label="Synthetic hedge mode grid chart">
            <defs>
              <linearGradient id="priceAreaGradient" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stop-color="rgba(105, 212, 255, 0.30)"></stop>
                <stop offset="100%" stop-color="rgba(105, 212, 255, 0.00)"></stop>
              </linearGradient>
            </defs>
            <rect class="plot-shell" x="0" y="0" width="900" height="560" rx="24"></rect>
            <rect class="plot-surface" x="60" y="24" width="760" height="492" rx="18"></rect>
            <g id="gridLayer"></g>
            <path id="areaPath" class="area-path"></path>
            <path id="pricePath" class="price-path"></path>
            <line id="priceGuide" class="price-guide" x1="0" y1="0" x2="0" y2="0"></line>
            <g id="positionLayer"></g>
            <g id="flashLayer"></g>
            <g id="axisLayer"></g>
            <g id="priceCursor" class="price-cursor">
              <circle id="priceHalo" class="price-halo" cx="0" cy="0" r="11"></circle>
              <circle id="priceDot" class="price-dot" cx="0" cy="0" r="5"></circle>
            </g>
            <text id="priceTag" class="price-tag" x="0" y="0"></text>
          </svg>
        </div>

        <div class="chart-note">
          <span>Green flashes mark upward crossings that fill a short ladder level. Red flashes mark downward crossings that fill a long ladder level.</span>
          <span>Reset applies the input values and regenerates the oscillation so you can compare different grid densities.</span>
        </div>
      </section>

      <aside class="side-panel">
        <section class="panel stats-panel">
          <div>
            <p class="panel-title">Live Book</p>
            <p class="panel-copy">Open positions stay pinned to their entry grid line and unrealized PnL updates against the moving price dot.</p>
          </div>
          <div class="stats-grid">
            <article class="stat-card long-card">
              <span class="stat-label">Open longs</span>
              <strong id="openLongCount" class="stat-value">0</strong>
              <span id="openLongMeta" class="stat-meta">flat</span>
            </article>
            <article class="stat-card short-card">
              <span class="stat-label">Open shorts</span>
              <strong id="openShortCount" class="stat-value">0</strong>
              <span id="openShortMeta" class="stat-meta">flat</span>
            </article>
            <article class="stat-card">
              <span class="stat-label">Realized PnL</span>
              <strong id="realizedPnl" class="stat-value">+$0.00</strong>
              <span class="stat-meta">Closed ladder pairs only</span>
            </article>
            <article class="stat-card">
              <span class="stat-label">Unrealized PnL</span>
              <strong id="unrealizedPnl" class="stat-value">+$0.00</strong>
              <span class="stat-meta">Mark-to-price on open inventory</span>
            </article>
            <article class="stat-card">
              <span class="stat-label">Total trades</span>
              <strong id="totalTrades" class="stat-value">0</strong>
              <span class="stat-meta">Entries plus take-profit exits</span>
            </article>
            <article class="stat-card price-card">
              <span class="stat-label">Current price</span>
              <strong id="currentPrice" class="stat-value">0.00</strong>
              <span id="currentPriceMeta" class="stat-meta">Awaiting first tick</span>
            </article>
          </div>
        </section>

        <section class="panel log-panel">
          <div>
            <p class="panel-title">Trade Log</p>
            <p class="panel-copy">Every event is timestamped from the synthetic session clock so you can inspect the exact order of fills and closes.</p>
          </div>
          <div id="tradeLog" class="trade-log"></div>
        </section>
      </aside>
    </main>

    <section class="panel controls-panel">
      <div class="controls-row">
        <div class="button-strip">
          <button id="playButton" class="control-button primary" type="button">Play</button>
          <button id="pauseButton" class="control-button" type="button">Pause</button>
          <button id="stepButton" class="control-button" type="button">Step Forward</button>
          <button id="resetButton" class="control-button" type="button">Reset</button>
        </div>

        <label class="speed-group" for="speedSlider">
          <span>Speed</span>
          <input id="speedSlider" type="range" min="1" max="24" step="1" value="6">
          <output id="speedValue" for="speedSlider">6 ticks/s</output>
        </label>
      </div>

      <div class="controls-row">
        <div class="mode-group" role="group" aria-label="Grid bias mode">
          <span class="mode-label">Mode</span>
          <div class="mode-toggle">
            <button id="modeLongButton" class="control-button mode-button long" type="button">Long mode</button>
            <button id="modeNeutralButton" class="control-button mode-button neutral" type="button">Neutral mode</button>
            <button id="modeShortButton" class="control-button mode-button short" type="button">Short mode</button>
            <button id="modeTrailingButton" class="control-button mode-button trailing" type="button">Trailing mode</button>
          </div>
        </div>
      </div>

      <div class="inputs-grid">
        <label class="field" for="centerPriceInput">
          <span>Center price</span>
          <input id="centerPriceInput" type="number" step="0.01" value="100.00">
        </label>
        <label class="field" for="gridSpacingInput">
          <span>Grid spacing (%)</span>
          <input id="gridSpacingInput" type="number" step="0.05" value="1.20">
        </label>
        <label class="field" for="gridCountInput">
          <span>Grid count</span>
          <input id="gridCountInput" type="number" step="1" value="6">
        </label>
        <label class="field" for="orderSizeInput">
          <span>Order size</span>
          <input id="orderSizeInput" type="number" step="0.1" value="1.0">
        </label>
        <label class="field" for="takeProfitInput">
          <span>Take-profit (%)</span>
          <input id="takeProfitInput" type="number" step="0.05" value="0.45">
        </label>
      </div>

      <div class="controls-footnote">Step Forward advances exactly one synthetic price tick. Switching between long, neutral, short, and trailing mode rebuilds the ladder with the same bias rules the repo uses: long adds more lower grids, short adds more upper grids, neutral keeps both sides symmetric, and trailing slides the whole ladder forward once price clears a full grid interval.</div>
    </section>
  </div>

  <script>
    (() => {
      const SVG_NS = 'http://www.w3.org/2000/svg';
      const chartBox = {
        left: 72,
        right: 744,
        top: 40,
        bottom: 482,
        labelRight: 812,
        width: 900,
        height: 560,
      };

      const ui = {
        modeBadge: document.getElementById('modeBadge'),
        runStatus: document.getElementById('runStatus'),
        tickCounter: document.getElementById('tickCounter'),
        openLongCount: document.getElementById('openLongCount'),
        openLongMeta: document.getElementById('openLongMeta'),
        openShortCount: document.getElementById('openShortCount'),
        openShortMeta: document.getElementById('openShortMeta'),
        realizedPnl: document.getElementById('realizedPnl'),
        unrealizedPnl: document.getElementById('unrealizedPnl'),
        totalTrades: document.getElementById('totalTrades'),
        currentPrice: document.getElementById('currentPrice'),
        currentPriceMeta: document.getElementById('currentPriceMeta'),
        tradeLog: document.getElementById('tradeLog'),
        playButton: document.getElementById('playButton'),
        pauseButton: document.getElementById('pauseButton'),
        stepButton: document.getElementById('stepButton'),
        resetButton: document.getElementById('resetButton'),
        modeLongButton: document.getElementById('modeLongButton'),
        modeNeutralButton: document.getElementById('modeNeutralButton'),
        modeShortButton: document.getElementById('modeShortButton'),
        modeTrailingButton: document.getElementById('modeTrailingButton'),
        speedSlider: document.getElementById('speedSlider'),
        speedValue: document.getElementById('speedValue'),
        centerPriceInput: document.getElementById('centerPriceInput'),
        gridSpacingInput: document.getElementById('gridSpacingInput'),
        gridCountInput: document.getElementById('gridCountInput'),
        orderSizeInput: document.getElementById('orderSizeInput'),
        takeProfitInput: document.getElementById('takeProfitInput'),
      };

      const chart = {
        gridLayer: document.getElementById('gridLayer'),
        axisLayer: document.getElementById('axisLayer'),
        areaPath: document.getElementById('areaPath'),
        pricePath: document.getElementById('pricePath'),
        priceGuide: document.getElementById('priceGuide'),
        positionLayer: document.getElementById('positionLayer'),
        flashLayer: document.getElementById('flashLayer'),
        priceCursor: document.getElementById('priceCursor'),
        priceTag: document.getElementById('priceTag'),
      };

      const defaults = {
        centerPrice: 100,
        gridSpacingPct: 1.2,
        gridCount: 6,
        orderSize: 1,
        takeProfitPct: 0.45,
        mode: 'neutral',
        speed: 6,
      };

      const modeProfiles = {
        long: {
          label: 'Long mode',
          centerShift: -1,
          buyLevelsDelta: 2,
          sellLevelsDelta: -2,
          buyMultiplier: 1.25,
          sellMultiplier: 0.85,
        },
        neutral: {
          label: 'Neutral mode',
          centerShift: 0,
          buyLevelsDelta: 0,
          sellLevelsDelta: 0,
          buyMultiplier: 1,
          sellMultiplier: 1,
        },
        short: {
          label: 'Short mode',
          centerShift: 1,
          buyLevelsDelta: -2,
          sellLevelsDelta: 2,
          buyMultiplier: 0.85,
          sellMultiplier: 1.25,
        },
        trailing: {
          label: 'Trailing mode',
          centerShift: 0,
          buyLevelsDelta: 0,
          sellLevelsDelta: 0,
          buyMultiplier: 1,
          sellMultiplier: 1,
          trailing: true,
        },
      };

      const state = {
        config: { ...defaults },
        selectedMode: defaults.mode,
        levels: null,
        series: [],
        yDomain: { min: 0, max: 1 },
        currentIndex: 0,
        partialProgress: 0,
        accumulator: 0,
        isPlaying: false,
        lastFrame: 0,
        longs: [],
        shorts: [],
        realizedPnl: 0,
        totalTrades: 0,
        tradeLog: [],
        flashes: [],
        gridFlash: Object.create(null),
        nextPositionId: 1,
      };

      function setDefaults() {
        ui.centerPriceInput.value = defaults.centerPrice.toFixed(2);
        ui.gridSpacingInput.value = defaults.gridSpacingPct.toFixed(2);
        ui.gridCountInput.value = String(defaults.gridCount);
        ui.orderSizeInput.value = defaults.orderSize.toFixed(1);
        ui.takeProfitInput.value = defaults.takeProfitPct.toFixed(2);
        ui.speedSlider.value = String(defaults.speed);
      }

      function clamp(value, min, max) {
        return Math.min(max, Math.max(min, value));
      }

      function lerp(start, end, amount) {
        return start + (end - start) * amount;
      }

      function round(value, places = 4) {
        const scale = 10 ** places;
        return Math.round(value * scale) / scale;
      }

      function formatPrice(value) {
        return Number(value).toLocaleString(undefined, {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        });
      }

      function formatSignedCurrency(value) {
        const prefix = value >= 0 ? '+' : '-';
        return `${prefix}$${formatPrice(Math.abs(value))}`;
      }

      function formatTime(tickIndex) {
        const totalMinutes = (10 * 60) + tickIndex;
        const hours = Math.floor(totalMinutes / 60) % 24;
        const minutes = totalMinutes % 60;
        return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
      }

      function createSvgElement(tag, attributes = {}) {
        const node = document.createElementNS(SVG_NS, tag);
        Object.entries(attributes).forEach(([key, value]) => {
          node.setAttribute(key, String(value));
        });
        return node;
      }

      function positiveNumber(rawValue, fallback, minimum) {
        const parsed = Number.parseFloat(rawValue);
        return Number.isFinite(parsed) && parsed >= minimum ? parsed : fallback;
      }

      function boundedInteger(rawValue, fallback, minimum, maximum) {
        const parsed = Number.parseInt(rawValue, 10);
        if (!Number.isFinite(parsed)) {
          return fallback;
        }
        return Math.max(minimum, Math.min(maximum, parsed));
      }

      function modeProfile(mode) {
        return modeProfiles[mode] ?? modeProfiles.neutral;
      }

      function readConfig() {
        const config = {
          centerPrice: positiveNumber(ui.centerPriceInput.value, defaults.centerPrice, 1),
          gridSpacingPct: positiveNumber(ui.gridSpacingInput.value, defaults.gridSpacingPct, 0.1),
          gridCount: boundedInteger(ui.gridCountInput.value, defaults.gridCount, 1, 12),
          orderSize: positiveNumber(ui.orderSizeInput.value, defaults.orderSize, 0.1),
          takeProfitPct: positiveNumber(ui.takeProfitInput.value, defaults.takeProfitPct, 0),
          mode: state.selectedMode,
          speed: boundedInteger(ui.speedSlider.value, defaults.speed, 1, 24),
        };

        ui.centerPriceInput.value = config.centerPrice.toFixed(2);
        ui.gridSpacingInput.value = config.gridSpacingPct.toFixed(2);
        ui.gridCountInput.value = String(config.gridCount);
        ui.orderSizeInput.value = config.orderSize.toFixed(1);
        ui.takeProfitInput.value = config.takeProfitPct.toFixed(2);
        ui.speedSlider.value = String(config.speed);
        ui.speedValue.value = `${config.speed} ticks/s`;
        ui.speedValue.textContent = `${config.speed} ticks/s`;
        return config;
      }

      function setMode(mode, shouldReset = true) {
        state.selectedMode = modeProfiles[mode] ? mode : defaults.mode;
        ui.modeLongButton.classList.toggle('active', state.selectedMode === 'long');
        ui.modeNeutralButton.classList.toggle('active', state.selectedMode === 'neutral');
        ui.modeShortButton.classList.toggle('active', state.selectedMode === 'short');
        ui.modeTrailingButton.classList.toggle('active', state.selectedMode === 'trailing');
        ui.modeBadge.textContent = modeProfile(state.selectedMode).label;
        ui.modeBadge.className = `badge mode-badge ${state.selectedMode}`;
        if (shouldReset) {
          resetSimulation();
        }
      }

      function levelKey(level) {
        return level.toFixed(4);
      }

      function buildLevels(config, centerOverride = null) {
        const profile = modeProfile(config.mode);
        const spacingPct = config.gridSpacingPct / 100;
        const biasShift = 0.45 * spacingPct * profile.centerShift;
        const effectiveCenter = centerOverride === null
          ? round(config.centerPrice * (1 + biasShift))
          : round(centerOverride);
        const displayLevels = [effectiveCenter];
        const tradeUpper = [];
        const tradeLower = [];
        const spacingValue = effectiveCenter * spacingPct;
        const buyLevelCount = Math.max(2, config.gridCount + profile.buyLevelsDelta);
        const sellLevelCount = Math.max(2, config.gridCount + profile.sellLevelsDelta);

        for (let step = 1; step <= sellLevelCount; step += 1) {
          const upper = round(effectiveCenter + (spacingValue * step));
          tradeUpper.push(upper);
          displayLevels.push(upper);
        }

        for (let step = 1; step <= buyLevelCount; step += 1) {
          const lower = round(effectiveCenter - (spacingValue * step));
          if (lower > 0) {
            tradeLower.push(lower);
            displayLevels.push(lower);
          }
        }

        displayLevels.sort((left, right) => left - right);
        tradeUpper.sort((left, right) => left - right);
        tradeLower.sort((left, right) => left - right);

        return {
          center: effectiveCenter,
          display: displayLevels,
          tradeUpper,
          tradeLower,
        };
      }

      function mulberry32(seed) {
        return function nextRandom() {
          let hash = seed += 0x6d2b79f5;
          hash = Math.imul(hash ^ (hash >>> 15), hash | 1);
          hash ^= hash + Math.imul(hash ^ (hash >>> 7), hash | 61);
          return ((hash ^ (hash >>> 14)) >>> 0) / 4294967296;
        };
      }

      function generateSeries(config) {
        const rng = mulberry32((Math.round(config.centerPrice * 100) ^ (config.gridCount * 97)) >>> 0);
        const spacingValue = config.centerPrice * config.gridSpacingPct / 100;
        const amplitude = spacingValue * Math.max(config.gridCount * 0.88, 2.6);
        const lowerBound = Math.max(config.centerPrice - (amplitude * 1.55), config.centerPrice * 0.35, 0.1);
        const upperBound = config.centerPrice + (amplitude * 1.55);
        const points = [];
        let previous = config.centerPrice;

        for (let index = 0; index < 480; index += 1) {
          const primaryWave = Math.sin(index / 9.5) * amplitude * 0.78;
          const secondaryWave = Math.sin((index / 28) + 0.65) * amplitude * 0.42;
          const tertiaryWave = Math.cos(index / 4.6) * spacingValue * 0.34;
          const drift = Math.sin(index / 85) * spacingValue * 1.35;
          const noise = (rng() - 0.5) * spacingValue * 0.65;
          const target = config.centerPrice + primaryWave + secondaryWave + tertiaryWave + drift + noise;
          previous = lerp(previous, target, 0.46);
          previous = clamp(previous, lowerBound, upperBound);
          points.push(round(previous));
        }

        if (points.length > 0) {
          points[0] = round(config.centerPrice);
        }
        return points;
      }

      function computeYDomain(series, levels) {
        const values = series.concat(levels);
        const minimum = Math.min(...values);
        const maximum = Math.max(...values);
        const padding = Math.max((maximum - minimum) * 0.12, 1.5);
        return {
          min: Math.max(0.01, minimum - padding),
          max: maximum + padding,
        };
      }

      function xFor(indexValue) {
        const denominator = Math.max(state.series.length - 1, 1);
        const usableWidth = chartBox.right - chartBox.left;
        return chartBox.left + (usableWidth * indexValue / denominator);
      }

      function yFor(price) {
        const domain = state.yDomain.max - state.yDomain.min || 1;
        const ratio = (price - state.yDomain.min) / domain;
        return chartBox.bottom - ((chartBox.bottom - chartBox.top) * ratio);
      }

      function currentDisplayIndex() {
        return Math.min(state.currentIndex + state.partialProgress, Math.max(state.series.length - 1, 0));
      }

      function currentDisplayPrice() {
        if (state.series.length === 0) {
          return state.config.centerPrice;
        }
        const current = state.series[state.currentIndex] ?? state.series[0];
        const next = state.series[state.currentIndex + 1] ?? current;
        return lerp(current, next, state.partialProgress);
      }

      function buildVisiblePoints() {
        if (state.series.length === 0) {
          return [];
        }
        const points = [];
        for (let index = 0; index <= state.currentIndex; index += 1) {
          points.push([xFor(index), yFor(state.series[index])]);
        }
        if (state.currentIndex < state.series.length - 1 && state.partialProgress > 0) {
          points.push([xFor(currentDisplayIndex()), yFor(currentDisplayPrice())]);
        }
        if (points.length === 0) {
          points.push([xFor(0), yFor(state.series[0])]);
        }
        return points;
      }

      function buildLinePath(points) {
        if (points.length === 0) {
          return '';
        }
        return points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point[0].toFixed(2)} ${point[1].toFixed(2)}`).join(' ');
      }

      function buildAreaPath(points) {
        if (points.length < 2) {
          const x = points.length === 1 ? points[0][0] : xFor(0);
          const y = points.length === 1 ? points[0][1] : yFor(state.config.centerPrice);
          return `M ${x.toFixed(2)} ${chartBox.bottom.toFixed(2)} L ${x.toFixed(2)} ${y.toFixed(2)} L ${x.toFixed(2)} ${chartBox.bottom.toFixed(2)} Z`;
        }
        const first = points[0];
        const last = points[points.length - 1];
        return `${buildLinePath(points)} L ${last[0].toFixed(2)} ${chartBox.bottom.toFixed(2)} L ${first[0].toFixed(2)} ${chartBox.bottom.toFixed(2)} Z`;
      }

      function polygonPoints(x, y, size, direction) {
        if (direction === 'long') {
          return `${x},${y - size} ${x - size},${y + size} ${x + size},${y + size}`;
        }
        return `${x},${y + size} ${x - size},${y - size} ${x + size},${y - size}`;
      }

      function totalPositionSize(positions) {
        return positions.reduce((sum, position) => sum + position.size, 0);
      }

      function averageEntry(positions) {
        const totalSize = totalPositionSize(positions);
        if (totalSize === 0) {
          return 0;
        }
        const total = positions.reduce((sum, position) => sum + (position.entry * position.size), 0);
        return total / totalSize;
      }

      function unrealizedPnl(markPrice) {
        const longPnl = state.longs.reduce((sum, position) => sum + ((markPrice - position.entry) * position.size), 0);
        const shortPnl = state.shorts.reduce((sum, position) => sum + ((position.entry - markPrice) * position.size), 0);
        return longPnl + shortPnl;
      }

      function setValueTone(element, value) {
        element.classList.remove('positive', 'negative');
        element.classList.add(value >= 0 ? 'positive' : 'negative');
      }

      function renderTradeLog() {
        if (state.tradeLog.length === 0) {
          ui.tradeLog.innerHTML = '<div class="log-empty">No fills yet. Press Play or use Step Forward to walk into the first grid crossing.</div>';
          return;
        }

        ui.tradeLog.innerHTML = state.tradeLog.map((entry) => {
          return `<div class="log-entry ${entry.direction}">${entry.message}</div>`;
        }).join('');
      }

      function updateButtons() {
        const atEnd = state.currentIndex >= Math.max(state.series.length - 1, 0);
        ui.playButton.disabled = state.isPlaying || atEnd;
        ui.pauseButton.disabled = !state.isPlaying;
        ui.stepButton.disabled = state.isPlaying || atEnd;
        ui.runStatus.textContent = state.isPlaying ? 'Playing' : (atEnd ? 'Complete' : 'Paused');
      }

      function speedTicksPerSecond() {
        return boundedInteger(ui.speedSlider.value, defaults.speed, 1, 24);
      }

      function syncSpeedLabel() {
        const speed = speedTicksPerSecond();
        ui.speedValue.value = `${speed} ticks/s`;
        ui.speedValue.textContent = `${speed} ticks/s`;
        state.config.speed = speed;
      }

      function registerPosition(side, entryPrice, tickIndex, size) {
        return {
          id: state.nextPositionId,
          side,
          entry: entryPrice,
          openedAt: tickIndex,
          size,
        };
      }

      function takeProfitMultiplier() {
        return state.config.takeProfitPct / 100;
      }

      function findClosableLong(level) {
        const threshold = 1 + takeProfitMultiplier();
        const candidates = state.longs.filter((position) => level >= position.entry * threshold);
        if (candidates.length === 0) {
          return null;
        }
        candidates.sort((left, right) => {
          const distance = Math.abs(left.entry - level) - Math.abs(right.entry - level);
          return distance !== 0 ? distance : right.entry - left.entry;
        });
        return candidates[0];
      }

      function findClosableShort(level) {
        const threshold = 1 - takeProfitMultiplier();
        const candidates = state.shorts.filter((position) => level <= position.entry * threshold);
        if (candidates.length === 0) {
          return null;
        }
        candidates.sort((left, right) => {
          const distance = Math.abs(left.entry - level) - Math.abs(right.entry - level);
          return distance !== 0 ? distance : left.entry - right.entry;
        });
        return candidates[0];
      }

      function markGridFlash(level, direction, realized) {
        state.gridFlash[levelKey(level)] = {
          direction,
          expiresAt: performance.now() + 760,
        };
        if (realized > 0) {
          state.flashes.push({
            level,
            direction,
            realized,
            bornAt: performance.now(),
          });
        }
      }

      function appendLog(message, direction) {
        state.tradeLog.unshift({
          message,
          direction,
        });
        state.tradeLog = state.tradeLog.slice(0, 180);
        renderTradeLog();
      }

      function processLevelCross(level, direction, tickIndex) {
        const profile = modeProfile(state.config.mode);
        let closedPosition = null;
        let realized = 0;

        if (direction === 'up') {
          const shortPosition = registerPosition('short', level, tickIndex, state.config.orderSize * profile.sellMultiplier);
          state.nextPositionId += 1;
          state.shorts.push(shortPosition);
          state.totalTrades += 1;
          closedPosition = findClosableLong(level);
          if (closedPosition !== null) {
            state.longs = state.longs.filter((position) => position.id !== closedPosition.id);
            realized = (level - closedPosition.entry) * closedPosition.size;
            state.realizedPnl += realized;
            state.totalTrades += 1;
          }
        }

        if (direction === 'down') {
          const longPosition = registerPosition('long', level, tickIndex, state.config.orderSize * profile.buyMultiplier);
          state.nextPositionId += 1;
          state.longs.push(longPosition);
          state.totalTrades += 1;
          closedPosition = findClosableShort(level);
          if (closedPosition !== null) {
            state.shorts = state.shorts.filter((position) => position.id !== closedPosition.id);
            realized = (closedPosition.entry - level) * closedPosition.size;
            state.realizedPnl += realized;
            state.totalTrades += 1;
          }
        }

        markGridFlash(level, direction, realized);

        const fillSide = direction === 'up' ? 'SHORT' : 'LONG';
        const oppositeSide = direction === 'up' ? 'LONG' : 'SHORT';
        let message = `${formatTime(tickIndex)} - ${fillSide} filled @ ${formatPrice(level)}`;
        if (closedPosition !== null) {
          message += `, ${oppositeSide} closed @ ${formatPrice(level)}, +$${formatPrice(realized)}`;
        } else {
          message += `, waiting for ${oppositeSide} take-profit`;
        }
        appendLog(message, direction);
      }

      function maybeTrailGrid(markPrice, tickIndex) {
        const profile = modeProfile(state.config.mode);
        if (!profile.trailing) {
          return;
        }

        const spacingValue = state.levels.center * state.config.gridSpacingPct / 100;
        if (spacingValue <= 0) {
          return;
        }

        const offset = markPrice - state.levels.center;
        const stepCount = Math.floor(Math.abs(offset) / spacingValue);
        if (stepCount < 1) {
          return;
        }

        const direction = offset > 0 ? 1 : -1;
        const nextCenter = round(state.levels.center + (direction * spacingValue * stepCount));
        if (Math.abs(nextCenter - state.levels.center) < 0.0001) {
          return;
        }

        state.levels = buildLevels(state.config, nextCenter);
        state.yDomain = computeYDomain(state.series, state.levels.display);
        appendLog(`${formatTime(tickIndex)} - TRAILING grid recentered to ${formatPrice(nextCenter)}`, direction > 0 ? 'up' : 'down');
      }

      function crossedTradeLevels(previousPrice, nextPrice) {
        if (nextPrice > previousPrice) {
          return state.levels.tradeUpper.filter((level) => previousPrice < level && level <= nextPrice);
        }
        if (nextPrice < previousPrice) {
          return state.levels.tradeLower.filter((level) => nextPrice <= level && level < previousPrice).sort((left, right) => right - left);
        }
        return [];
      }

      function advanceTick() {
        if (state.currentIndex >= state.series.length - 1) {
          state.isPlaying = false;
          updateButtons();
          return;
        }

        const previousPrice = state.series[state.currentIndex];
        const nextPrice = state.series[state.currentIndex + 1];
        const direction = nextPrice > previousPrice ? 'up' : (nextPrice < previousPrice ? 'down' : null);
        state.currentIndex += 1;
        state.partialProgress = 0;

        if (direction !== null) {
          crossedTradeLevels(previousPrice, nextPrice).forEach((level) => {
            processLevelCross(level, direction, state.currentIndex);
          });
        }

        maybeTrailGrid(nextPrice, state.currentIndex);

        if (state.currentIndex >= state.series.length - 1) {
          state.isPlaying = false;
        }
        updateButtons();
      }

      function renderStats() {
        const displayPrice = currentDisplayPrice();
        const unrealized = unrealizedPnl(displayPrice);
        const longQuantity = totalPositionSize(state.longs);
        const shortQuantity = totalPositionSize(state.shorts);
        ui.openLongCount.textContent = String(state.longs.length);
        ui.openLongMeta.textContent = state.longs.length === 0
          ? 'flat'
          : `qty ${formatPrice(longQuantity)} | avg ${formatPrice(averageEntry(state.longs))}`;
        ui.openShortCount.textContent = String(state.shorts.length);
        ui.openShortMeta.textContent = state.shorts.length === 0
          ? 'flat'
          : `qty ${formatPrice(shortQuantity)} | avg ${formatPrice(averageEntry(state.shorts))}`;
        ui.realizedPnl.textContent = formatSignedCurrency(state.realizedPnl);
        ui.unrealizedPnl.textContent = formatSignedCurrency(unrealized);
        setValueTone(ui.realizedPnl, state.realizedPnl);
        setValueTone(ui.unrealizedPnl, unrealized);
        ui.totalTrades.textContent = String(state.totalTrades);
        ui.currentPrice.textContent = formatPrice(displayPrice);
        ui.currentPriceMeta.textContent = `${formatTime(Math.round(currentDisplayIndex()))} synthetic session clock`;
        ui.tickCounter.textContent = `Tick ${String(state.currentIndex).padStart(3, '0')} / ${String(Math.max(state.series.length - 1, 0)).padStart(3, '0')}`;
      }

      function renderGrid(now) {
        const gridFragment = document.createDocumentFragment();
        const axisFragment = document.createDocumentFragment();
        const currentX = xFor(currentDisplayIndex());

        state.levels.display.forEach((level) => {
          const y = yFor(level);
          const key = levelKey(level);
          const flash = state.gridFlash[key];
          const isCenter = Math.abs(level - state.levels.center) < 0.0001;
          const lineClass = flash && flash.expiresAt > now
            ? `grid-line flash-${flash.direction}`
            : `grid-line${isCenter ? ' center' : ''}`;

          gridFragment.appendChild(createSvgElement('line', {
            x1: chartBox.left,
            y1: y.toFixed(2),
            x2: chartBox.right,
            y2: y.toFixed(2),
            class: lineClass,
          }));

          const label = createSvgElement('text', {
            x: chartBox.left - 12,
            y: (y + 4).toFixed(2),
            class: `axis-label${isCenter ? ' center' : ''}`,
            'text-anchor': 'end',
          });
          label.textContent = formatPrice(level);
          axisFragment.appendChild(label);
        });

        [
          { x: chartBox.left, text: formatTime(0), anchor: 'start', className: 'axis-label axis-time' },
          { x: clamp(currentX, chartBox.left + 52, chartBox.right - 52), text: formatTime(Math.round(currentDisplayIndex())), anchor: 'middle', className: 'axis-label axis-time current' },
          { x: chartBox.right, text: formatTime(Math.max(state.series.length - 1, 0)), anchor: 'end', className: 'axis-label axis-time' },
        ].forEach((entry) => {
          const node = createSvgElement('text', {
            x: entry.x.toFixed(2),
            y: chartBox.bottom + 26,
            class: entry.className,
            'text-anchor': entry.anchor,
          });
          node.textContent = entry.text;
          axisFragment.appendChild(node);
        });

        chart.gridLayer.replaceChildren(gridFragment);
        chart.axisLayer.replaceChildren(axisFragment);
      }

      function renderPositions(displayPrice, currentX, currentY) {
        const fragment = document.createDocumentFragment();
        const longs = [...state.longs].sort((left, right) => left.entry - right.entry);
        const shorts = [...state.shorts].sort((left, right) => right.entry - left.entry);

        longs.forEach((position, index) => {
          const x = chartBox.right + 20 + ((index % 2) * 16);
          const y = yFor(position.entry);
          fragment.appendChild(createSvgElement('line', {
            x1: currentX.toFixed(2),
            y1: currentY.toFixed(2),
            x2: x.toFixed(2),
            y2: y.toFixed(2),
            class: 'position-tether long',
          }));
          fragment.appendChild(createSvgElement('polygon', {
            points: polygonPoints(x, y, 6, 'long'),
            class: 'position-marker long',
          }));
        });

        shorts.forEach((position, index) => {
          const x = chartBox.right + 52 + ((index % 2) * 16);
          const y = yFor(position.entry);
          fragment.appendChild(createSvgElement('line', {
            x1: currentX.toFixed(2),
            y1: currentY.toFixed(2),
            x2: x.toFixed(2),
            y2: y.toFixed(2),
            class: 'position-tether short',
          }));
          fragment.appendChild(createSvgElement('polygon', {
            points: polygonPoints(x, y, 6, 'short'),
            class: 'position-marker short',
          }));
        });

        chart.positionLayer.replaceChildren(fragment);
      }

      function renderFlashes(now) {
        state.flashes = state.flashes.filter((flash) => (now - flash.bornAt) < 1200);
        const fragment = document.createDocumentFragment();
        state.flashes.forEach((flash, index) => {
          const life = (now - flash.bornAt) / 1200;
          const x = Math.min(chartBox.right - 12, xFor(Math.min(state.currentIndex + 0.35 + (index * 0.04), state.series.length - 1)));
          const y = yFor(flash.level) - (life * 34);
          const node = createSvgElement('text', {
            x: x.toFixed(2),
            y: y.toFixed(2),
            class: `flash-badge ${flash.direction}`,
            opacity: (1 - life).toFixed(3),
          });
          node.textContent = `+$${formatPrice(flash.realized)}`;
          fragment.appendChild(node);
        });
        chart.flashLayer.replaceChildren(fragment);
      }

      function renderChart(now) {
        renderGrid(now);
        const points = buildVisiblePoints();
        chart.areaPath.setAttribute('d', buildAreaPath(points));
        chart.pricePath.setAttribute('d', buildLinePath(points));

        const displayIndex = currentDisplayIndex();
        const displayPrice = currentDisplayPrice();
        const currentX = xFor(displayIndex);
        const currentY = yFor(displayPrice);

        chart.priceGuide.setAttribute('x1', currentX.toFixed(2));
        chart.priceGuide.setAttribute('y1', currentY.toFixed(2));
        chart.priceGuide.setAttribute('x2', chart.right ? chart.right : chartBox.right);
        chart.priceGuide.setAttribute('y2', currentY.toFixed(2));
        chart.priceCursor.setAttribute('transform', `translate(${currentX.toFixed(2)} ${currentY.toFixed(2)})`);

        const tagOnRight = currentX <= chartBox.right - 98;
        chart.priceTag.setAttribute('x', (tagOnRight ? currentX + 12 : currentX - 12).toFixed(2));
        chart.priceTag.setAttribute('y', clamp(currentY - 14, chartBox.top + 16, chartBox.bottom - 6).toFixed(2));
        chart.priceTag.setAttribute('text-anchor', tagOnRight ? 'start' : 'end');
        chart.priceTag.textContent = formatPrice(displayPrice);

        renderPositions(displayPrice, currentX, currentY);
        renderFlashes(now);
      }

      function resetSimulation() {
        state.config = readConfig();
        state.levels = buildLevels(state.config);
        state.series = generateSeries(state.config);
        state.yDomain = computeYDomain(state.series, state.levels.display);
        state.currentIndex = 0;
        state.partialProgress = 0;
        state.accumulator = 0;
        state.isPlaying = false;
        state.lastFrame = 0;
        state.longs = [];
        state.shorts = [];
        state.realizedPnl = 0;
        state.totalTrades = 0;
        state.tradeLog = [];
        state.flashes = [];
        state.gridFlash = Object.create(null);
        state.nextPositionId = 1;
        renderTradeLog();
        updateButtons();
        renderStats();
        renderChart(performance.now());
      }

      function animationFrame(now) {
        if (state.isPlaying && state.currentIndex < state.series.length - 1) {
          if (state.lastFrame === 0) {
            state.lastFrame = now;
          }
          const delta = now - state.lastFrame;
          state.lastFrame = now;
          const tickDuration = 1000 / Math.max(state.config.speed, 1);
          state.accumulator += delta;

          while (state.accumulator >= tickDuration && state.currentIndex < state.series.length - 1) {
            state.accumulator -= tickDuration;
            advanceTick();
          }

          state.partialProgress = state.currentIndex < state.series.length - 1
            ? Math.min(state.accumulator / tickDuration, 0.999)
            : 0;
        }

        renderStats();
        renderChart(now);
        requestAnimationFrame(animationFrame);
      }

      ui.playButton.addEventListener('click', () => {
        if (state.currentIndex >= state.series.length - 1) {
          return;
        }
        state.isPlaying = true;
        state.lastFrame = 0;
        updateButtons();
      });

      ui.pauseButton.addEventListener('click', () => {
        state.isPlaying = false;
        state.lastFrame = 0;
        updateButtons();
      });

      ui.stepButton.addEventListener('click', () => {
        state.isPlaying = false;
        state.lastFrame = 0;
        state.accumulator = 0;
        state.partialProgress = 0;
        advanceTick();
        renderStats();
        renderChart(performance.now());
      });

      ui.resetButton.addEventListener('click', () => {
        resetSimulation();
      });

      ui.modeLongButton.addEventListener('click', () => {
        setMode('long');
      });

      ui.modeNeutralButton.addEventListener('click', () => {
        setMode('neutral');
      });

      ui.modeShortButton.addEventListener('click', () => {
        setMode('short');
      });

      ui.modeTrailingButton.addEventListener('click', () => {
        setMode('trailing');
      });

      ui.speedSlider.addEventListener('input', () => {
        syncSpeedLabel();
      });

      setDefaults();
      setMode(defaults.mode, false);
      syncSpeedLabel();
      resetSimulation();
      requestAnimationFrame(animationFrame);
    })();
  </script>
</body>
</html>
"""


def write_hedge_mode_grid_demo(output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_hedge_mode_grid_demo_html(), encoding="utf-8")
    return path