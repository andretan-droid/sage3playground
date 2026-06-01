// Copyright 2026 Anthropic, PBC
// SPDX-License-Identifier: Apache-2.0
/**
 * Build a map from point index to the list of all indices sharing the same
 * coordinates. Used to randomly pick among overlapping points on hover/click,
 * so each interaction reveals a different sequence.
 *
 * @param {{ d0: ArrayLike<number>, d1: ArrayLike<number>, d2?: ArrayLike<number> }} coords
 * @returns {number[][] | null} — overlapGroups[i] = array of all indices at point i's location, or null if no overlaps
 */
export function buildOverlapGroups(coords) {
  const n = coords.d0.length
  if (n === 0) return null

  const axes = coords.d2 ? [coords.d0, coords.d1, coords.d2] : [coords.d0, coords.d1]
  const nAxes = axes.length

  const groups = new Map()
  let hasDuplicates = false
  for (let i = 0; i < n; i++) {
    let key = ''
    for (let a = 0; a < nAxes; a++) {
      if (a > 0) key += ','
      key += axes[a][i]
    }
    const group = groups.get(key)
    if (group) {
      group.push(i)
      hasDuplicates = true
    } else {
      groups.set(key, [i])
    }
  }

  if (!hasDuplicates) return null

  // Build per-index lookup: overlapGroups[i] points to the shared group array
  const overlapGroups = new Array(n)
  for (const group of groups.values()) {
    for (const i of group) {
      overlapGroups[i] = group
    }
  }
  return overlapGroups
}

/**
 * Given a point index from Plotly, return a random member of its overlap group.
 * If there are no overlaps (groups is null) or the point is unique, returns idx unchanged.
 */
export function pickFromOverlap(groups, idx) {
  if (!groups) return idx
  const group = groups[idx]
  if (!group || group.length < 2) return idx
  return group[Math.floor(Math.random() * group.length)]
}
