# -*- coding: utf-8 -*-
"""
Generator script for Red & Black Theme: Pulsus MedScout
Applies high-impact obsidian black + glowing ruby/crimson styling across templates.
"""
import os

HTML_CONTENT = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pulsus MedScout // Biomedical Literature &amp; Author Outreach Platform</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.tailwindcss.com"></script>
<script>
tailwind.config = {
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'sans-serif'],
        display: ['"Space Grotesk"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace']
      },
      colors: {
        ruby: {
          50: '#FFF1F2',
          100: '#FFE4E6',
          200: '#FECDD3',
          300: '#FDA4AF',
          400: '#FB7185',
          500: '#F43F5E',
          600: '#E11D48',
          700: '#BE123C',
          800: '#9F1239',
          900: '#881337',
          950: '#4C0519'
        },
        carbon: {
          850: '#12141D',
          900: '#0E1017',
          950: '#08090E',
          975: '#05060A'
        }
      }
    }
  }
}
</script>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg-page: #06070B;
  --panel-black: #0E1017;
  --panel-elevated: #131622;
  --panel-border: rgba(225, 29, 72, 0.22);
  --panel-border-hover: rgba(244, 63, 94, 0.45);
  --red-primary: #E11D48;
  --red-bright: #F43F5E;
  --red-deep: #BE123C;
  --text-pure: #FFFFFF;
  --text-sub: #94A3B8;
  --text-muted: #64748B;
}

body {
  background-color: var(--bg-page);
  color: #E2E8F0;
  font-family: 'Plus Jakarta Sans', sans-serif;
  min-height: 100vh;
  overflow-x: hidden;
  letter-spacing: -0.01em;
}

/* Subtle Dark Grid with Ruby Accent */
.dark-red-grid {
  position: fixed;
  inset: 0;
  background-image: 
    linear-gradient(to right, rgba(225, 29, 72, 0.04) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(225, 29, 72, 0.04) 1px, transparent 1px);
  background-size: 38px 38px;
  pointer-events: none;
  z-index: 0;
}

/* Ambient Glowing Orbs */
.ambient-orb-top {
  position: fixed;
  top: -120px;
  left: 20%;
  width: 600px;
  height: 600px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(225, 29, 72, 0.12) 0%, transparent 68%);
  filter: blur(120px);
  pointer-events: none;
  z-index: 0;
}
.ambient-orb-bottom {
  position: fixed;
  bottom: -150px;
  right: 15%;
  width: 500px;
  height: 500px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(190, 18, 60, 0.08) 0%, transparent 68%);
  filter: blur(100px);
  pointer-events: none;
  z-index: 0;
}

/* Custom Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #08090E; }
::-webkit-scrollbar-thumb { background: #E11D48; border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: #F43F5E; }

/* Obsidian & Red Panels */
.dark-card {
  background: #0E1017;
  border: 1px solid var(--panel-border);
  border-radius: 18px;
  box-shadow: 0 10px 35px rgba(0, 0, 0, 0.7), 0 0 18px rgba(225, 29, 72, 0.05);
  position: relative;
  transition: all 0.22s ease;
}
.dark-card:hover {
  border-color: var(--panel-border-hover);
  box-shadow: 0 14px 45px rgba(0, 0, 0, 0.8), 0 0 25px rgba(225, 29, 72, 0.1);
}

/* Inputs */
.dark-input {
  width: 100%;
  background: #090A10;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  padding: 13px 16px;
  color: #FFFFFF;
  font-size: 14px;
  transition: all 0.2s ease;
}
.dark-input:focus {
  outline: none;
  border-color: #E11D48;
  box-shadow: 0 0 0 3px rgba(225, 29, 72, 0.28);
  background: #0C0E16;
}
.dark-input::placeholder {
  color: #64748B;
}

/* Primary Action Button (Red & Black Glow) */
.btn-red-action {
  background: linear-gradient(135deg, #9F1239 0%, #E11D48 55%, #F43F5E 100%);
  color: #FFFFFF;
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 0.03em;
  padding: 13px 26px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-shadow: 0 4px 22px rgba(225, 29, 72, 0.45);
  transition: all 0.2s ease;
  cursor: pointer;
  border: 1px solid rgba(255, 255, 255, 0.15);
}
.btn-red-action:hover:not(:disabled) {
  transform: translateY(-1.5px);
  box-shadow: 0 6px 30px rgba(244, 63, 94, 0.65);
  border-color: rgba(255, 255, 255, 0.3);
}
.btn-red-action:active:not(:disabled) {
  transform: translateY(0);
}
.btn-red-action:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* Excel Download Button */
.btn-excel-green {
  background: linear-gradient(135deg, #065F46 0%, #059669 50%, #10B981 100%);
  color: #FFFFFF;
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 700;
  font-size: 13px;
  padding: 10px 20px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 4px 18px rgba(16, 185, 129, 0.35);
  transition: all 0.2s ease;
  text-decoration: none;
  border: 1px solid rgba(255, 255, 255, 0.15);
}
.btn-excel-green:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 24px rgba(16, 185, 129, 0.55);
  color: #FFFFFF;
}

/* Secondary Button (Obsidian with Red hover) */
.btn-obsidian {
  background: #11131C;
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #E2E8F0;
  font-weight: 600;
  border-radius: 10px;
  padding: 8px 14px;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}
.btn-obsidian:hover {
  background: #1B121A;
  border-color: rgba(244, 63, 94, 0.4);
  color: #FDA4AF;
}

/* Repository Tile (All 34 Repos Displayed in Red & Black) */
.repo-tile {
  background: #0B0D14;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 8px 10px;
  cursor: pointer;
  transition: all 0.18s ease;
  user-select: none;
  display: flex;
  align-items: center;
  gap: 8px;
}
.repo-tile:hover {
  border-color: rgba(244, 63, 94, 0.45);
  background: #14111A;
  transform: translateY(-1px);
}
.repo-tile.active {
  background: linear-gradient(135deg, rgba(225, 29, 72, 0.18) 0%, rgba(14, 16, 24, 0.95) 100%);
  border-color: #E11D48;
  box-shadow: 0 0 12px rgba(225, 29, 72, 0.25);
}
.repo-tile.active .repo-check {
  background-color: #E11D48;
  border-color: #E11D48;
  color: #FFFFFF;
}
.repo-check {
  width: 15px;
  height: 15px;
  border-radius: 4px;
  border: 1.5px solid #475569;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 800;
  transition: all 0.15s ease;
  flex-shrink: 0;
  color: transparent;
}

/* Category Filter Chips */
.filter-chip {
  padding: 7px 11px;
  border-radius: 9px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  background: #0B0D14;
  color: #94A3B8;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.18s ease;
  display: flex;
  align-items: center;
  gap: 5px;
}
.filter-chip:hover {
  border-color: rgba(244, 63, 94, 0.45);
  color: #FDA4AF;
  background: #14111A;
}
.filter-chip.selected {
  border-color: #E11D48;
  background: rgba(225, 29, 72, 0.22);
  color: #FFFFFF;
  font-weight: 700;
  box-shadow: 0 0 8px rgba(225, 29, 72, 0.25);
}

/* Suggestions Dropdown */
#suggestionsList {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 6px;
  background: #0E1018;
  border: 1px solid rgba(244, 63, 94, 0.35);
  border-radius: 12px;
  box-shadow: 0 16px 45px rgba(0, 0, 0, 0.85), 0 0 20px rgba(225, 29, 72, 0.15);
  z-index: 50;
  max-height: 260px;
  overflow-y: auto;
  display: none;
}
.suggestion-item {
  padding: 10px 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  transition: all 0.15s ease;
}
.suggestion-item:last-child { border-bottom: none; }
.suggestion-item:hover, .suggestion-item.active {
  background: rgba(225, 29, 72, 0.18);
  color: #FFFFFF;
}
.suggestion-cat {
  font-size: 10px;
  font-family: 'JetBrains Mono', monospace;
  padding: 2px 7px;
  border-radius: 6px;
  background: rgba(225, 29, 72, 0.2);
  color: #FB7185;
  border: 1px solid rgba(225, 29, 72, 0.3);
  font-weight: 600;
}

/* Accordion */
#filterAccordion {
  transition: max-height 0.35s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.25s ease;
}
#filterAccordion.closed { max-height: 0; opacity: 0; overflow: hidden; }
#filterAccordion.open { max-height: 600px; opacity: 1; }

/* Progress Bar */
.red-progress-bar {
  height: 5px;
  background: linear-gradient(90deg, #9F1239, #E11D48, #FDA4AF, #E11D48);
  background-size: 200% 100%;
  animation: laserStream 1.6s linear infinite;
  border-radius: 99px;
  box-shadow: 0 0 10px rgba(225, 29, 72, 0.6);
}
@keyframes laserStream {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Results Table */
.data-row {
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  transition: all 0.15s ease;
  background: #0E1017;
}
.data-row:nth-child(even) {
  background: #0A0C12;
}
.data-row:hover {
  background: #17111A !important;
  border-left: 3px solid #E11D48;
}
</style>
</head>
<body class="relative">

<!-- Subtle Red & Black Background Grid & Ambient Lighting -->
<div class="dark-red-grid"></div>
<div class="ambient-orb-top"></div>
<div class="ambient-orb-bottom"></div>

<div class="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-5">

  <!-- ═════════════════════════════════════════════════════════════════════ -->
  <!-- 1. SLEEK RED & BLACK HEADER                                          -->
  <!-- ═════════════════════════════════════════════════════════════════════ -->
  <header class="dark-card p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
    <div class="flex items-center gap-4">
      <!-- Ruby Glowing Logo Icon -->
      <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-rose-900 via-rose-700 to-rose-600 flex items-center justify-center shadow-lg shadow-rose-600/30 border border-rose-500/40">
        <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/>
        </svg>
      </div>
      <div>
        <div class="flex items-center gap-2.5">
          <h1 class="font-display text-2xl font-extrabold tracking-tight text-white">
            Pulsus <span class="text-rose-500 font-extrabold drop-shadow-[0_0_12px_rgba(244,63,94,0.4)]">MedScout</span>
          </h1>
          <span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-rose-950/80 text-rose-300 border border-rose-600/50 flex items-center gap-1.5 shadow-sm">
            <span class="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping"></span>
            LIVE ENGINE
          </span>
        </div>
        <p class="text-xs text-slate-400 mt-0.5">Biomedical Literature &amp; Author Outreach Platform · Pulsus Group</p>
      </div>
    </div>

    <!-- Live Metrics Counter Strip -->
    <div class="flex items-center gap-3 self-stretch md:self-auto justify-end flex-wrap">
      <div class="px-3.5 py-1.5 rounded-xl bg-carbon-850/90 border border-rose-900/40 text-center shadow-inner">
        <span class="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">Indexed</span>
        <span class="font-mono text-sm font-bold text-rose-400">200M+ Papers</span>
      </div>
      <div class="px-3.5 py-1.5 rounded-xl bg-carbon-850/90 border border-rose-900/40 text-center shadow-inner">
        <span class="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">Network</span>
        <span class="font-mono text-sm font-bold text-rose-400">34 Repositories</span>
      </div>
      <div class="px-3.5 py-1.5 rounded-xl bg-carbon-850/90 border border-emerald-900/50 text-center shadow-inner">
        <span class="text-[10px] font-mono text-emerald-400/80 uppercase tracking-wider block">Validation</span>
        <span class="font-mono text-sm font-bold text-emerald-400">100% Verified</span>
      </div>
    </div>
  </header>

  <!-- ═════════════════════════════════════════════════════════════════════ -->
  <!-- 2. SEARCH & EXTRACTION COMMAND FORM                                  -->
  <!-- ═════════════════════════════════════════════════════════════════════ -->
  <section class="dark-card p-6 space-y-5">
    <form id="extractForm" class="space-y-5">

      <!-- Keyword Input Row with Auto-Suggestions -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-3 items-end">
        <div class="lg:col-span-8 space-y-1.5 relative">
          <label class="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-rose-400">
            <span class="flex items-center gap-1.5">
              <svg class="w-3.5 h-3.5 text-rose-500" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
              </svg>
              Research Topic or Paper Title Keyword
            </span>
            <span class="text-[10px] text-slate-500 font-mono normal-case">type for instant suggestions</span>
          </label>
          <div class="relative">
            <input type="text" id="topic" name="topic" required autocomplete="off"
                   placeholder="e.g. Immunotherapy in Glioblastoma, CRISPR-Cas13, Cardiovascular Genetics..."
                   class="dark-input font-medium placeholder-slate-500 text-sm pl-4 pr-10">
            <div class="absolute right-3.5 top-1/2 -translate-y-1/2 text-rose-500">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
            </div>
            <!-- Auto-Suggestions Dropdown -->
            <div id="suggestionsList"></div>
          </div>
        </div>

        <div class="lg:col-span-2 space-y-1.5">
          <label class="block text-xs font-bold uppercase tracking-wider text-rose-400">Target Limit</label>
          <input type="number" id="max_papers" name="max_papers" min="1" max="1000" value="15"
                 class="dark-input font-mono font-bold text-center text-sm">
        </div>

        <div class="lg:col-span-2">
          <button type="submit" id="submitBtn" class="btn-red-action w-full py-3.5">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
            <span>EXTRACT DATA</span>
          </button>
        </div>
      </div>

      <!-- Quick Topics -->
      <div class="flex items-center gap-2 flex-wrap text-xs pt-0.5">
        <span class="text-slate-500 font-mono text-[11px]">Popular:</span>
        <button type="button" onclick="setTopic('Cancer Immunotherapy Checkpoint Inhibitors')" class="px-2.5 py-1 rounded-md bg-carbon-850 hover:bg-rose-950 text-slate-300 hover:text-rose-300 border border-slate-800 hover:border-rose-700/50 text-[11px] transition-colors">Cancer Immunotherapy</button>
        <button type="button" onclick="setTopic('CRISPR-Cas9 Base Editing Therapeutics')" class="px-2.5 py-1 rounded-md bg-carbon-850 hover:bg-rose-950 text-slate-300 hover:text-rose-300 border border-slate-800 hover:border-rose-700/50 text-[11px] transition-colors">CRISPR Gene Editing</button>
        <button type="button" onclick="setTopic('Alzheimer Disease Amyloid Tau Biomarkers')" class="px-2.5 py-1 rounded-md bg-carbon-850 hover:bg-rose-950 text-slate-300 hover:text-rose-300 border border-slate-800 hover:border-rose-700/50 text-[11px] transition-colors">Alzheimer Biomarkers</button>
        <button type="button" onclick="setTopic('Cardiovascular Risk Factors in Diabetes')" class="px-2.5 py-1 rounded-md bg-carbon-850 hover:bg-rose-950 text-slate-300 hover:text-rose-300 border border-slate-800 hover:border-rose-700/50 text-[11px] transition-colors">Cardiovascular Diabetes</button>
      </div>

      <hr class="border-rose-900/30">

      <!-- ═════════════════════════════════════════════════════════════════ -->
      <!-- 3. ALL 34 REPOSITORIES SELECTOR (DISPLAYED DIRECTLY ON SCREEN)     -->
      <!-- ═════════════════════════════════════════════════════════════════ -->
      <div class="space-y-3">
        <div class="flex flex-wrap items-center justify-between gap-2.5">
          <div class="flex items-center gap-2">
            <span class="text-xs font-bold uppercase tracking-wider text-rose-400 font-display flex items-center gap-1.5">
              <svg class="w-4 h-4 text-rose-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>
              Select Target Repositories (All 34 Platforms Available)
            </span>
            <span id="selectedSourcesBadge" class="px-2.5 py-0.5 rounded-full text-[11px] font-mono font-bold bg-rose-950/90 text-rose-300 border border-rose-700/50">
              34 Active
            </span>
          </div>

          <!-- Presets and Filter -->
          <div class="flex items-center gap-1.5 flex-wrap text-xs">
            <input type="text" id="repoSearchInput" oninput="filterRepoGrid()" placeholder="Filter repositories..." class="dark-input text-xs py-1 px-2.5 w-44">
            <button type="button" onclick="selectPreset('all')" class="px-2.5 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white font-semibold text-[11px] shadow-sm transition-colors">Select All 34</button>
            <button type="button" onclick="selectPreset('biomedical')" class="px-2.5 py-1 rounded bg-carbon-850 hover:bg-rose-950 text-slate-300 hover:text-rose-300 border border-slate-800 text-[11px] transition-colors">Biomedical (11)</button>
            <button type="button" onclick="selectPreset('preprints')" class="px-2.5 py-1 rounded bg-carbon-850 hover:bg-rose-950 text-slate-300 hover:text-rose-300 border border-slate-800 text-[11px] transition-colors">Preprints (9)</button>
            <button type="button" onclick="selectPreset('global')" class="px-2.5 py-1 rounded bg-carbon-850 hover:bg-rose-950 text-slate-300 hover:text-rose-300 border border-slate-800 text-[11px] transition-colors">Global (14)</button>
            <button type="button" onclick="selectPreset('clear')" class="px-2.5 py-1 rounded bg-carbon-850 hover:bg-slate-800 text-slate-400 border border-slate-800 text-[11px] transition-colors">Clear All</button>
          </div>
        </div>

        <!-- 34 REPOSITORIES COMPLETE GRID -->
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2 max-h-72 overflow-y-auto pr-1" id="allReposGrid">

          <!-- 1. PLOS ONE -->
          <div class="repo-tile active" data-tag="biomedical" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="plos" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">PLOS ONE</span><span class="text-[9px] text-slate-400 font-mono block">Peer-Reviewed</span></div>
          </div>

          <!-- 2. PubMed -->
          <div class="repo-tile active" data-tag="biomedical" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="pubmed" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">PubMed / NCBI</span><span class="text-[9px] text-slate-400 font-mono block">NLM Entrez</span></div>
          </div>

          <!-- 3. bioRxiv -->
          <div class="repo-tile active" data-tag="preprints" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="biorxiv" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">bioRxiv</span><span class="text-[9px] text-slate-400 font-mono block">Biology Preprints</span></div>
          </div>

          <!-- 4. medRxiv -->
          <div class="repo-tile active" data-tag="preprints" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="medrxiv" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">medRxiv</span><span class="text-[9px] text-slate-400 font-mono block">Health Preprints</span></div>
          </div>

          <!-- 5. Europe PMC -->
          <div class="repo-tile active" data-tag="biomedical" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="europepmc" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">Europe PMC</span><span class="text-[9px] text-slate-400 font-mono block">EMBL-EBI</span></div>
          </div>

          <!-- 6. arXiv.org -->
          <div class="repo-tile active" data-tag="preprints" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="arxiv" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">arXiv.org</span><span class="text-[9px] text-slate-400 font-mono block">Cornell Preprints</span></div>
          </div>

          <!-- 7. OpenAlex -->
          <div class="repo-tile active" data-tag="global" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="openalex" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">OpenAlex</span><span class="text-[9px] text-slate-400 font-mono block">250M+ Papers</span></div>
          </div>

          <!-- 8. Semantic Scholar -->
          <div class="repo-tile active" data-tag="global" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="semanticscholar" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">Semantic Scholar</span><span class="text-[9px] text-slate-400 font-mono block">AI Knowledge Graph</span></div>
          </div>

          <!-- 9. Crossref -->
          <div class="repo-tile active" data-tag="global" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="crossref" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">Crossref</span><span class="text-[9px] text-slate-400 font-mono block">DOI Resolver</span></div>
          </div>

          <!-- 10. eLife -->
          <div class="repo-tile active" data-tag="biomedical" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="elife" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">eLife</span><span class="text-[9px] text-slate-400 font-mono block">Biomedical OA</span></div>
          </div>

          <!-- 11. Preprints.org -->
          <div class="repo-tile active" data-tag="preprints" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="preprints" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">Preprints.org</span><span class="text-[9px] text-slate-400 font-mono block">MDPI Platform</span></div>
          </div>

          <!-- 12. ScienceDirect -->
          <div class="repo-tile active" data-tag="global" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="sciencedirect" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">ScienceDirect</span><span class="text-[9px] text-slate-400 font-mono block">Elsevier OA</span></div>
          </div>

          <!-- 13. iMedPub -->
          <div class="repo-tile active" data-tag="biomedical" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="imedpub" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">iMedPub</span><span class="text-[9px] text-slate-400 font-mono block">Clinical Journals</span></div>
          </div>

          <!-- 14. OSF Preprints -->
          <div class="repo-tile active" data-tag="preprints" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="osf" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">OSF Preprints</span><span class="text-[9px] text-slate-400 font-mono block">Open Science</span></div>
          </div>

          <!-- 15. ChemRxiv -->
          <div class="repo-tile active" data-tag="preprints" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="chemrxiv" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">ChemRxiv</span><span class="text-[9px] text-slate-400 font-mono block">Chemistry Preprints</span></div>
          </div>

          <!-- 16. PeerJ -->
          <div class="repo-tile active" data-tag="biomedical" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="peerj" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">PeerJ</span><span class="text-[9px] text-slate-400 font-mono block">Biological Sciences</span></div>
          </div>

          <!-- 17. F1000Research -->
          <div class="repo-tile active" data-tag="biomedical" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="f1000" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">F1000Research</span><span class="text-[9px] text-slate-400 font-mono block">Post-Pub Review</span></div>
          </div>

          <!-- 18. DOAJ -->
          <div class="repo-tile active" data-tag="global" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="doaj" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">DOAJ</span><span class="text-[9px] text-slate-400 font-mono block">Open Directory</span></div>
          </div>

          <!-- 19. BASE -->
          <div class="repo-tile active" data-tag="global" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="base" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">BASE Search</span><span class="text-[9px] text-slate-400 font-mono block">Bielefeld Engine</span></div>
          </div>

          <!-- 20. CORE -->
          <div class="repo-tile active" data-tag="global" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="core" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">CORE OA</span><span class="text-[9px] text-slate-400 font-mono block">Global Aggregator</span></div>
          </div>

          <!-- 21. Zenodo -->
          <div class="repo-tile active" data-tag="preprints" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="zenodo" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">Zenodo</span><span class="text-[9px] text-slate-400 font-mono block">CERN Universal</span></div>
          </div>

          <!-- 22. ResearchGate -->
          <div class="repo-tile active" data-tag="global" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="researchgate" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">ResearchGate</span><span class="text-[9px] text-slate-400 font-mono block">Academic Network</span></div>
          </div>

          <!-- 23. Frontiers -->
          <div class="repo-tile active" data-tag="biomedical" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="frontiers" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">Frontiers</span><span class="text-[9px] text-slate-400 font-mono block">Frontiers in Med</span></div>
          </div>

          <!-- 24. MDPI -->
          <div class="repo-tile active" data-tag="biomedical" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="mdpi" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">MDPI</span><span class="text-[9px] text-slate-400 font-mono block">Open Journals</span></div>
          </div>

          <!-- 25. Hindawi -->
          <div class="repo-tile active" data-tag="biomedical" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="hindawi" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">Hindawi</span><span class="text-[9px] text-slate-400 font-mono block">Peer-Reviewed OA</span></div>
          </div>

          <!-- 26. BioMed Central -->
          <div class="repo-tile active" data-tag="biomedical" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="biomedcentral" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">BMC</span><span class="text-[9px] text-slate-400 font-mono block">BioMed Central</span></div>
          </div>

          <!-- 27. PubMed Central -->
          <div class="repo-tile active" data-tag="biomedical" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="pmc" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">NCBI PMC</span><span class="text-[9px] text-slate-400 font-mono block">PubMed Central</span></div>
          </div>

          <!-- 28. Springer Open -->
          <div class="repo-tile active" data-tag="global" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="springer" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">Springer Open</span><span class="text-[9px] text-slate-400 font-mono block">Springer Nature</span></div>
          </div>

          <!-- 29. Taylor & Francis -->
          <div class="repo-tile active" data-tag="global" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="tandf" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">Taylor &amp; Francis</span><span class="text-[9px] text-slate-400 font-mono block">T&amp;F Open</span></div>
          </div>

          <!-- 30. SSRN -->
          <div class="repo-tile active" data-tag="preprints" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="ssrn" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">SSRN</span><span class="text-[9px] text-slate-400 font-mono block">Social &amp; Health</span></div>
          </div>

          <!-- 31. EarthArXiv -->
          <div class="repo-tile active" data-tag="preprints" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="eartharxiv" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">EarthArXiv</span><span class="text-[9px] text-slate-400 font-mono block">Earth Sciences</span></div>
          </div>

          <!-- 32. ESSOAr -->
          <div class="repo-tile active" data-tag="preprints" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="essoar" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">ESSOAr</span><span class="text-[9px] text-slate-400 font-mono block">Space &amp; Earth OA</span></div>
          </div>

          <!-- 33. SciELO -->
          <div class="repo-tile active" data-tag="global" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="scielo" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">SciELO</span><span class="text-[9px] text-slate-400 font-mono block">Latin America &amp; Global</span></div>
          </div>

          <!-- 34. HAL Open Archive -->
          <div class="repo-tile active" data-tag="global" onclick="toggleRepoTile(this)">
            <input type="checkbox" name="source_sites[]" value="hal" checked class="hidden source-cb">
            <div class="repo-check">✓</div>
            <div class="min-w-0"><span class="text-xs font-bold text-white block truncate">HAL Archive</span><span class="text-[9px] text-slate-400 font-mono block">French Open Archive</span></div>
          </div>

        </div>
      </div>

      <hr class="border-rose-900/30">

      <!-- ═════════════════════════════════════════════════════════════════ -->
      <!-- 4. ADVANCED FILTERS: CLASSIFICATION, YEARS & 36+ COUNTRIES        -->
      <!-- ═════════════════════════════════════════════════════════════════ -->
      <div>
        <div class="flex items-center justify-between">
          <button type="button" id="accordionToggleBtn"
                  class="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-300 hover:text-rose-400 transition-colors">
            <svg id="accordionArrow" class="w-3.5 h-3.5 text-rose-500 transition-transform duration-300" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
            <span>Advanced Filters: Document Classification, Years &amp; Global Countries</span>
          </button>
          <div id="filterPillBadges" class="flex flex-wrap gap-1"></div>
        </div>

        <div id="filterAccordion" class="closed">
          <div class="mt-3.5 p-4 rounded-xl bg-carbon-900 border border-slate-800/80 grid grid-cols-1 md:grid-cols-3 gap-5">

            <!-- 1. Document Classification (Exact 4 Requested) -->
            <div class="space-y-2.5">
              <div class="flex items-center justify-between">
                <span class="text-xs font-bold uppercase tracking-wider text-rose-400 font-display">Document Classification</span>
                <button type="button" onclick="clearFilterGroup('article_types')" class="text-[10px] text-slate-400 hover:text-slate-200">Reset</button>
              </div>
              <div class="grid grid-cols-2 gap-1.5">
                <label class="filter-chip"><input type="checkbox" name="article_types[]" value="Research Article" class="hidden filter-cb"><span>Research Article</span></label>
                <label class="filter-chip"><input type="checkbox" name="article_types[]" value="Case Reports" class="hidden filter-cb"><span>Case Reports</span></label>
                <label class="filter-chip"><input type="checkbox" name="article_types[]" value="Brief Reports" class="hidden filter-cb"><span>Brief Reports</span></label>
                <label class="filter-chip"><input type="checkbox" name="article_types[]" value="Systematic Reports" class="hidden filter-cb"><span>Systematic Reports</span></label>
              </div>
            </div>

            <!-- 2. Publication Year -->
            <div class="space-y-2.5">
              <div class="flex items-center justify-between">
                <span class="text-xs font-bold uppercase tracking-wider text-rose-400 font-display">Publication Years</span>
                <button type="button" onclick="clearYears()" class="text-[10px] text-slate-400 hover:text-slate-200">Reset</button>
              </div>
              <div class="grid grid-cols-2 gap-2">
                <input type="number" id="year_from" name="year_from" min="1990" max="2026" placeholder="From (2023)" class="dark-input text-xs py-2 font-mono">
                <input type="number" id="year_to" name="year_to" min="1990" max="2026" placeholder="To (2026)" class="dark-input text-xs py-2 font-mono">
              </div>
              <div class="flex gap-1.5 text-xs">
                <button type="button" onclick="setYears(2024,2026)" class="px-2 py-0.5 rounded bg-carbon-850 hover:bg-rose-950 text-slate-300 hover:text-rose-300 border border-slate-800 text-[10px]">Last 2 Yrs</button>
                <button type="button" onclick="setYears(2023,2026)" class="px-2 py-0.5 rounded bg-rose-950/80 text-rose-300 border border-rose-700/50 text-[10px] font-semibold">Last 3 Yrs</button>
                <button type="button" onclick="setYears(2020,2026)" class="px-2 py-0.5 rounded bg-carbon-850 hover:bg-rose-950 text-slate-300 hover:text-rose-300 border border-slate-800 text-[10px]">Last 6 Yrs</button>
              </div>
            </div>

            <!-- 3. Expanded Countries (36+) -->
            <div class="space-y-2.5">
              <div class="flex items-center justify-between">
                <span class="text-xs font-bold uppercase tracking-wider text-rose-400 font-display">Global Countries (36+)</span>
                <button type="button" onclick="clearFilterGroup('countries')" class="text-[10px] text-slate-400 hover:text-slate-200">Reset</button>
              </div>
              <input type="text" id="countrySearch" oninput="filterCountryList()" placeholder="Quick filter country..." class="dark-input text-xs py-1.5 px-2.5 mb-1">
              <div class="max-h-36 overflow-y-auto grid grid-cols-2 gap-1 pr-1" id="countryListGrid">
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="USA" class="hidden filter-cb"><span>USA</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="UK" class="hidden filter-cb"><span>United Kingdom</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Germany" class="hidden filter-cb"><span>Germany</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="France" class="hidden filter-cb"><span>France</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Canada" class="hidden filter-cb"><span>Canada</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Australia" class="hidden filter-cb"><span>Australia</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="China" class="hidden filter-cb"><span>China</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Japan" class="hidden filter-cb"><span>Japan</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="India" class="hidden filter-cb"><span>India</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Italy" class="hidden filter-cb"><span>Italy</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Spain" class="hidden filter-cb"><span>Spain</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Netherlands" class="hidden filter-cb"><span>Netherlands</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Switzerland" class="hidden filter-cb"><span>Switzerland</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Sweden" class="hidden filter-cb"><span>Sweden</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Belgium" class="hidden filter-cb"><span>Belgium</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="South Korea" class="hidden filter-cb"><span>South Korea</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Singapore" class="hidden filter-cb"><span>Singapore</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Brazil" class="hidden filter-cb"><span>Brazil</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Denmark" class="hidden filter-cb"><span>Denmark</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Norway" class="hidden filter-cb"><span>Norway</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Finland" class="hidden filter-cb"><span>Finland</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Austria" class="hidden filter-cb"><span>Austria</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Ireland" class="hidden filter-cb"><span>Ireland</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="New Zealand" class="hidden filter-cb"><span>New Zealand</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Poland" class="hidden filter-cb"><span>Poland</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Portugal" class="hidden filter-cb"><span>Portugal</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Israel" class="hidden filter-cb"><span>Israel</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Saudi Arabia" class="hidden filter-cb"><span>Saudi Arabia</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="UAE" class="hidden filter-cb"><span>UAE</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="South Africa" class="hidden filter-cb"><span>South Africa</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Turkey" class="hidden filter-cb"><span>Turkey</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Mexico" class="hidden filter-cb"><span>Mexico</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Argentina" class="hidden filter-cb"><span>Argentina</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Chile" class="hidden filter-cb"><span>Chile</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Romania" class="hidden filter-cb"><span>Romania</span></label>
                <label class="filter-chip country-opt"><input type="checkbox" name="countries[]" value="Greece" class="hidden filter-cb"><span>Greece</span></label>
              </div>
            </div>

          </div>
        </div>
      </div>

    </form>
  </section>

  <!-- ═════════════════════════════════════════════════════════════════════ -->
  <!-- 5. REAL-TIME EXTRACTION STATUS                                       -->
  <!-- ═════════════════════════════════════════════════════════════════════ -->
  <div id="statusBox" class="hidden dark-card p-5 space-y-3 border-rose-600/40 shadow-[0_0_25px_rgba(225,29,72,0.15)]">
    <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
      <div class="flex items-center gap-3">
        <svg class="animate-spin w-5 h-5 text-rose-500" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-95" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
        </svg>
        <div>
          <div id="statusText" class="font-display font-bold text-white text-sm">Harvesting scientific papers...</div>
          <div id="statusSubtext" class="text-[11px] text-slate-400 font-mono">Querying live API endpoints</div>
        </div>
      </div>
      <div class="flex items-center gap-5 font-mono text-xs">
        <div>
          <span class="text-slate-400 uppercase text-[9px] block">Progress</span>
          <span id="percentageText" class="font-display text-lg font-bold text-rose-400">0%</span>
        </div>
        <div class="border-l border-slate-800 pl-5">
          <span class="text-slate-400 uppercase text-[9px] block">Verified Contacts</span>
          <span id="liveContactCount" class="font-display text-lg font-bold text-emerald-400">0</span>
        </div>
      </div>
    </div>
    <div class="w-full h-1.5 bg-slate-900 rounded-full overflow-hidden border border-slate-800">
      <div id="progressBar" class="red-progress-bar h-1.5 transition-all duration-300" style="width: 0%"></div>
    </div>
  </div>

  <!-- ═════════════════════════════════════════════════════════════════════ -->
  <!-- 6. 3-COLUMN RESULTS TABLE & EXCEL DOWNLOAD                           -->
  <!-- ═════════════════════════════════════════════════════════════════════ -->
  <div id="resultsCard" class="hidden space-y-4">
    <!-- Results HUD Bar -->
    <div class="dark-card p-4 flex flex-col sm:flex-row items-center justify-between gap-3">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-xl bg-emerald-950/80 border border-emerald-500/40 flex items-center justify-center shadow-md">
          <svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
          </svg>
        </div>
        <div>
          <div class="flex items-center gap-2">
            <span class="font-display text-sm font-bold uppercase tracking-wider text-white">Extracted Verified Contacts</span>
            <span id="countBadge" class="font-mono text-xs font-bold text-emerald-400 bg-emerald-950/80 px-2 py-0.5 rounded-full border border-emerald-600/50">0</span>
          </div>
          <span class="text-[11px] text-slate-400 font-mono">Strict Trio: Paper Title · Author Name · Email ID (100% Complete)</span>
        </div>
      </div>

      <div class="flex items-center gap-2 w-full sm:w-auto">
        <button type="button" id="copyAllEmailsBtn" onclick="copyAllEmails()"
                class="btn-obsidian flex-1 sm:flex-initial justify-center shadow-sm">
          <svg class="w-4 h-4 text-rose-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
          <span>Copy All Emails</span>
        </button>

        <!-- Prominent Excel (.xlsx) Download Button -->
        <a id="downloadLink" href="#" class="btn-excel-green flex-1 sm:flex-initial justify-center">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
          <span>Download Excel (.xlsx)</span>
        </a>
      </div>
    </div>

    <!-- The 3 Columns Table (Paper Title, Author Name, Email ID) -->
    <div class="dark-card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-left text-sm">
          <thead class="bg-carbon-900 border-b border-rose-900/40">
            <tr>
              <th class="px-5 py-3.5 w-12 text-center font-mono text-[11px] text-slate-500 uppercase">#</th>
              <th class="px-5 py-3.5 font-display text-xs uppercase tracking-wider text-rose-400 font-bold">Paper Title</th>
              <th class="px-5 py-3.5 w-64 font-display text-xs uppercase tracking-wider text-rose-400 font-bold">Author Name</th>
              <th class="px-5 py-3.5 w-72 font-display text-xs uppercase tracking-wider text-rose-400 font-bold">Email ID</th>
            </tr>
          </thead>
          <tbody id="tableBody" class="font-sans">
            <!-- Dynamically populated with strict triple-field validation -->
          </tbody>
        </table>
      </div>
    </div>
  </div>

</div>


<!-- ═════════════════════════════════════════════════════════════════════════ -->
<!-- 7. SCRIPT LOGIC (AUTOCOMPLETE, REPO GRID, STRICT VALIDATION)              -->
<!-- ═════════════════════════════════════════════════════════════════════════ -->
<script>
/* ── Comprehensive Biomedical & Research Suggestion Dictionary ── */
const RESEARCH_SUGGESTIONS = [
  { text: "Cancer Immunotherapy and PD-1/PD-L1 Checkpoint Blockade", cat: "Oncology" },
  { text: "CRISPR-Cas9 Base Editing and Gene Therapy Applications", cat: "Genetics" },
  { text: "Alzheimer Disease Amyloid-Beta and Tau Protein Biomarkers", cat: "Neurology" },
  { text: "Cardiovascular Disease and Atherosclerosis Pathogenesis", cat: "Cardiology" },
  { text: "Single-Cell RNA Sequencing in Tumor Microenvironment", cat: "Genomics" },
  { text: "mRNA Vaccine Delivery Mechanisms via Lipid Nanoparticles", cat: "Immunology" },
  { text: "CAR-T Cell Therapy for Hematologic Malignancies", cat: "Oncology" },
  { text: "Deep Learning Neural Networks in Medical Diagnostic Imaging", cat: "AI in Med" },
  { text: "Type 2 Diabetes Mellitus and GLP-1 Receptor Agonists", cat: "Endocrinology" },
  { text: "Antimicrobial Resistance and Novel Antibiotic Targets", cat: "Microbiology" },
  { text: "Parkinson Disease Alpha-Synuclein Neurodegeneration", cat: "Neurology" },
  { text: "Rheumatoid Arthritis and JAK/STAT Inhibitor Mechanisms", cat: "Rheumatology" },
  { text: "Non-Alcoholic Fatty Liver Disease (NAFLD / NASH) Therapies", cat: "Hepatology" },
  { text: "Chronic Kidney Disease and SGLT2 Inhibitor Renoprotection", cat: "Nephrology" },
  { text: "Gut Microbiome Dysbiosis and Systemic Immune Responses", cat: "Microbiology" },
  { text: "Major Depressive Disorder and Ketamine Synaptic Plasticity", cat: "Psychiatry" },
  { text: "Glioblastoma Multiforme Targeted Molecular Therapeutics", cat: "Oncology" },
  { text: "Stem Cell Regeneration and Tissue Engineering Scaffolds", cat: "Regenerative" },
  { text: "SARS-CoV-2 Spike Protein Mutations and Neutralizing Antibodies", cat: "Virology" },
  { text: "Epigenetic DNA Methylation in Human Longevity and Aging", cat: "Genetics" },
  { text: "Asthma Phenotypes and Biologic Targeted Therapies", cat: "Pulmonology" },
  { text: "CRISPR-Cas13 RNA Targeting and Viral Diagnostics", cat: "Biotech" },
  { text: "Metabolic Syndrome and Mitochondrial Dysfunction", cat: "Metabolism" },
  { text: "Liquid Biopsy Circulating Tumor DNA (ctDNA) Monitoring", cat: "Oncology" }
];

const topicInput = document.getElementById('topic');
const suggestionsBox = document.getElementById('suggestionsList');

function filterSuggestions(query) {
  if (!query || query.trim().length < 2) {
    suggestionsBox.style.display = 'none';
    return;
  }
  const q = query.toLowerCase().trim();
  const matched = RESEARCH_SUGGESTIONS.filter(item => item.text.toLowerCase().includes(q));

  if (!matched.length) {
    suggestionsBox.style.display = 'none';
    return;
  }

  suggestionsBox.innerHTML = matched.map(item => {
    const re = new RegExp(`(${q})`, 'gi');
    const highlighted = item.text.replace(re, '<strong class="text-rose-400 font-bold">$1</strong>');
    return `
      <div class="suggestion-item" onclick="selectSuggestion('${item.text.replace(/'/g, "\\'")}')">
        <span class="text-xs text-slate-200 font-medium">${highlighted}</span>
        <span class="suggestion-cat">${item.cat}</span>
      </div>
    `;
  }).join('');

  suggestionsBox.style.display = 'block';
}

function selectSuggestion(val) {
  topicInput.value = val;
  suggestionsBox.style.display = 'none';
  topicInput.focus();
}

function setTopic(val) {
  topicInput.value = val;
  topicInput.focus();
}

topicInput.addEventListener('input', (e) => filterSuggestions(e.target.value));

document.addEventListener('click', (e) => {
  if (!topicInput.contains(e.target) && !suggestionsBox.contains(e.target)) {
    suggestionsBox.style.display = 'none';
  }
});

/* ── 34 Repositories Interactive Grid ── */
function toggleRepoTile(tile){
  const cb = tile.querySelector('.source-cb');
  cb.checked = !cb.checked;
  tile.classList.toggle('active', cb.checked);
  updateActiveBadge();
}

function updateActiveBadge(){
  const count = document.querySelectorAll('.source-cb:checked').length;
  document.getElementById('selectedSourcesBadge').textContent = `${count} Active`;
}

function filterRepoGrid(){
  const q = document.getElementById('repoSearchInput').value.toLowerCase().trim();
  document.querySelectorAll('.repo-tile').forEach(tile => {
    const name = tile.querySelector('.text-xs').textContent.toLowerCase();
    tile.style.display = (!q || name.includes(q)) ? 'flex' : 'none';
  });
}

const PRESETS = {
  all: null,
  biomedical: ['plos', 'pubmed', 'biorxiv', 'medrxiv', 'europepmc', 'elife', 'imedpub', 'peerj', 'f1000', 'frontiers', 'mdpi', 'hindawi', 'biomedcentral', 'pmc'],
  preprints: ['biorxiv', 'medrxiv', 'arxiv', 'preprints', 'osf', 'chemrxiv', 'zenodo', 'ssrn', 'eartharxiv', 'essoar'],
  global: ['openalex', 'semanticscholar', 'crossref', 'sciencedirect', 'doaj', 'base', 'core', 'researchgate', 'springer', 'tandf', 'scielo', 'hal'],
  clear: []
};

function selectPreset(key){
  document.querySelectorAll('.repo-tile').forEach(tile => {
    const cb = tile.querySelector('.source-cb');
    if (key === 'all') {
      cb.checked = true;
    } else if (key === 'clear') {
      cb.checked = false;
    } else {
      cb.checked = (PRESETS[key] || []).includes(cb.value);
    }
    tile.classList.toggle('active', cb.checked);
  });
  updateActiveBadge();
}
updateActiveBadge();

/* ── Country Quick Filter ── */
function filterCountryList() {
  const q = document.getElementById('countrySearch').value.toLowerCase().trim();
  document.querySelectorAll('.country-opt').forEach(opt => {
    const txt = opt.querySelector('span').textContent.toLowerCase();
    opt.style.display = (!q || txt.includes(q)) ? 'flex' : 'none';
  });
}

/* ── Filter Chips ── */
document.querySelectorAll('.filter-chip').forEach(chip => {
  const cb = chip.querySelector('input');
  chip.addEventListener('click', (e) => {
    e.preventDefault();
    cb.checked = !cb.checked;
    chip.classList.toggle('selected', cb.checked);
    updateFilterBadges();
  });
});

function clearFilterGroup(name){
  document.querySelectorAll(`input[name="${name}[]"]`).forEach(cb => {
    cb.checked = false;
    cb.closest('.filter-chip')?.classList.remove('selected');
  });
  updateFilterBadges();
}

function setYears(f, t){
  document.getElementById('year_from').value = f;
  document.getElementById('year_to').value = t;
  updateFilterBadges();
}
function clearYears(){
  document.getElementById('year_from').value = '';
  document.getElementById('year_to').value = '';
  updateFilterBadges();
}

function updateFilterBadges(){
  const bar = document.getElementById('filterPillBadges');
  bar.innerHTML = '';
  const types = [...document.querySelectorAll('input[name="article_types[]"]:checked')].map(c => c.value);
  const countries = [...document.querySelectorAll('input[name="countries[]"]:checked')].map(c => c.value);
  const yf = document.getElementById('year_from').value;
  const yt = document.getElementById('year_to').value;

  if(types.length) bar.insertAdjacentHTML('beforeend', `<span class="px-2 py-0.5 rounded-full text-[10px] font-mono bg-rose-950 text-rose-300 border border-rose-700/50">📄 ${types.join(', ')}</span>`);
  if(yf || yt) bar.insertAdjacentHTML('beforeend', `<span class="px-2 py-0.5 rounded-full text-[10px] font-mono bg-carbon-850 text-slate-300 border border-slate-700">📅 ${yf||'..'}–${yt||'..'}</span>`);
  if(countries.length) bar.insertAdjacentHTML('beforeend', `<span class="px-2 py-0.5 rounded-full text-[10px] font-mono bg-carbon-850 text-slate-300 border border-slate-700">🌍 ${countries.slice(0,3).join(', ')}${countries.length > 3 ? ' +'+(countries.length-3):''}</span>`);
}
document.getElementById('year_from').addEventListener('input', updateFilterBadges);
document.getElementById('year_to').addEventListener('input', updateFilterBadges);

/* ── Accordion ── */
const accordionBtn = document.getElementById('accordionToggleBtn');
const accordionPanel = document.getElementById('filterAccordion');
const accordionArrow = document.getElementById('accordionArrow');
let isAccordionOpen = false;

accordionBtn.addEventListener('click', () => {
  isAccordionOpen = !isAccordionOpen;
  accordionPanel.className = isAccordionOpen ? 'open' : 'closed';
  accordionArrow.style.transform = isAccordionOpen ? 'rotate(180deg)' : '';
});

/* ── Extraction & Results Polling Logic ── */
const form = document.getElementById('extractForm');
const submitBtn = document.getElementById('submitBtn');
const statusBox = document.getElementById('statusBox');
const statusText = document.getElementById('statusText');
const statusSubtext = document.getElementById('statusSubtext');
const progressBar = document.getElementById('progressBar');
const percentageText = document.getElementById('percentageText');
const liveContactCount = document.getElementById('liveContactCount');

const resultsCard = document.getElementById('resultsCard');
const tableBody = document.getElementById('tableBody');
const countBadge = document.getElementById('countBadge');
const downloadLink = document.getElementById('downloadLink');

let currentRecords = [];
let pollTimer = null;

function setBusy(isBusy){
  submitBtn.disabled = isBusy;
  statusBox.classList.toggle('hidden', !isBusy);
}

function showResults(resp){
  if(resp.success && resp.data && resp.data.length > 0){
    // STRICT CLIENT-SIDE FILTER: Drop any row if even ONE field is missing or empty
    const validRows = resp.data.filter(row => {
      const t = (row['Paper Title'] || '').trim();
      const a = (row['Author Name'] || '').trim();
      const e = (row['Email ID'] || '').trim();
      if (!t || t.toLowerCase() === 'untitled paper' || t.length < 3) return false;
      if (!a || a.toLowerCase() === 'unknown' || a.toLowerCase() === 'none' || a.length < 2) return false;
      if (!e || !e.includes('@') || !e.includes('.')) return false;
      return true;
    });

    if (validRows.length === 0) {
      alert("No records with complete Title, Author Name, and Email ID could be extracted for this topic.");
      return;
    }

    currentRecords = validRows;
    countBadge.textContent = validRows.length;
    downloadLink.href = `/download/${resp.download_file}`;
    tableBody.innerHTML = '';

    validRows.forEach((row, i) => {
      const tr = document.createElement('tr');
      tr.className = 'data-row';

      const title = row['Paper Title'].trim();
      const author = row['Author Name'].trim();
      const email = row['Email ID'].trim();
      const initial = author.charAt(0).toUpperCase() || 'A';

      tr.innerHTML = `
        <td class="px-5 py-3.5 text-center font-mono text-xs text-slate-500">${i + 1}</td>
        <td class="px-5 py-3.5 max-w-sm">
          <span class="block line-clamp-2 text-sm text-slate-100 font-semibold leading-snug" title="${title}">
            ${title}
          </span>
        </td>
        <td class="px-5 py-3.5">
          <div class="flex items-center gap-2.5">
            <div class="w-7 h-7 rounded-full flex items-center justify-center font-display font-bold text-xs flex-shrink-0 bg-rose-950 text-rose-300 border border-rose-700/60 shadow-inner">
              ${initial}
            </div>
            <span class="text-sm font-bold text-white tracking-wide">${author}</span>
          </div>
        </td>
        <td class="px-5 py-3.5 font-mono text-xs">
          <div class="flex items-center justify-between gap-2">
            <a href="mailto:${email}" class="text-rose-400 hover:text-white hover:underline flex items-center gap-1.5 transition-colors font-medium">
              <svg class="w-3.5 h-3.5 text-rose-500 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
              </svg>
              <span>${email}</span>
            </a>
            <button type="button" onclick="copySingleEmail('${email}', this)"
                    class="text-slate-400 hover:text-rose-400 p-1 rounded hover:bg-rose-950 transition-colors" title="Copy Email">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
            </button>
          </div>
        </td>
      `;
      tableBody.appendChild(tr);
    });

    resultsCard.classList.remove('hidden');
    resultsCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } else {
    alert(resp.message || resp.error || 'No verified author contacts found for the specified topic.');
  }
}

function copySingleEmail(email, btn){
  navigator.clipboard.writeText(email).then(() => {
    const original = btn.innerHTML;
    btn.innerHTML = `<span class="text-emerald-400 font-bold text-xs">✓</span>`;
    setTimeout(() => { btn.innerHTML = original; }, 1500);
  });
}

function copyAllEmails(){
  if(!currentRecords.length) return;
  const emails = currentRecords.map(r => r['Email ID']).filter(Boolean);
  navigator.clipboard.writeText(emails.join(', ')).then(() => {
    const btn = document.getElementById('copyAllEmailsBtn');
    const orig = btn.innerHTML;
    btn.innerHTML = `<span class="text-emerald-400 font-bold">✓ Copied ${emails.length} Emails</span>`;
    setTimeout(() => { btn.innerHTML = orig; }, 2000);
  });
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  suggestionsBox.style.display = 'none';
  resultsCard.classList.add('hidden');
  tableBody.innerHTML = '';

  statusText.textContent = 'Launching real-time scrapers across selected repositories...';
  statusSubtext.textContent = 'Querying live literature APIs & resolving author metadata';
  progressBar.style.width = '0%';
  percentageText.textContent = '0%';
  liveContactCount.textContent = '0';
  setBusy(true);

  const formData = new FormData(form);

  try {
    const startResp = await fetch('/start-extraction', { method: 'POST', body: formData });
    const startData = await startResp.json();

    if(startData.error){
      setBusy(false);
      alert(startData.error);
      return;
    }

    const taskId = startData.task_id;

    pollTimer = setInterval(async () => {
      try {
        const pollResp = await fetch(`/status/${taskId}`);
        const pollData = await pollResp.json();

        if(pollData.progress) statusText.textContent = pollData.progress;
        const pct = pollData.percentage || 0;
        progressBar.style.width = `${pct}%`;
        percentageText.textContent = `${pct}%`;
        liveContactCount.textContent = pollData.contacts_found || 0;

        if(pollData.status === 'done' || pollData.status === 'error'){
          clearInterval(pollTimer);
          pollTimer = null;
          const finalResp = await fetch(`/result/${taskId}`);
          const finalResult = await finalResp.json();
          setBusy(false);
          showResults(finalResult);
        }
      } catch(err){
        console.error('Polling error:', err);
      }
    }, 2200);

  } catch(err){
    setBusy(false);
    if(pollTimer){ clearInterval(pollTimer); pollTimer = null; }
    alert('Failed to connect to Flask backend.');
  }
});
</script>
</body>
</html>
'''

targets = [
    r"C:\Users\yashw\Email-Scraping\WS2.0\templates\index.html",
    r"C:\Users\yashw\.gemini\antigravity\scratch\Email-Scraping\WS2.0\templates\index.html"
]

for t in targets:
    os.makedirs(os.path.dirname(t), exist_ok=True)
    with open(t, "w", encoding="utf-8") as f:
        f.write(HTML_CONTENT)
    print(f"Successfully generated Red & Black UI template: {t} ({len(HTML_CONTENT)} bytes)")
