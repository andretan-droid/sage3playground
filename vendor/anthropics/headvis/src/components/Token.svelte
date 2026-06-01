<!-- Copyright 2026 Anthropic, PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script>
  import { renderStringVisibly } from '../lib/tokens.js'

  let {
    text,
    color = 'transparent',
    isAssociated = false,
    index = null,
    onHover = null,
    onClick = null,
    activation = null,
    isQuerySelected = false,
    isKeySelected = false,
    attributionType = null,  // 'qk' or 'ov' — determines selection colors
    isCached = false,  // token has cached attribution data
    // Per-role color overrides (optional). When both set, Q and K get DIFFERENT
    // colors + full-word labels instead of shared selectionColor + single-letter.
    queryColor = null,
    keyColor = null,
  } = $props()

  // Selection color based on attribution type
  let selectionColor = $derived(
    attributionType === 'ov' ? '#c2185b' :
    attributionType === 'umap' ? '#2e7d32' : '#1565c0'
  )

  // Effective box-outline color for this token (per-role if override provided)
  let roleColor = $derived(
    isQuerySelected ? (queryColor ?? selectionColor) :
    isKeySelected ? (keyColor ?? selectionColor) :
    selectionColor
  )
  let fullLabels = $derived(queryColor != null && keyColor != null)

  let displayText = $derived(renderStringVisibly(text))
  let isHovered = $state(false)

  function handleClick() {
    if (onClick && index !== null) {
      onClick(index)
    }
  }
</script>

<span
  class="token"
  class:associated={isAssociated}
  class:hovered={isHovered}
  class:query-token={color !== 'transparent'}
  class:selected={isQuerySelected || isKeySelected}
  class:clickable={onClick !== null}
  class:cached={isCached}
  style:background={color !== 'transparent' ? color : (isAssociated ? '#d3d3d3' : 'transparent')}
  style:border-color={(isQuerySelected || isKeySelected) ? roleColor : undefined}
  style:box-shadow={(isQuerySelected || isKeySelected) ? `0 0 0 2px ${roleColor}33` : undefined}
  onmouseenter={() => {
    isHovered = true
    if (onHover && index !== null) onHover(index)
  }}
  onmouseleave={() => {
    // Only clear the local tooltip; the parent container clears hoveredIdx
    // on its own mouseleave so moving between adjacent tokens doesn't flash
    // through the un-hovered reduction.
    isHovered = false
  }}
  onclick={handleClick}
  role={onClick ? 'button' : undefined}
  tabindex={onClick ? 0 : undefined}
>{#if isAssociated}<span class="arrow-indicator"></span>{/if}{#if isQuerySelected}<span class="selection-label" style:background={roleColor}>{fullLabels ? 'QUERY' : 'Q'}</span>{/if}{#if isKeySelected}<span class="selection-label" style:background={roleColor}>{fullLabels ? 'KEY' : 'K'}</span>{/if}{displayText}{#if isCached}<span class="cached-label">cached</span>{/if}{#if isHovered && activation !== null}<span class="tooltip">{index}: {activation.toFixed(4)}</span>{/if}</span>

<style>
  .token {
    display: inline-block;
    padding: 1px 3px 1px 2px;
    margin: 0 0 8px 0;
    border-radius: 3px;
    font-family: monospace;
    font-size: 11px;
    line-height: 1;
    min-height: 1em;
    vertical-align: top;
    white-space: pre-wrap;
    word-break: break-word;
    cursor: default;
    user-select: none;
    position: relative;
    border: 2px solid transparent;
  }

  .token.hovered {
    border-color: black;
  }

  .token.associated {
    border-bottom: 2px solid #666;
  }

  .token.clickable {
    cursor: pointer;
  }

  .token.clickable:hover {
    border-color: #4285f4;
  }

  .token.cached {
    border-bottom: 2px solid currentColor;
    opacity: 1;
  }

  .cached-label {
    position: absolute;
    top: -10px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 7px;
    color: #999;
    white-space: nowrap;
    pointer-events: none;
  }

  .token.selected {
    /* border-color and box-shadow set via inline styles for dynamic coloring */
  }

  .selection-label {
    position: absolute;
    top: -14px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 9px;
    font-weight: 700;
    padding: 1px 4px;
    border-radius: 3px;
    pointer-events: none;
    color: white;
    white-space: nowrap;
  }

  .arrow-indicator {
    position: absolute;
    top: -12px;
    left: 50%;
    transform: translateX(-50%);
    width: 0;
    height: 0;
    border-left: 6px solid transparent;
    border-right: 6px solid transparent;
    border-top: 8px solid #666;
    pointer-events: none;
  }

  .tooltip {
    position: absolute;
    bottom: 100%;
    left: 0;
    margin-bottom: 4px;
    background: #333;
    color: white;
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 12px;
    font-family: monospace;
    white-space: nowrap;
    z-index: 10000;
    pointer-events: none;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  }
</style>
