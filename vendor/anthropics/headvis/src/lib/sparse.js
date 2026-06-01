// Copyright 2026 Anthropic, PBC
// SPDX-License-Identifier: Apache-2.0
/**
 * Sparse attention utilities.
 * Works with COO (Coordinate) format attention data.
 *
 * TODO(portability): getRowMax, getColMax, and findMax skip position 0,
 * assuming it's a special token to exclude from attention stats.
 * This won't be correct for all models — consider making it configurable
 * via a flag in config.json (e.g. "skip_position_0": true).
 */

/**
 * Create a sparse tensor object from COO index/value arrays.
 *
 * @param {number[]} indices - Flat COO indices
 * @param {number[]} values - COO values
 * @param {number} seqLen - Sequence length (attention is seqLen x seqLen)
 * @returns {Object} Sparse tensor object
 */
export function createSparse(indices, values, seqLen) {
  return {
    sparse_indices: indices,
    sparse_values: values,
    shape: [seqLen, seqLen]
  }
}

/**
 * Expand COO sparse format to dense 2D array.
 *
 * @param {Object} sparse - {sparse_indices, sparse_values, shape}
 * @returns {Float32Array[]} Array of Float32Arrays (one per row)
 */
export function expandToDense(sparse) {
  const { sparse_indices, sparse_values, shape } = sparse
  const [rows, cols] = shape
  const result = []

  for (let r = 0; r < rows; r++) {
    result.push(new Float32Array(cols))
  }

  for (let i = 0; i < sparse_indices.length; i++) {
    const flatIdx = Number(sparse_indices[i])
    const r = Math.floor(flatIdx / cols)
    const c = flatIdx % cols
    result[r][c] = Number(sparse_values[i])
  }

  return result
}

/**
 * Get a specific row from sparse format as dense array.
 *
 * @param {Object} sparse - COO sparse data
 * @param {number} row - Row index (query token)
 * @returns {Float32Array} Attention weights for this query
 */
export function getRow(sparse, row) {
  const { sparse_indices, sparse_values, shape } = sparse
  const cols = shape[1]
  const result = new Float32Array(cols)
  const rowStart = row * cols
  const rowEnd = (row + 1) * cols

  for (let i = 0; i < sparse_indices.length; i++) {
    const flatIdx = Number(sparse_indices[i])
    if (flatIdx >= rowStart && flatIdx < rowEnd) {
      result[flatIdx - rowStart] = Number(sparse_values[i])
    }
  }
  return result
}

/**
 * Get a specific column from sparse format as dense array.
 *
 * @param {Object} sparse - COO sparse data
 * @param {number} col - Column index (key token)
 * @returns {Float32Array} Attention to this key from all queries
 */
export function getCol(sparse, col) {
  const { sparse_indices, sparse_values, shape } = sparse
  const [rows, cols] = shape
  const result = new Float32Array(rows)

  for (let i = 0; i < sparse_indices.length; i++) {
    const flatIdx = Number(sparse_indices[i])
    const c = flatIdx % cols
    if (c === col) {
      const r = Math.floor(flatIdx / cols)
      result[r] = Number(sparse_values[i])
    }
  }
  return result
}

/**
 * Get max value in each row (max attention per query).
 * Skips position 0 (see TODO at top of file).
 *
 * @param {Object} sparse - COO sparse data
 * @returns {Float32Array} Max attention for each query token
 */
export function getRowMax(sparse) {
  const { sparse_indices, sparse_values, shape } = sparse
  const [rows, cols] = shape
  const rowMax = new Float32Array(rows)

  for (let i = 0; i < sparse_indices.length; i++) {
    const flatIdx = Number(sparse_indices[i])
    const r = Math.floor(flatIdx / cols)
    const c = flatIdx % cols
    // Skip position 0 for both row and column
    if (r === 0 || c === 0) continue
    const val = Number(sparse_values[i])
    if (val > rowMax[r]) {
      rowMax[r] = val
    }
  }
  return rowMax
}

/**
 * Get max value in each column (max attention to each key).
 * Skips position 0 (see TODO at top of file).
 *
 * @param {Object} sparse - COO sparse data
 * @returns {Float32Array} Max attention for each key token
 */
export function getColMax(sparse) {
  const { sparse_indices, sparse_values, shape } = sparse
  const [, cols] = shape
  const colMax = new Float32Array(cols)

  for (let i = 0; i < sparse_indices.length; i++) {
    const flatIdx = Number(sparse_indices[i])
    const r = Math.floor(flatIdx / cols)
    const c = flatIdx % cols
    // Skip position 0 for both row and column
    if (r === 0 || c === 0) continue
    const val = Number(sparse_values[i])
    if (val > colMax[c]) {
      colMax[c] = val
    }
  }
  return colMax
}

/**
 * Find global maximum and its position.
 * Skips position 0 (see TODO at top of file).
 *
 * @param {Object} sparse - COO sparse data
 * @returns {{value: number, row: number, col: number} | null}
 */
export function findMax(sparse) {
  const { sparse_indices, sparse_values, shape } = sparse
  const cols = shape[1]

  let maxValue = -Infinity
  let maxRow = -1
  let maxCol = -1

  for (let i = 0; i < sparse_indices.length; i++) {
    const flatIdx = Number(sparse_indices[i])
    const r = Math.floor(flatIdx / cols)
    const c = flatIdx % cols
    // Skip position 0 for both row and column
    if (r === 0 || c === 0) continue
    const val = Number(sparse_values[i])
    if (val > maxValue) {
      maxValue = val
      maxRow = r
      maxCol = c
    }
  }

  if (maxRow === -1 || maxValue <= 0) return null
  return { value: maxValue, row: maxRow, col: maxCol }
}
