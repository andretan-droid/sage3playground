// Copyright 2026 Anthropic, PBC
// SPDX-License-Identifier: Apache-2.0
/**
 * Attention reduction utilities.
 *
 * Reduction modes:
 * - "max": For each token, show max attention it gives (as query) or receives (as key).
 *         Supports hover: when hoveredIdx is set, shows the attention pattern for that token.
 * - "pairwise_max": Highlight the single (query, key) pair with highest attention
 *
 * TODO(portability): computeHover skips position 0 and zeroes activations[0],
 * assuming it's a special token. See sparse.js for the same assumption.
 */

import { getRow, getCol, getRowMax, getColMax, findMax } from './sparse.js'

/**
 * Compute token activations based on reduction mode.
 *
 * @param {Object} sparse - Sparse attention tensor
 * @param {string} mode - Reduction mode: "max" or "pairwise_max"
 * @param {number|null} hoveredIdx - Index of hovered token (for dynamic hover in max mode)
 * @param {boolean} transpose - If true, show attention TO tokens (columns) instead of FROM (rows)
 * @returns {Object} { activations: Float32Array, pairInfo: {queryIdx, keyIdx} | null }
 */
export function computeReduction(sparse, mode, hoveredIdx = null, transpose = false) {
  const seqLen = sparse.shape[0]

  switch (mode) {
    case 'pairwise_max':
      return computePairwiseMax(sparse, seqLen)

    case 'max':
    default:
      // In max mode, if a token is hovered, show that token's attention pattern
      if (hoveredIdx !== null && hoveredIdx > 0 && hoveredIdx < seqLen) {
        return computeHover(sparse, seqLen, hoveredIdx, transpose)
      }
      return computeMax(sparse, seqLen, transpose)
  }
}

/**
 * Max reduction: show max attention per token.
 */
function computeMax(sparse, seqLen, transpose) {
  const activations = transpose ? getColMax(sparse) : getRowMax(sparse)
  return { activations, pairInfo: null }
}

/**
 * Pairwise max: highlight the single (query, key) pair with highest attention.
 * Returns activations where only the query and key tokens are colored.
 */
function computePairwiseMax(sparse, seqLen) {
  const activations = new Float32Array(seqLen)
  const maxPair = findMax(sparse)

  if (maxPair) {
    // Color the query token with the max attention value
    activations[maxPair.row] = maxPair.value
    // Mark the key token as "associated" (will get special styling)
  }

  return {
    activations,
    pairInfo: maxPair ? { queryIdx: maxPair.row, keyIdx: maxPair.col, maxValue: maxPair.value } : null
  }
}

/**
 * Hover mode: show attention for the hovered token.
 * If transpose=false: show what the hovered query attends to (row)
 * If transpose=true: show what attends to the hovered key (column)
 * Skips position 0 (see TODO at top of file).
 */
function computeHover(sparse, seqLen, hoveredIdx, transpose) {
  // Skip position 0 entirely
  if (hoveredIdx === null || hoveredIdx < 0 || hoveredIdx >= seqLen || hoveredIdx === 0) {
    return { activations: new Float32Array(seqLen), pairInfo: null }
  }

  const activations = transpose ? getCol(sparse, hoveredIdx) : getRow(sparse, hoveredIdx)
  // Zero out position 0 in the result
  activations[0] = 0
  return { activations, pairInfo: null }
}
