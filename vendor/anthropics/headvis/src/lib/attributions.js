// Copyright 2026 Anthropic, PBC
// SPDX-License-Identifier: Apache-2.0
/**
 * Attribution loading utilities.
 * Loads attribution data from local cache or remote server.
 */

const DATA_BASE = './data'

/**
 * Generate cache key for an attribution file.
 * @param {'qk' | 'ov'} type - Attribution type
 * @param {number} layer - Layer index
 * @param {number} head - Head index
 * @param {number|string} seqIdx - Sequence index
 * @param {number} qpos - Query position
 * @param {number} kpos - Key position
 * @returns {string} Cache file path relative to data/attributions/
 */
export function getAttributionCacheKey(type, layer, head, seqIdx, qpos, kpos) {
  return `${type}/L${layer}H${head}S${seqIdx}Q${qpos}K${kpos}.json`
}

/**
 * Try to load attribution from local cache.
 * @param {string} cacheKey - Cache key from getAttributionCacheKey
 * @returns {Promise<Object|null>} Attribution data or null if not cached
 */
async function tryLoadCached(cacheKey) {
  try {
    const url = `${DATA_BASE}/attributions/${cacheKey}`
    const response = await fetch(url)
    if (!response.ok) {
      return null
    }
    const data = await response.json()
    return data
  } catch (e) {
    return null
  }
}

/**
 * Fetch attribution from server.
 * @param {string} serverUrl - Base server URL
 * @param {'qk' | 'ov'} type - Attribution type
 * @param {Object} params - Request parameters
 * @param {Object} context - Server context
 * @returns {Promise<Object>} Attribution data
 */
async function fetchFromServer(serverUrl, type, params, context) {
  const endpoint = type === 'qk'
    ? '/api/head_vis/public/qk_attributions/v0'
    : '/api/head_vis/public/ov_attributions/v0'

  const url = `${serverUrl}${endpoint}`
  const body = {
    // Layer/head pair to compute attributions for
    layer: params.layer,
    head: params.head,
    seq_idx: params.seqIdx,
    query_pos: params.qpos,
    key_pos: params.kpos,
    // Server context
    context: context || {}
  }

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body)
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `Server error: ${response.status}`)
  }

  const data = await response.json()
  return data
}

/**
 * Load attribution data from cache or server.
 * @param {'qk' | 'ov'} type - Attribution type
 * @param {Object} params - Parameters
 * @param {number} params.layer - Layer index
 * @param {number} params.head - Head index
 * @param {number|string} params.seqIdx - Sequence index
 * @param {number} params.qpos - Query position
 * @param {number} params.kpos - Key position
 * @param {Object} serverConfig - Server configuration {server_url, context}
 * @returns {Promise<{data: Object|null, source: 'cache'|'server'|'none'}>}
 */
export async function loadAttribution(type, params, serverConfig) {
  const cacheKey = getAttributionCacheKey(
    type,
    params.layer,
    params.head,
    params.seqIdx,
    params.qpos,
    params.kpos
  )

  // 1. Try cache first
  const cached = await tryLoadCached(cacheKey)
  if (cached) {
    return { data: cached, source: 'cache' }
  }

  // 2. Try server if configured
  const serverUrl = serverConfig?.server_url
  if (serverUrl) {
    try {
      const data = await fetchFromServer(serverUrl, type, params, serverConfig?.context)
      return { data, source: 'server' }
    } catch (e) {
      console.error('Failed to load from server:', e)
      throw e
    }
  }

  // 3. No data available
  return { data: null, source: 'none' }
}

/**
 * Save attribution data to local storage for offline viewing.
 * Note: This doesn't write to the actual cache files (which require build time),
 * but stores in sessionStorage for the current session.
 * @param {'qk' | 'ov'} type - Attribution type
 * @param {Object} params - Parameters used to generate the key
 * @param {Object} data - Attribution data to save
 */
export function saveAttributionToSession(type, params, data) {
  const cacheKey = getAttributionCacheKey(
    type,
    params.layer,
    params.head,
    params.seqIdx,
    params.qpos,
    params.kpos
  )
  try {
    sessionStorage.setItem(`attribution:${cacheKey}`, JSON.stringify(data))
  } catch (e) {
    console.warn('Failed to save attribution to session:', e)
  }
}

// Attribution manifest — tracks which sequences have cached attributions
let manifest = null

/**
 * Load attribution manifest from cache.
 * Maps "L{layer}H{head}S{seqId}" -> { qk: [[q,k],...], ov: [[q,k],...] }
 * @returns {Promise<Object>} The manifest (empty object if not found)
 */
export async function loadManifest() {
  if (manifest !== null) return manifest
  try {
    const response = await fetch(`${DATA_BASE}/attributions/manifest.json`)
    if (!response.ok) {
      manifest = {}
      return manifest
    }
    manifest = await response.json()
  } catch (e) {
    manifest = {}
  }
  return manifest
}

/**
 * Update local manifest after a new attribution is computed.
 * @param {'qk'|'ov'} type
 * @param {number} layer
 * @param {number} head
 * @param {number|string} seqIdx
 * @param {number} qpos
 * @param {number} kpos
 */
export function updateManifestLocally(type, layer, head, seqIdx, qpos, kpos) {
  if (!manifest) manifest = {}
  const key = `L${layer}H${head}S${seqIdx}`
  if (!manifest[key]) manifest[key] = { qk: [], ov: [] }
  const pair = [qpos, kpos]
  if (!manifest[key][type].some(p => p[0] === qpos && p[1] === kpos)) {
    manifest[key][type].push(pair)
  }
}

/**
 * Check if a sequence has any cached attributions.
 * @param {number} layer
 * @param {number} head
 * @param {number|string} seqIdx
 * @returns {{ qk: boolean, ov: boolean }}
 */
export function getSequenceCacheStatus(layer, head, seqIdx) {
  if (!manifest) return { qk: false, ov: false }
  const key = `L${layer}H${head}S${seqIdx}`
  const entry = manifest[key]
  if (!entry) return { qk: false, ov: false }
  return { qk: entry.qk.length > 0, ov: entry.ov.length > 0 }
}

/**
 * Get cached query positions for a sequence+type.
 * @param {number} layer
 * @param {number} head
 * @param {number|string} seqIdx
 * @param {'qk'|'ov'} type
 * @returns {Set<number>} Set of query positions with cached attributions
 */
export function getCachedQueryPositions(layer, head, seqIdx, type) {
  if (!manifest) return new Set()
  const key = `L${layer}H${head}S${seqIdx}`
  const entry = manifest[key]
  if (!entry || !entry[type]) return new Set()
  return new Set(entry[type].map(p => p[0]))
}

/**
 * Get cached key positions for a specific query position.
 * @param {number} layer
 * @param {number} head
 * @param {number|string} seqIdx
 * @param {'qk'|'ov'} type
 * @param {number} queryPos
 * @returns {Set<number>} Set of key positions with cached attributions
 */
export function getCachedKeyPositions(layer, head, seqIdx, type, queryPos) {
  if (!manifest) return new Set()
  const key = `L${layer}H${head}S${seqIdx}`
  const entry = manifest[key]
  if (!entry || !entry[type]) return new Set()
  return new Set(entry[type].filter(p => p[0] === queryPos).map(p => p[1]))
}
