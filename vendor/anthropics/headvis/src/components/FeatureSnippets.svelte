<!-- Copyright 2026 Anthropic, PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script>
  import { sanitizeToken, renderStringVisiblyWithNewline } from '../lib/tokens.js'
  import { getAttentionColor } from '../lib/colors.js'

  // Check if a raw token contains a newline character
  function tokenHasNewline(rawToken) {
    return typeof rawToken === 'string' && rawToken.includes('\n')
  }

  let {
    snippets = [],
    nIntervals = 10,
    hideIntervalHeader = false,
  } = $props()

  // Compute max activation across all snippets for normalization
  let maxActivation = $derived.by(() => {
    let max = 0.001
    for (const snippet of snippets) {
      if (snippet.activations) {
        for (const a of snippet.activations) {
          if (a > max) max = a
        }
      }
    }
    return max
  })

  // Group snippets by interval (highest first)
  let groupedSnippets = $derived.by(() => {
    const groups = new Map()
    for (const s of snippets) {
      const interval = s.interval ?? 0
      if (!groups.has(interval)) {
        groups.set(interval, { items: [], maxAct: 0 })
      }
      const group = groups.get(interval)
      group.items.push(s)
      if (s.activations) {
        for (const a of s.activations) {
          if (a > group.maxAct) group.maxAct = a
        }
      }
    }
    // Sort by interval descending (highest = strongest activations first)
    return Array.from(groups.entries())
      .sort((a, b) => b[0] - a[0])
      .map(([interval, { items, maxAct }]) => ({ interval, items, maxAct }))
  })

  // Get background color for activation (same scale as attention pattern)
  function getTokenColor(activation) {
    if (!activation || activation <= 0) return 'transparent'
    return getAttentionColor(activation, maxActivation)
  }

  // Find index of max activation in a snippet
  function getMaxIdx(activations) {
    if (!activations || activations.length === 0) return -1
    let maxIdx = 0
    let maxVal = activations[0]
    for (let i = 1; i < activations.length; i++) {
      if (activations[i] > maxVal) {
        maxVal = activations[i]
        maxIdx = i
      }
    }
    return maxIdx
  }

  // Svelte action: translate snippet content so max-activating token is centered
  function centerMaxToken(node, activations) {
    let currentActs = activations

    function recenter() {
      const maxIdx = getMaxIdx(currentActs)
      if (maxIdx < 0) return
      const inner = node.querySelector('.snippet-inner')
      if (!inner) return
      const tokens = inner.querySelectorAll('.token')
      if (tokens[maxIdx]) {
        const token = tokens[maxIdx]
        const containerWidth = node.clientWidth
        if (containerWidth === 0) return  // not laid out yet
        const tokenLeft = token.offsetLeft
        const tokenWidth = token.offsetWidth
        const offset = tokenLeft - containerWidth / 2 + tokenWidth / 2
        inner.style.transform = `translateX(${-offset}px)`
      }
    }

    // Double-rAF to ensure tokens are painted before measuring
    requestAnimationFrame(() => requestAnimationFrame(recenter))

    // Recenter on container resize
    const ro = new ResizeObserver(recenter)
    ro.observe(node)

    return {
      update(acts) {
        currentActs = acts
        requestAnimationFrame(recenter)
      },
      destroy() {
        ro.disconnect()
      }
    }
  }

  function formatMaxAct(val) {
    if (val >= 100) return val.toFixed(1)
    if (val >= 10) return val.toFixed(2)
    return val.toFixed(3)
  }

  // --- Tooltip (hover, portaled to body) ---
  let tooltipSnippet = $state(null)
  let tooltipFadeTimer = null
  let tooltipEl = null

  function ensureTooltipEl() {
    if (tooltipEl) return tooltipEl
    tooltipEl = document.createElement('div')
    tooltipEl.className = 'snippet-tooltip-portal'
    tooltipEl.style.cssText = 'position:fixed;width:500px;max-height:300px;overflow-y:auto;background:white;border:1px solid lightgray;box-shadow:0 2px 10px rgba(0,0,0,0.1);z-index:10000;padding:8px;pointer-events:all;display:none;font-family:monospace;font-size:10px;line-height:1.4;white-space:pre-wrap;color:#444;'
    tooltipEl.addEventListener('mouseenter', cancelHideTooltip)
    tooltipEl.addEventListener('mouseleave', startHideTooltip)
    document.body.appendChild(tooltipEl)
    return tooltipEl
  }

  function appendTokenNodes(parent, snippet) {
    for (let i = 0; i < snippet.tokens.length; i++) {
      const rawToken = snippet.tokens[i]
      const span = document.createElement('span')
      span.textContent = sanitizeToken(rawToken)
      const act = snippet.activations?.[i]
      span.style.backgroundColor = (act && act > 0) ? getAttentionColor(act, maxActivation) : 'transparent'
      span.style.borderRadius = '3px'
      span.style.padding = '1px 0'
      span.style.whiteSpace = 'pre'
      span.className = 'snippet-tooltip-token'
      parent.appendChild(span)
      if (tokenHasNewline(rawToken)) {
        parent.appendChild(document.createElement('br'))
      }
    }
  }

  function renderTooltipContent(snippet) {
    const el = ensureTooltipEl()
    el.replaceChildren()
    appendTokenNodes(el, snippet)

    // Scroll to max-activating token
    requestAnimationFrame(() => {
      const maxIdx = getMaxIdx(snippet.activations)
      if (maxIdx < 0) return
      const tokens = el.querySelectorAll('.snippet-tooltip-token')
      if (tokens[maxIdx]) tokens[maxIdx].scrollIntoView({ block: 'center' })
    })
  }

  function showTooltip(event, snippet) {
    if (tooltipFadeTimer) { clearTimeout(tooltipFadeTimer); tooltipFadeTimer = null }
    tooltipSnippet = snippet
    renderTooltipContent(snippet)

    // Position right next to the button, preferring right side unless it would be cut off
    const el = ensureTooltipEl()
    const rect = event.currentTarget.getBoundingClientRect()
    const tooltipWidth = 500
    const spaceOnRight = window.innerWidth - rect.right - 16
    const left = spaceOnRight >= tooltipWidth
      ? rect.right + 8
      : rect.left - tooltipWidth - 16
    const top = Math.max(10, Math.min(rect.top - 20, window.innerHeight - 320))
    el.style.left = `${left}px`
    el.style.top = `${top}px`
    el.style.display = 'block'
  }

  function startHideTooltip() {
    if (tooltipFadeTimer) clearTimeout(tooltipFadeTimer)
    tooltipFadeTimer = setTimeout(() => {
      tooltipSnippet = null
      if (tooltipEl) tooltipEl.style.display = 'none'
    }, 250)
  }

  function cancelHideTooltip() {
    if (tooltipFadeTimer) { clearTimeout(tooltipFadeTimer); tooltipFadeTimer = null }
  }

  // --- Modal (click) ---
  let modalSnippet = $state(null)

  function openModal(snippet) {
    modalSnippet = snippet
  }

  function closeModal() {
    modalSnippet = null
  }

  function handleModalKeydown(event) {
    if (event.key === 'Escape') closeModal()
  }
</script>

<svelte:window onkeydown={handleModalKeydown} />

<div class="snippets-container">
  {#if snippets.length === 0}
    <div class="no-snippets">No example activations available</div>
  {:else}
    {#each groupedSnippets as group (group.interval)}
      <div class="interval-group">
        {#if !hideIntervalHeader}
        <div class="interval-header">
          <span class="interval-label">{group.interval}/{nIntervals}</span>
          <span class="interval-max">(max {formatMaxAct(group.maxAct)})</span>
        </div>
        {/if}
        {#each group.items as snippet, idx (idx)}
          <div class="snippet-row">
            <button
              class="expand-icon"
              class:tooltipped={tooltipSnippet === snippet}
              aria-label="Show full example"
              onmouseenter={(e) => showTooltip(e, snippet)}
              onmouseleave={startHideTooltip}
              onclick={() => openModal(snippet)}
            >&#x29C9;</button>
            <div
              class="snippet"
              use:centerMaxToken={snippet.activations}
            >
              <span class="snippet-inner">
                {#each snippet.tokens as token, tidx (tidx)}
                  <span
                    class="token"
                    style:background-color={getTokenColor(snippet.activations?.[tidx])}
                  >{sanitizeToken(token)}</span>
                {/each}
              </span>
            </div>
          </div>
        {/each}
      </div>
    {/each}
  {/if}
</div>

<!-- Modal (click) -->
{#if modalSnippet}
  <div class="modal-backdrop" onclick={closeModal}>
    <div class="modal-content" onclick={(e) => e.stopPropagation()}>
      <div class="modal-header">
        <span class="modal-title">Full Context</span>
        <button class="modal-close" onclick={closeModal}>&times;</button>
      </div>
      <div class="modal-body">
        {#each modalSnippet.tokens as token, tidx (tidx)}
          <span
            class="modal-token"
            style:background-color={getTokenColor(modalSnippet.activations?.[tidx])}
          >{sanitizeToken(token)}</span>{#if tokenHasNewline(token)}<br>{/if}
        {/each}
      </div>
    </div>
  </div>
{/if}

<style>
  .snippets-container {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .no-snippets {
    color: #999;
    font-size: 12px;
    font-style: italic;
    padding: 12px;
    text-align: center;
  }

  .interval-group {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .interval-header {
    display: flex;
    align-items: baseline;
    gap: 6px;
    padding: 4px 4px 2px 4px;
    margin-top: 4px;
  }

  .interval-label {
    font-size: 10px;
    font-weight: 700;
    color: #555;
    font-family: monospace;
  }

  .interval-max {
    font-size: 9px;
    color: #888;
    font-family: monospace;
  }

  .snippet-row {
    display: flex;
    align-items: stretch;
  }

  .snippet-row + .snippet-row {
    border-top: 1px solid #e8e8e8;
  }

  .expand-icon {
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    color: #ccc;
    font-size: 10px;
    width: 14px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.1s;
  }

  .expand-icon:hover {
    color: #999;
    background: #f0f0f0;
  }

  .expand-icon.tooltipped {
    background-color: #f0f0f0;
    color: #999;
  }

  .snippet {
    font-family: monospace;
    font-size: 10px;
    line-height: 1.5;
    padding: 2px 4px;
    background: white;
    overflow: hidden;
    flex: 1;
    min-width: 0;
  }

  .snippet-inner {
    display: inline-block;
    white-space: nowrap;
  }

  .token {
    border-radius: 3px;
    padding: 1px 0;
    white-space: pre;
  }

  /* --- Modal --- */
  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    z-index: 10001;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .modal-content {
    background: white;
    border-radius: 8px;
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);
    width: 80vw;
    max-width: 900px;
    display: flex;
    flex-direction: column;
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid #e0e0e0;
    flex-shrink: 0;
  }

  .modal-title {
    font-size: 14px;
    font-weight: 600;
    color: #333;
  }

  .modal-close {
    background: none;
    border: none;
    font-size: 22px;
    color: #666;
    cursor: pointer;
    line-height: 1;
    padding: 0 4px;
  }

  .modal-close:hover {
    color: #333;
  }

  .modal-body {
    padding: 16px;
    overflow-y: auto;
    font-family: monospace;
    font-size: 12px;
    line-height: 1.6;
    white-space: pre-wrap;
    color: #333;
    /* 12px font * 1.6 line-height = 19.2px per line */
    min-height: calc(19.2px * 3);
    max-height: calc(19.2px * 10);
  }

  .modal-token {
    border-radius: 3px;
    padding: 1px 0;
    white-space: pre;
  }
</style>
