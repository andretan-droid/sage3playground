<!-- Copyright 2026 Anthropic, PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script>
  import { onMount, untrack, tick } from 'svelte'
  import { loadConfig, loadScatterData, loadHeadData, loadUmapHeadData, loadUmapSequences, saveUmapClusters, projectToUmap } from './lib/data.js'
  import { loadServerConfig, serverStore, attributionStore } from './lib/stores.svelte.js'
  import { loadCustomSequences, addCustomSequence, deleteCustomSequence } from './lib/customSequences.js'
  import { loadAttribution } from './lib/attributions.js'
  import { loadManifest } from './lib/attributions.js'
  import { createSparse, findMax } from './lib/sparse.js'

  // --- URL state management ---
  function getUrlParams() {
    return new URLSearchParams(window.location.search)
  }

  function updateUrl(params) {
    const url = new URL(window.location.href)
    for (const [key, value] of Object.entries(params)) {
      if (value === null || value === undefined) {
        url.searchParams.delete(key)
      } else {
        url.searchParams.set(key, String(value))
      }
    }
    history.replaceState(null, '', url)
  }

  // Flag to suppress URL→state sync during initial load
  let initialLoadDone = $state(false)
  // Flag to suppress state→URL sync during URL→state restoration
  let restoringFromUrl = false
  import Sidebar from './components/Sidebar.svelte'
  import SequencesTab from './components/SequencesTab.svelte'
  import MetricsTab from './components/MetricsTab.svelte'
  import HelpTab from './components/HelpTab.svelte'
  import AttributionTab from './components/AttributionTab.svelte'
  import Colorbar from './components/Colorbar.svelte'
  import UmapView from './components/UmapView.svelte'

  // App state
  let config = $state(null)
  let scatterData = $state([])
  let availableMetrics = $state([])
  let headData = $state(null)
  let headRawData = $state(null)
  let customSequences = $state([])
  let loading = $state(true)
  let error = $state(null)

  // UMAP state
  let umapData = $state(null)
  let umapSequences = $state(null)
  let umapLoading = $state(false)
  let umapError = $state(null)
  let umapLoadedKey = $state(null) // "layer,head" of last successful load
  let umapProjectionResult = $state(null)
  let umapProjecting = $state(false)

  // Selection state
  let selectedLayer = $state(0)
  let selectedHead = $state(0)
  let reductionMode = $state('max')
  let selectedInterval = $state(null)
  let transpose = $state(false)
  let isAltPressed = $state(false)
  let activeTab = $state('sequences') // 'sequences', 'metrics', 'qk', 'ov', 'umap', or 'help'
  let sidebarWidth = $state(350)

  // Track active attribution reactively (ensures template re-renders on store change)
  let activeAttr = $derived(attributionStore.active)
  let qkActive = $derived(activeAttr?.type === 'qk')
  let ovActive = $derived(activeAttr?.type === 'ov')

  // UMAP availability: config has umap data and current head is in the umap_heads list
  let umapAvailable = $derived(
    config?.has_umap &&
    config?.umap_heads?.some(([l, h]) => l === selectedLayer && h === selectedHead)
  )

  // Handle when attribution selection completes - switch to appropriate tab
  function handleAttributionComplete(type) {
    activeTab = type  // 'qk' or 'ov'
  }

  // Combined transpose (default + alt key)
  let effectiveTranspose = $derived(transpose !== isAltPressed)

  // Load initial data
  onMount(async () => {
    try {
      // Load config
      config = await loadConfig()

      // Load server config (for attribution API calls)
      await loadServerConfig()

      // Load attribution cache manifest (for cache-aware UI indicators)
      await loadManifest()

      // Load scatter data
      const { rows, columnNames } = await loadScatterData()
      scatterData = rows

      // Detect available metrics (numeric columns besides dimension columns)
      const dimensionCols = [
        config.dimensions?.primary || 'layer',
        config.dimensions?.secondary || 'head'
      ]
      availableMetrics = columnNames.filter(name =>
        !dimensionCols.includes(name) &&
        typeof rows[0]?.[name] === 'number'
      )
      // Add dimension columns to the front
      availableMetrics = [...dimensionCols, ...availableMetrics]

      // Read URL params for initial state
      const urlParams = getUrlParams()
      const urlLayer = urlParams.get('layer')
      const urlHead = urlParams.get('head')
      const urlTab = urlParams.get('tab')
      const urlInterval = urlParams.get('interval')
      const urlReduction = urlParams.get('reduction')
      const urlTranspose = urlParams.get('transpose')

      // Set layer/head from URL or default to first valid head
      restoringFromUrl = true
      if (urlLayer !== null && urlHead !== null && config.heads?.length) {
        const l = parseInt(urlLayer, 10)
        const h = parseInt(urlHead, 10)
        if (config.heads.some(([cl, ch]) => cl === l && ch === h)) {
          selectedLayer = l
          selectedHead = h
        } else if (config.heads.length) {
          selectedLayer = config.heads[0][0]
          selectedHead = config.heads[0][1]
        }
      } else if (config.heads?.length) {
        selectedLayer = config.heads[0][0]
        selectedHead = config.heads[0][1]
      }

      // Restore other easy params
      if (urlInterval !== null) {
        selectedInterval = parseInt(urlInterval, 10)
      } else {
        selectedInterval = config.n_intervals
      }
      if (urlReduction === 'pairwise_max' || urlReduction === 'max') {
        reductionMode = urlReduction
      }
      if (urlTranspose === 'true') {
        transpose = true
      }
      if (urlTab && ['sequences', 'metrics', 'umap', 'help'].includes(urlTab)) {
        activeTab = urlTab
      }

      loading = false
      initialLoadDone = true
      // The head-change effect runs as a microtask after this sync block ends;
      // clearing the flag before tick() means it always sees false and resets
      // activeTab to 'sequences', overwriting the URL's tab.
      await tick()
      restoringFromUrl = false

      // Deferred: restore attribution from URL after head data loads
      const urlAttrType = urlParams.get('attr')
      const urlSeq = urlParams.get('seq')
      const urlQpos = urlParams.get('qpos')
      const urlKpos = urlParams.get('kpos')
      if (urlAttrType && urlSeq !== null && urlQpos !== null && urlKpos !== null) {
        // Wait for head data to load, then trigger attribution
        const isCustom = urlSeq.startsWith('c')
        const waitForHeadData = () => {
          const check = setInterval(() => {
            const scanReady = headData && headData.length > 0
            // Custom sequences load in the same async as headData; waiting for
            // scan alone can race if the fetch order flips.
            const customReady = !isCustom || customSequences.length > 0
            if (scanReady && customReady) {
              clearInterval(check)
              const qpos = parseInt(urlQpos, 10)
              const kpos = parseInt(urlKpos, 10)
              const match = s => String(s.sequence_id) === String(urlSeq)
              const seq = headData.find(match) || customSequences.find(match)
              if (seq) {
                attributionStore.setAttribution(seq, urlAttrType, qpos, kpos)
                activeTab = urlAttrType
              }
            }
          }, 100)
          // Give up after 10s
          setTimeout(() => clearInterval(check), 10000)
        }
        waitForHeadData()
      }
    } catch (e) {
      error = e.message
      loading = false
    }
  })

  // Sync state → URL whenever key state changes
  $effect(() => {
    // Read all deps above untrack
    const l = selectedLayer
    const h = selectedHead
    const tab = activeTab
    const interval = selectedInterval
    const red = reductionMode
    const trans = transpose
    const attr = activeAttr

    untrack(() => {
      if (!initialLoadDone || restoringFromUrl) return
      const params = {
        layer: l,
        head: h,
        tab: tab !== 'sequences' ? tab : null,
        interval: interval,
        reduction: red !== 'max' ? red : null,
        transpose: trans ? 'true' : null,
      }
      // Attribution params
      if (attr) {
        params.attr = attr.type
        params.seq = attr.sequence?.sequence_id
        params.qpos = attr.queryPos
        params.kpos = attr.keyPos
      } else {
        params.attr = null
        params.seq = null
        params.qpos = null
        params.kpos = null
      }
      updateUrl(params)
    })
  })

  // Load head data when selection changes
  $effect(() => {
    if (config && selectedLayer !== null && selectedHead !== null) {
      // Clear stale data immediately so UI shows loading state
      headData = null
      headRawData = null
      customSequences = []
      umapData = null
      umapLoadedKey = null
      umapError = null
      attributionStore.clearAttribution()
      if (!restoringFromUrl) activeTab = 'sequences'
      loadHeadDataForSelection()
    }
  })

  // Lazy-load UMAP data when tab is activated
  $effect(() => {
    if (activeTab === 'umap' && umapAvailable) {
      const key = `${selectedLayer},${selectedHead}`
      if (umapLoadedKey !== key) {
        loadUmapForSelection(selectedLayer, selectedHead)
      }
    }
  })


  async function loadHeadDataForSelection() {
    // Load custom sequences (static fetch, no server needed)
    customSequences = await loadCustomSequences(selectedLayer, selectedHead)
    try {
      const filePattern = config?.head_data_pattern || 'L{layer}H{head}.json'
      const result = await loadHeadData(selectedLayer, selectedHead, filePattern)
      headData = result.rows
      headRawData = result.rawData

    } catch (e) {
      console.error('Failed to load head data:', e)
      headData = []
      headRawData = null
    }
  }

  async function loadUmapForSelection(layer, head) {
    const key = `${layer},${head}`
    umapLoading = true
    umapError = null
    try {
      const [headUmap, seqs] = await Promise.all([
        loadUmapHeadData(layer, head),
        loadUmapSequences(),
      ])
      umapData = headUmap
      umapSequences = seqs
      umapLoadedKey = key
    } catch (e) {
      console.error('Failed to load UMAP data:', e)
      umapError = e.message
    } finally {
      umapLoading = false
    }
  }

  async function handleUmapSaveClusters(clusters) {
    await saveUmapClusters(selectedLayer, selectedHead, clusters, serverStore.config)
  }

  async function handleUmapProjection(sequence, queryPos, keyPos) {
    const projLayer = selectedLayer
    const projHead = selectedHead
    umapProjecting = true
    try {
      const result = await projectToUmap(projLayer, projHead, sequence.sequence_id, queryPos, keyPos, serverStore.config)
      // Staleness guard: discard if head changed during the projection
      if (selectedLayer !== projLayer || selectedHead !== projHead) return
      // Ensure UMAP data is loaded before switching tab
      if (!umapData) {
        await loadUmapForSelection(projLayer, projHead)
      }
      umapProjectionResult = result
      activeTab = 'umap'
    } catch (e) {
      if (selectedLayer !== projLayer || selectedHead !== projHead) return
      console.error('UMAP projection failed:', e)
      alert(`Projection failed: ${e.message}`)
    } finally {
      umapProjecting = false
    }
  }

  function handleProjectionHandled() {
    umapProjectionResult = null
  }

  function handleScatterSelect(layer, head) {
    selectedLayer = layer
    selectedHead = head
  }

  async function handleAddCustomSequence(text) {
    const newSeq = await addCustomSequence(selectedLayer, selectedHead, text)
    // Update local state optimistically (server write may not be immediately visible)
    customSequences = [...customSequences.filter(s => s.sequence_id !== newSeq.sequence_id), newSeq]
  }

  async function handleDeleteCustomSequence(sequenceId) {
    await deleteCustomSequence(selectedLayer, selectedHead, sequenceId)
    customSequences = customSequences.filter(s => s.sequence_id !== sequenceId)
  }

  // Keyboard navigation
  function handleKeydown(event) {
    // Ignore if typing in input fields
    if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA' || event.target.tagName === 'SELECT') {
      return
    }

    const key = event.key
    const shift = event.shiftKey

    // Alt key for temporary transpose
    if (event.key === 'Alt') {
      isAltPressed = true
      return
    }

    switch (key.toLowerCase()) {
      case 't':
        // Toggle default transpose
        transpose = !transpose
        break

      case 'r':
        // Toggle reduction mode between max and pairwise_max
        reductionMode = reductionMode === 'max' ? 'pairwise_max' : 'max'
        break

      case 'h':
      case 'l':
        // Navigate through valid heads (h/l forward, H/L backward)
        if (config?.heads?.length) {
          const headsList = config.heads
          const curIdx = headsList.findIndex(([l, h]) => l === selectedLayer && h === selectedHead)
          const delta = shift ? -1 : 1
          const nextIdx = (curIdx + delta + headsList.length) % headsList.length
          selectedLayer = headsList[nextIdx][0]
          selectedHead = headsList[nextIdx][1]
        }
        break

      case '[':
        // Next interval: 1→2→...→10→custom→1→...
        if (config && config.n_intervals) {
          if (selectedInterval === -1) {
            selectedInterval = 1
          } else if (selectedInterval >= config.n_intervals) {
            selectedInterval = -1
          } else {
            selectedInterval = selectedInterval + 1
          }
        }
        break

      case ']':
        // Previous interval: custom→10→9→...→1→custom→...
        if (config && config.n_intervals) {
          if (selectedInterval === -1) {
            selectedInterval = config.n_intervals
          } else if (selectedInterval <= 1) {
            selectedInterval = -1
          } else {
            selectedInterval = selectedInterval - 1
          }
        }
        break

      case 'm':
        // Toggle metrics tab
        activeTab = activeTab === 'sequences' ? 'metrics' : 'sequences'
        break

      case '?':
        // Switch to help tab
        activeTab = 'help'
        break
    }
  }

  function handleKeyup(event) {
    if (event.key === 'Alt') {
      isAltPressed = false
    }
  }
</script>

<svelte:head>
  <title>HeadVis</title>
</svelte:head>

<svelte:window onkeydown={handleKeydown} onkeyup={handleKeyup} />

<div class="app">
  {#if loading}
    <div class="loading">Loading...</div>
  {:else if error}
    <div class="error">Error: {error}</div>
  {:else}
    <Sidebar
      {config}
      {scatterData}
      {availableMetrics}
      bind:selectedLayer
      bind:selectedHead
      onScatterSelect={handleScatterSelect}
      bind:width={sidebarWidth}
    />

    <div class="main">
      <div class="panel-header">
        <div class="tab-bar">
          <button
            class="tab-btn"
            class:active={activeTab === 'sequences'}
            onclick={() => activeTab = 'sequences'}
          >Sequences</button>
          <button
            class="tab-btn"
            class:active={activeTab === 'metrics'}
            onclick={() => activeTab = 'metrics'}
          >Metrics</button>
          <button
            class="tab-btn"
            class:active={activeTab === 'umap'}
            class:inactive={!umapAvailable}
            onclick={() => { if (umapAvailable) activeTab = 'umap' }}
            disabled={!umapAvailable}
          >UMAP</button>
          <button
            class="tab-btn"
            class:active={activeTab === 'qk'}
            class:inactive={!qkActive}
            onclick={() => { if (qkActive) activeTab = 'qk' }}
            disabled={!qkActive}
          >QK</button>
          <button
            class="tab-btn"
            class:active={activeTab === 'ov'}
            class:inactive={!ovActive}
            onclick={() => { if (ovActive) activeTab = 'ov' }}
            disabled={!ovActive}
          >OV</button>
          <button
            class="tab-btn"
            class:active={activeTab === 'help'}
            onclick={() => activeTab = 'help'}
          >Help</button>
        </div>
        <div class="header-right">
          <Colorbar />
        </div>
      </div>

      <div class="tab-content">
        {#if activeTab === 'sequences'}
          {#if headData}
            <SequencesTab
              sequences={headData}
              {customSequences}
              bind:reductionMode
              transpose={effectiveTranspose}
              bind:selectedInterval
              nIntervals={config?.n_intervals ?? 10}
              layer={selectedLayer}
              head={selectedHead}
              onAttributionComplete={handleAttributionComplete}
              onAddCustomSequence={handleAddCustomSequence}
              onDeleteCustomSequence={handleDeleteCustomSequence}
              {umapAvailable}
              onUmapProjection={handleUmapProjection}
            />
          {:else}
            <div class="loading-sequences">Loading sequences...</div>
          {/if}
        {:else if activeTab === 'metrics'}
          <MetricsTab
            headMetrics={scatterData.find(d => d.layer === selectedLayer && d.head === selectedHead)}
            rawData={headRawData}
            {config}
          />
        {:else if activeTab === 'qk' && activeAttr}
          <AttributionTab
            type="qk"
            layer={selectedLayer}
            head={selectedHead}
            sequence={activeAttr.sequence}
            queryPos={activeAttr.queryPos}
            keyPos={activeAttr.keyPos}
            {reductionMode}
            transpose={effectiveTranspose}
            nIntervals={config?.n_intervals ?? 10}
            onClose={() => { attributionStore.clearAttribution(); activeTab = 'sequences' }}
          />
        {:else if activeTab === 'ov' && activeAttr}
          <AttributionTab
            type="ov"
            layer={selectedLayer}
            head={selectedHead}
            sequence={activeAttr.sequence}
            queryPos={activeAttr.queryPos}
            keyPos={activeAttr.keyPos}
            {reductionMode}
            transpose={effectiveTranspose}
            nIntervals={config?.n_intervals ?? 10}
            onClose={() => { attributionStore.clearAttribution(); activeTab = 'sequences' }}
          />
        {:else if activeTab === 'umap'}
          {#if umapLoading}
            <div class="loading-sequences">Loading UMAP data...</div>
          {:else if umapError}
            <div class="loading-sequences" style="color: #c00;">UMAP error: {umapError}</div>
          {:else if umapData && umapSequences}
            <UmapView
              umapData={umapData}
              sequences={umapSequences}
              layer={selectedLayer}
              head={selectedHead}
              onSaveClusters={serverStore.config ? handleUmapSaveClusters : null}
              projectionResult={umapProjectionResult}
              onProjectionHandled={handleProjectionHandled}
            />
          {:else}
            <div class="loading-sequences">No UMAP data available for this head.</div>
          {/if}
        {:else if activeTab === 'help'}
          <HelpTab metricDescriptions={config?.metric_descriptions} />
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  :global(body) {
    margin: 0;
    font-family: system-ui, -apple-system, sans-serif;
  }

  .app {
    display: flex;
    height: 100vh;
    overflow: hidden;
  }

  .loading, .error {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    font-size: 18px;
  }

  .error {
    color: #c00;
  }

  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .panel-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    padding: 12px 16px 0 16px;
    background: #f5f5f5;
    border-bottom: 1px solid #ddd;
    flex-shrink: 0;
  }

  .header-right {
    padding-bottom: 8px;
  }

  .tab-bar {
    display: flex;
    gap: 4px;
  }

  .tab-btn {
    padding: 8px 16px;
    font-size: 13px;
    border: 1px solid #ccc;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    background: #e8e8e8;
    color: #666;
    cursor: pointer;
    transition: all 0.15s;
    position: relative;
    top: 1px;
  }

  .tab-btn:hover {
    background: #f0f0f0;
    color: #333;
  }

  .tab-btn.active {
    background: white;
    color: #333;
    border-color: #ddd;
    font-weight: 500;
    z-index: 1;
  }

  .tab-btn.inactive {
    color: #999;
    cursor: not-allowed;
  }

  .tab-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 0;
  }

  .loading-sequences {
    padding: 40px;
    text-align: center;
    color: #666;
  }
</style>
