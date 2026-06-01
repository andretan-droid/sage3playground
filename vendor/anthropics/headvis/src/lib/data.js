// Copyright 2026 Anthropic, PBC
// SPDX-License-Identifier: Apache-2.0
/**
 * Data loading utilities.
 * Loads JSON files from ./data/
 */

const DATA_BASE = './data'

/**
 * Load a JSON data file and return rows with column names.
 */
async function loadJsonData(url) {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to load ${url}: ${response.status}`)
  }
  const rows = await response.json()

  // Get column names from first row
  const columnNames = rows.length > 0 ? Object.keys(rows[0]) : []

  return { rows, columnNames }
}

/**
 * Load the config.json file.
 */
export async function loadConfig() {
  const response = await fetch(`${DATA_BASE}/config.json`)
  if (!response.ok) {
    throw new Error(`Failed to load config: ${response.status}`)
  }
  return response.json()
}

/**
 * Load scatter plot data (all heads metrics).
 */
export async function loadScatterData() {
  return loadJsonData(`${DATA_BASE}/scatter_data.json`)
}

/**
 * Load attention data for a specific head.
 * Returns { rows, columnNames, rawData }
 * - rows: array of sequence objects
 * - columnNames: column names from first row
 * - rawData: full JSON object (or null for legacy array format)
 */
// --- UMAP data loading ---

/** Cache for shared UMAP sequences (same across all heads) */
let _cachedUmapSequences = null

/**
 * Load per-head UMAP JSON data.
 */
export async function loadUmapHeadData(layer, head) {
  const url = `${DATA_BASE}/umap/L${layer}H${head}.json?_t=${Date.now()}`
  const response = await fetch(url, { cache: 'no-store' })
  if (!response.ok) {
    throw new Error(`Failed to load UMAP data from ${url}: ${response.status}`)
  }
  return response.json()
}

/**
 * Load shared UMAP sequences (cached across head switches).
 */
export async function loadUmapSequences() {
  if (_cachedUmapSequences) return _cachedUmapSequences
  const url = `${DATA_BASE}/umap/sequences.json`
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to load UMAP sequences from ${url}: ${response.status}`)
  }
  _cachedUmapSequences = await response.json()
  return _cachedUmapSequences
}

/**
 * Save UMAP cluster labels via the public API endpoint.
 */
export async function saveUmapClusters(layer, head, clusters, serverConfig) {
  if (!serverConfig || !serverConfig.server_url) {
    throw new Error('No server configured for cluster persistence')
  }
  const url = `${serverConfig.server_url}/api/head_vis/public/save_umap_clusters/v0`
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      layer,
      head,
      clusters,
      context: serverConfig.context || {},
    }),
  })
  if (!response.ok) {
    throw new Error(`Failed to save clusters: ${response.status}`)
  }
  return response.json()
}

// --- UMAP projection ---

/**
 * Project a (seq, Q, K) triple onto the UMAP/PCA point cloud via server.
 * Returns one of three response shapes:
 * - { found_in_cloud: true, existing_index }
 * - { found_in_cloud: false, found_in_projected: true, projected_index }
 * - { found_in_cloud: false, found_in_projected: false, point: { seq_idx, top_q, top_k, norm, pca, umap_views, tokens } }
 */
export async function projectToUmap(layer, head, seqIdx, queryPos, keyPos, serverConfig) {
  if (!serverConfig || !serverConfig.server_url) {
    throw new Error('No server configured for UMAP projection')
  }
  const url = `${serverConfig.server_url}/api/head_vis/public/project_to_umap/v0`
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      layer,
      head,
      seq_idx: seqIdx,
      query_pos: queryPos,
      key_pos: keyPos,
      context: serverConfig.context || {},
    }),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `Projection failed: ${response.status}`)
  }
  return response.json()
}

// --- Head data loading ---

export async function loadHeadData(layer, head, filePattern = 'L{layer}H{head}.json') {
  const filename = filePattern
    .replace('{layer}', layer)
    .replace('{head}', head)
  const url = `${DATA_BASE}/heads/${filename}`
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to load ${url}: ${response.status}`)
  }
  const data = await response.json()

  // Handle both old format (array of sequences) and new format (object with sequences key)
  const rows = Array.isArray(data) ? data : (data.sequences || [])
  const columnNames = rows.length > 0 ? Object.keys(rows[0]) : []

  return { rows, columnNames, rawData: Array.isArray(data) ? null : data }
}
