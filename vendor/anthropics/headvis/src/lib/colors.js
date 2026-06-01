// Copyright 2026 Anthropic, PBC
// SPDX-License-Identifier: Apache-2.0
/**
 * Color scale utilities.
 */

import * as d3 from 'd3'

/**
 * Custom interpolator that goes from white to orange.
 * Unlike d3.interpolateOranges which starts at a light orange (#fff5eb),
 * this starts at pure white (#ffffff) for better zero-value visibility.
 *
 * Uses a precomputed lookup table for performance.
 */
const WHITE_ORANGE_LUT_SIZE = 256
const WHITE_ORANGE_LUT = (() => {
  const lut = new Array(WHITE_ORANGE_LUT_SIZE)
  const blendThreshold = 0.15
  const blendTargetColor = d3.interpolateOranges(blendThreshold)
  const whiteToThreshold = d3.interpolateRgb('#ffffff', blendTargetColor)

  for (let i = 0; i < WHITE_ORANGE_LUT_SIZE; i++) {
    const t = i / (WHITE_ORANGE_LUT_SIZE - 1)
    if (t < blendThreshold) {
      lut[i] = whiteToThreshold(t / blendThreshold)
    } else {
      lut[i] = d3.interpolateOranges(t)
    }
  }
  return lut
})()

/**
 * @param {number} t - Value between 0 and 1
 * @returns {string} RGB color string
 */
function interpolateWhiteToOrange(t) {
  const idx = Math.round(t * (WHITE_ORANGE_LUT_SIZE - 1))
  return WHITE_ORANGE_LUT[Math.max(0, Math.min(WHITE_ORANGE_LUT_SIZE - 1, idx))]
}

/**
 * Create a color scale for attention values.
 * Uses an orange sequential scale (white to orange).
 *
 * @param {number} maxValue - Maximum value in the data
 * @returns {Function} D3 color scale function
 */
export function createAttentionColorScale(maxValue = 1) {
  // Add 40% headroom so the top of the range isn't saturated
  return d3.scaleSequential()
    .domain([0, maxValue * 1.4])
    .interpolator(interpolateWhiteToOrange)
    .clamp(true)
}

/**
 * Get color for an attention value.
 *
 * @param {number} value - Attention value
 * @param {number} maxValue - Maximum value for normalization
 * @returns {string} CSS color string
 */
export function getAttentionColor(value, maxValue = 1) {
  if (value <= 0) return 'transparent'
  const scale = createAttentionColorScale(maxValue)
  return scale(value)
}

/**
 * Create a color scale for scatter plot metrics.
 *
 * @param {number[]} domain - [min, max] values
 * @returns {Function} D3 color scale function
 */
export function createMetricColorScale(domain) {
  return d3.scaleSequential()
    .domain(domain)
    .interpolator(d3.interpolateViridis)
}
