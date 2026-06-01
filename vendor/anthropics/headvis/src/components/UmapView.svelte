<!-- Copyright 2026 Anthropic, PBC -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
<script>
  import * as Plotly from 'plotly.js-dist-min'
  import { tick, untrack } from 'svelte'
  import { sanitizeToken } from '$lib/tokens.js'
  import { buildOverlapGroups, pickFromOverlap } from '$lib/jitter.js'

  let {
    umapData,
    sequences,
    layer,
    head,
    onSaveClusters = null,
    compact = false,
    initialPanels = null,
    initialColorMode = null,
    initialProjection = null,
    // Per-panel camera override — lets the view open at a chosen angle.
    // Shape: {Q: {eye:{x,y,z}, up:{x,y,z}, center:{x,y,z}}, K: {...}, ...}
    // Any panels not specified fall back to the auto-computed tight camera.
    initialCamera = null,
    // Show 3D axes with labels (makes it clear the view is 3D).
    // Labels default to PC1/PC2/PC3; pass [x, y, z] names to override.
    showAxes = false,
    // Single-hue coloring — all points use the same dark-brown hue, varying
    // only in lightness. Less visually noisy than Viridis when the clusters
    // themselves are the focus.
    uniformColor = false,
    projectionResult = null,
    onProjectionHandled = null,
  } = $props()

  const BASE_KEYS = ['R', 'O', 'V', 'Q', 'K']
  let ALL_KEYS = $derived(BASE_KEYS.filter(k => currentEmbeddings?.[k] != null))

  let plotDivs = $state({O: null, V: null, Q: null, K: null, R: null})
  let textBox = $state(null)
  let colorbarCanvas = $state(null)

  // Multi-view state
  let currentViewIdx = $state(0)
  let views = $derived(umapData?.views || null)

  // Projection mode: 'umap' or 'pca'
  let projMode = $state(initialProjection || 'umap')
  let hasPca = $derived(umapData?.pca != null)

  // Current embeddings depend on projection mode and view index
  let currentEmbeddings = $derived.by(() => {
    if (projMode === 'pca' && umapData?.pca) return umapData.pca
    if (views) return views[currentViewIdx]?.embeddings || null
    return umapData?.embeddings || null
  })

  // Detect 3D data (d0/d1/d2) vs legacy 2D (x/y)
  let is3D = $derived.by(() => {
    if (!currentEmbeddings) return false
    const first = currentEmbeddings.O || currentEmbeddings.Q
    return first && 'd2' in first
  })

  // Panel visibility
  let panelVisible = $state(initialPanels || {O: true, V: false, Q: true, K: true})
  let sidebarCollapsed = $state(false)
  let visibleKeys = $derived(ALL_KEYS.filter(k => panelVisible[k]))

  // Cluster state
  let clusters = $state([])
  let labelingMode = $state(false)
  let colorMode = $state(initialColorMode || 'rank')
  let savingClusters = $state(false)

  const CLUSTER_COLORS = [
    '#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
    '#42d4f4', '#f032e6', '#bfef45', '#fabed4', '#469990',
    '#dcbeff', '#9A6324', '#800000', '#aaffc3', '#808000',
  ]

  // Custom modebar button icon for "back to 3D" (isometric cube)
  const CUBE_ICON = {
    width: 1000, height: 1000,
    path: 'M500 100L150 300v400l350 200 350-200V300L500 100zm0 75l275 157v315L500 805 225 647V332L500 175zM500 475L225 332v315l275 158V475z',
  }

  // Projected points state
  let projectedPointsStartIdx = 0
  let projectedTokensMap = new Map()  // cloudIndex → string[] (decoded tokens)
  let selectedPointIdx = -1  // -1 = no selection
  let prevUmapDataRef = null  // track object identity to skip deep-mutation re-fires

  // Camera persistence for 3D plots
  const defaultCam = {eye: {x: 0, y: 0, z: 2.5}, up: {x: 0, y: 1, z: 0}, center: {x: 0, y: 0, z: 0}}

  // Compute the tightest camera eye that still shows all points.
  // Plotly 3D auto-aspect normalizes data so the max range axis ≈ 1 unit.
  // Camera looks along -z with FOV = pi/4 (half_fov = pi/8).
  function computeTightCameraEye(coords) {
    if (!coords?.d2) return {...defaultCam.eye}
    const n = coords.d0.length
    if (n === 0) return {...defaultCam.eye}
    let minX = Infinity, maxX = -Infinity
    let minY = Infinity, maxY = -Infinity
    let minZ = Infinity, maxZ = -Infinity
    for (let i = 0; i < n; i++) {
      const x = coords.d0[i], y = coords.d1[i], z = coords.d2[i]
      if (x < minX) minX = x; if (x > maxX) maxX = x
      if (y < minY) minY = y; if (y > maxY) maxY = y
      if (z < minZ) minZ = z; if (z > maxZ) maxZ = z
    }
    const rx = maxX - minX || 1, ry = maxY - minY || 1, rz = maxZ - minZ || 1
    const maxRange = Math.max(rx, ry, rz)
    // Normalized half-extents after Plotly auto-aspect scaling
    const hx = (rx / maxRange) * 0.5, hy = (ry / maxRange) * 0.5, hz = (rz / maxRange) * 0.5
    // Distance = transverse_half / tan(half_fov) + z_half
    const dist = Math.max(hx, hy) / Math.tan(Math.PI / 8) + hz
    return {x: 0, y: 0, z: dist * 1.15}
  }

  let lastCameras = {O: {...defaultCam}, V: {...defaultCam}, Q: {...defaultCam}, K: {...defaultCam}, R: {...defaultCam}}
  let projectedCoords = {}
  let lastSceneInfos = {}
  let overlapGroups = null // overlap groups for the current embedding, or null if no overlaps

  // Initialize from props — only on new data identity, not deep mutations
  $effect(() => {
    const data = umapData
    untrack(() => {
      if (!data) return
      if (data === prevUmapDataRef) return  // skip deep-mutation re-fires
      prevUmapDataRef = data
      currentViewIdx = 0
      const defaultMode = initialProjection || (data.views?.length ? 'umap' : data.pca ? 'pca' : 'umap')
      projMode = defaultMode
      labelingMode = false
      projectedCoords = {}
      overlapGroups = null
      projectedPointsStartIdx = 0
      projectedTokensMap = new Map()
      selectedPointIdx = -1

      // Merge persisted projected points into the cloud arrays FIRST,
      // so the identity lookup below includes projected points.
      mergeProjectedPoints()

      // Compute tight camera for each panel from initial embeddings
      const initEmb = (() => {
        if (defaultMode === 'pca' && data.pca) return data.pca
        if (data.views) return data.views[0]?.embeddings || null
        return data.embeddings || null
      })()
      if (initEmb) {
        for (const key of BASE_KEYS) {
          const coords = getCoords(initEmb[key])
          const auto = {eye: computeTightCameraEye(coords), up: {...defaultCam.up}, center: {...defaultCam.center}}
          // initialCamera override (per-panel, any missing fields fall back to auto)
          const override = initialCamera?.[key]
          lastCameras[key] = override
            ? { eye: override.eye ?? auto.eye, up: override.up ?? auto.up, center: override.center ?? auto.center }
            : auto
        }
      }

      // Build identity lookup: "seq_idx,top_q,top_k" → positional index
      const idMap = new Map()
      for (let i = 0; i < data.seq_idx.length; i++) {
        idMap.set(`${data.seq_idx[i]},${data.top_q[i]},${data.top_k[i]}`, i)
      }

      // Load clusters — resolve identity tuples to positional indices
      clusters = (data.clusters || []).map(c => {
        const points = c.points || []
        const point_indices = points
          .map(([s, q, k]) => idMap.get(`${s},${q},${k}`))
          .filter(i => i !== undefined)
        return { name: c.name, color: c.color || null, points, point_indices }
      })

      if (initialColorMode) {
        colorMode = initialColorMode
      } else if (clusters.length > 0) {
        colorMode = 'clusters'
      }

      tick().then(() => {
        requestAnimationFrame(() => renderPlots())
      })
    })
  })

  // --- Merge persisted projected points into cloud arrays ---

  function mergeProjectedPoints() {
    if (umapData._originalCloudLength == null) {
      umapData._originalCloudLength = umapData.seq_idx.length
    }
    const origLen = umapData._originalCloudLength

    // Truncate arrays to original length (strip any previously appended projected points)
    umapData.seq_idx.length = origLen
    umapData.top_q.length = origLen
    umapData.top_k.length = origLen
    umapData.norms.length = origLen
    for (const view of (umapData.views || [])) {
      const emb = view?.embeddings
      if (!emb) continue
      for (const key of ALL_KEYS) {
        if (emb[key]) {
          emb[key].d0.length = origLen
          emb[key].d1.length = origLen
          if (emb[key].d2) emb[key].d2.length = origLen
        }
      }
    }
    if (umapData.pca) {
      for (const key of ALL_KEYS) {
        if (umapData.pca[key]) {
          umapData.pca[key].d0.length = origLen
          umapData.pca[key].d1.length = origLen
          if (umapData.pca[key].d2) umapData.pca[key].d2.length = origLen
        }
      }
    }

    const pts = umapData?.projected_points
    projectedPointsStartIdx = origLen
    projectedTokensMap = new Map()
    if (!pts || pts.length === 0) return

    // Append all projected points
    for (let pi = 0; pi < pts.length; pi++) {
      const pp = pts[pi]
      umapData.seq_idx.push(pp.seq_idx)
      umapData.top_q.push(pp.top_q)
      umapData.top_k.push(pp.top_k)
      umapData.norms.push(pp.norm ?? 0)

      // UMAP view embeddings
      for (let vi = 0; vi < (umapData.views || []).length; vi++) {
        const viewEmb = umapData.views[vi]?.embeddings
        const ppView = pp.umap_views?.[vi]
        if (!viewEmb || !ppView) continue
        for (const key of ALL_KEYS) {
          if (viewEmb[key] && ppView[key]) {
            viewEmb[key].d0.push(ppView[key].d0)
            viewEmb[key].d1.push(ppView[key].d1)
            viewEmb[key].d2.push(ppView[key].d2)
          }
        }
      }
      // PCA embeddings
      if (umapData.pca && pp.pca) {
        for (const key of ALL_KEYS) {
          if (umapData.pca[key] && pp.pca[key]) {
            umapData.pca[key].d0.push(pp.pca[key].d0)
            umapData.pca[key].d1.push(pp.pca[key].d1)
            umapData.pca[key].d2.push(pp.pca[key].d2)
          }
        }
      }

      // Rebuild token map
      if (pp.tokens) {
        projectedTokensMap.set(origLen + pi, pp.tokens)
      }
    }
  }

  // --- Handle incoming projection result ---

  $effect(() => {
    const result = projectionResult
    untrack(() => {
      if (!result || !umapData) return
      if (result.found_in_cloud && result.existing_index != null) {
        selectPoint(result.existing_index)
      } else if (result.found_in_projected && result.projected_index != null) {
        selectPoint(projectedPointsStartIdx + result.projected_index)
      } else if (result.point) {
        if (!umapData.projected_points) umapData.projected_points = []
        umapData.projected_points.push(result.point)
        mergeProjectedPoints()
        renderPlots()
        selectPoint(projectedPointsStartIdx + umapData.projected_points.length - 1)
      }
      if (onProjectionHandled) onProjectionHandled()
    })
  })

  // --- Point selection (click-to-highlight) ---

  function selectPoint(idx) {
    selectedPointIdx = idx
    applySelection()
    showHoverText(idx)
  }

  function deselectPoint() {
    if (selectedPointIdx < 0) return
    selectedPointIdx = -1

    // Restore cloud opacity and reset trace 1 to default hover marker
    const divs = visibleKeys.map(k => plotDivs[k]).filter(Boolean)
    divs.forEach(div => {
      if (!div?.data || div.data.length < 2) return
      Plotly.restyle(div, {'marker.opacity': 1, 'marker.size': 2}, [0])
    })
    visibleKeys.forEach((key, ki) => {
      const div = divs[ki]
      if (!div?.data || div.data.length < 2) return
      const coords = getCoords(currentEmbeddings?.[key])
      if (!coords) return
      Plotly.restyle(div, {
        x: [[coords.d0[0]]], y: [[coords.d1[0]]], z: [[coords.d2[0]]],
        'marker.size': 5, 'marker.color': 'rgba(0, 0, 0, 0.8)',
        'marker.symbol': 'circle-open', 'marker.line.width': 2,
      }, [1])
    })
    _lastHighlightIdx = -1
  }

  function applySelection() {
    if (selectedPointIdx < 0 || !currentEmbeddings) return
    const idx = selectedPointIdx
    const divs = visibleKeys.map(k => plotDivs[k]).filter(Boolean)
    divs.forEach(div => {
      if (!div?.data || div.data.length < 2) return
      Plotly.restyle(div, {'marker.opacity': 0.15, 'marker.size': 2}, [0])
    })
    visibleKeys.forEach((key, ki) => {
      const div = divs[ki]
      if (!div?.data || div.data.length < 2) return
      const coords = getCoords(currentEmbeddings?.[key])
      if (!coords) return
      Plotly.restyle(div, {
        x: [[coords.d0[idx]]], y: [[coords.d1[idx]]], z: [[coords.d2[idx]]],
        'marker.size': 6, 'marker.color': 'rgba(255, 100, 0, 0.9)',
        'marker.symbol': 'circle', 'marker.line.width': 2, 'marker.line.color': 'rgba(0, 0, 0, 0.8)',
      }, [1])
    })
  }

  // --- Norm ranks (computed once per data load) ---

  function computeNormRanks() {
    if (!umapData) return null
    const norms = umapData.norms
    const N = norms.length
    const normRanks = new Float64Array(N)
    const sortedIndices = Array.from({length: N}, (_, i) => i)
    sortedIndices.sort((a, b) => norms[a] - norms[b])
    for (let rank = 0; rank < N; rank++) {
      normRanks[sortedIndices[rank]] = rank / Math.max(N - 1, 1)
    }
    return normRanks
  }

  function getPointColors(normRanks) {
    if (colorMode === 'clusters' && clusters.length > 0) {
      const N = normRanks.length
      const colors = new Array(N)
      for (let i = 0; i < N; i++) colors[i] = '#cccccc'
      clusters.forEach((c, ci) => {
        const col = CLUSTER_COLORS[ci % CLUSTER_COLORS.length]
        const indices = c.point_indices || []
        indices.forEach(idx => { colors[idx] = col })
      })
      return { color: colors, colorscale: null, cmin: null, cmax: null }
    }
    if (uniformColor) {
      // Single dark-brown hue, lightness varies with rank. A rainbow
      // colorscale distracts when the absence of structure is the point.
      return {
        color: Array.from(normRanks),
        colorscale: [[0, 'rgba(99,54,54,0.25)'], [1, 'rgba(99,54,54,0.9)']],
        cmin: 0, cmax: 1,
      }
    }
    return { color: Array.from(normRanks), colorscale: 'Viridis', cmin: 0, cmax: 1 }
  }

  // --- 3D → 2D perspective projection ---

  function projectToCamera(data, cam, sceneInfo) {
    const ex = cam.eye.x - cam.center.x, ey = cam.eye.y - cam.center.y, ez = cam.eye.z - cam.center.z
    const fLen = Math.sqrt(ex*ex + ey*ey + ez*ez)
    const fx = -ex/fLen, fy = -ey/fLen, fz = -ez/fLen
    const ux = cam.up.x, uy = cam.up.y, uz = cam.up.z
    let rx = fy*uz - fz*uy, ry = fz*ux - fx*uz, rz = fx*uy - fy*ux
    const rLen = Math.sqrt(rx*rx + ry*ry + rz*rz)
    rx /= rLen; ry /= rLen; rz /= rLen
    let tux = ry*fz - rz*fy, tuy = rz*fx - rx*fz, tuz = rx*fy - ry*fx
    const n = data.d0.length
    const px = new Array(n), py = new Array(n)
    const xMid = (sceneInfo.xRange[0] + sceneInfo.xRange[1]) / 2
    const yMid = (sceneInfo.yRange[0] + sceneInfo.yRange[1]) / 2
    const zMid = (sceneInfo.zRange[0] + sceneInfo.zRange[1]) / 2
    const xScale = sceneInfo.aspect.x / (sceneInfo.xRange[1] - sceneInfo.xRange[0])
    const yScale = sceneInfo.aspect.y / (sceneInfo.yRange[1] - sceneInfo.yRange[0])
    const zScale = sceneInfo.aspect.z / (sceneInfo.zRange[1] - sceneInfo.zRange[0])
    for (let i = 0; i < n; i++) {
      const sx = (data.d0[i] - xMid) * xScale
      const sy = (data.d1[i] - yMid) * yScale
      const sz = (data.d2[i] - zMid) * zScale
      const vx = sx - cam.eye.x, vy = sy - cam.eye.y, vz = sz - cam.eye.z
      const depth = vx*fx + vy*fy + vz*fz
      px[i] = (vx*rx + vy*ry + vz*rz) * fLen / depth
      py[i] = (vx*tux + vy*tuy + vz*tuz) * fLen / depth
    }
    return {x: px, y: py, eyeDist: fLen}
  }

  // --- Get coord accessors (backward compat: d0/d1/d2 or x/y) ---

  function getCoords(embForKey) {
    if (!embForKey) return null
    if ('d0' in embForKey) return embForKey
    return {d0: embForKey.x, d1: embForKey.y}
  }

  // --- Render plots ---

  function renderPlots() {
    if (!umapData || !currentEmbeddings) return

    // Persist current camera state before purging plots
    if (is3D && !labelingMode) {
      visibleKeys.forEach(key => {
        const div = plotDivs[key]
        if (div?._fullLayout?.scene?._scene) {
          try {
            const cam = div._fullLayout.scene._scene.getCamera()
            lastCameras[key] = {eye: {...cam.eye}, up: {...cam.up}, center: {...cam.center}}
          } catch(e) { /* plot not yet initialized */ }
        }
      })
    }

    _lastHighlightIdx = -1

    const normRanks = computeNormRanks()
    if (!normRanks) return
    const mc = getPointColors(normRanks)

    const divs = []

    if (labelingMode && is3D) {
      // 2D projected mode for lasso selection
      visibleKeys.forEach(key => {
        const div = plotDivs[key]
        if (!div) return
        Plotly.purge(div)

        const proj = projectedCoords[key]
        if (!proj) return

        const halfRange = proj.eyeDist * Math.tan(Math.PI / 8)

        Plotly.newPlot(div, [{
          x: proj.x, y: proj.y,
          mode: 'markers', type: 'scattergl',
          marker: {
            size: 4,
            color: mc.color,
            colorscale: mc.colorscale,
            cmin: mc.cmin, cmax: mc.cmax,
            showscale: false,
          },
          hoverinfo: 'none',
          selected: {marker: {opacity: 1, size: 5, color: 'rgba(255, 100, 0, 0.9)'}},
          unselected: {marker: {opacity: 0.3, size: 3}},
        }], {
          title: {text: key, font: {size: 18, color: '#555'}, y: 0.98},
          xaxis: {zeroline: false, showgrid: false, showticklabels: false, range: [-halfRange, halfRange]},
          yaxis: {zeroline: false, showgrid: false, showticklabels: false, scaleanchor: 'x', range: [-halfRange, halfRange]},
          margin: {l: 5, r: 5, t: 30, b: 5},
          hovermode: 'closest',
          dragmode: 'lasso',
        }, {
          responsive: true,
          ...(!compact && {
            modeBarButtonsToAdd: [{
              name: 'back-to-3d',
              title: 'Back to 3D',
              icon: CUBE_ICON,
              click: () => onLabelingModeChange(false),
            }],
          }),
        })
        divs.push(div)
      })
    } else if (is3D) {
      // 3D scatter mode
      visibleKeys.forEach(key => {
        const div = plotDivs[key]
        if (!div) return
        Plotly.purge(div)

        const coords = getCoords(currentEmbeddings[key])
        if (!coords) return

        // Axis lines from origin — only when showAxes is enabled.
        // Compute axis length from the data range so they're visible but not dominant.
        const axisTraces = []
        if (showAxes) {
          const maxRange = Math.max(
            Math.max(...coords.d0.map(Math.abs)),
            Math.max(...coords.d1.map(Math.abs)),
            Math.max(...coords.d2.map(Math.abs)),
          )
          const axLen = maxRange * 0.7
          const axColor = '#888780'
          const axNames = Array.isArray(showAxes) ? showAxes : ['PC1', 'PC2', 'PC3']
          // X axis
          axisTraces.push({
            x: [0, axLen], y: [0, 0], z: [0, 0],
            mode: 'lines+text', type: 'scatter3d',
            line: {color: axColor, width: 2},
            text: ['', axNames[0]], textposition: 'top center',
            textfont: {size: 10, color: axColor},
            hoverinfo: 'none', showlegend: false,
          })
          // Y axis
          axisTraces.push({
            x: [0, 0], y: [0, axLen], z: [0, 0],
            mode: 'lines+text', type: 'scatter3d',
            line: {color: axColor, width: 2},
            text: ['', axNames[1]], textposition: 'top center',
            textfont: {size: 10, color: axColor},
            hoverinfo: 'none', showlegend: false,
          })
          // Z axis
          axisTraces.push({
            x: [0, 0], y: [0, 0], z: [0, axLen],
            mode: 'lines+text', type: 'scatter3d',
            line: {color: axColor, width: 2},
            text: ['', axNames[2]], textposition: 'top center',
            textfont: {size: 10, color: axColor},
            hoverinfo: 'none', showlegend: false,
          })
        }

        Plotly.newPlot(div, [{
          x: coords.d0, y: coords.d1, z: coords.d2,
          mode: 'markers', type: 'scatter3d',
          marker: {
            size: 2,
            color: mc.color,
            colorscale: mc.colorscale,
            cmin: mc.cmin, cmax: mc.cmax,
            showscale: false,
          },
          hoverinfo: 'none',
          showlegend: false,
        }, {
          x: [coords.d0[0]], y: [coords.d1[0]], z: [coords.d2[0]],
          mode: 'markers', type: 'scatter3d',
          marker: {size: 5, color: 'rgba(0, 0, 0, 0.8)', symbol: 'circle-open', line: {width: 2}},
          hoverinfo: 'none',
          showlegend: false,
        }, ...axisTraces], {
          title: {text: key, font: {size: 18, color: '#555'}, y: 0.98},
          margin: {l: 0, r: 0, t: 30, b: 0},
          scene: {
            ...(showAxes ? {
              // Thin axis lines only — no backplanes, no grid, no ticks.
              // Just the three spines meeting at the origin so the view is
              // unambiguously 3D. Plotly draws the spine when showline=true;
              // everything else is turned off.
              // Axes hidden — we draw our own from-origin lines as scatter3d traces
              xaxis: {visible: false},
              yaxis: {visible: false},
              zaxis: {visible: false},
            } : {
              xaxis: {visible: false},
              yaxis: {visible: false},
              zaxis: {visible: false},
            }),
            camera: lastCameras[key],
          },
        }, {
          responsive: true,
          ...(!compact && {
            modeBarButtonsToAdd: [{
              name: 'lasso-label',
              title: 'Lasso label mode',
              icon: Plotly.Icons.lasso,
              click: () => onLabelingModeChange(true),
            }],
          }),
        })
        divs.push(div)
      })
    } else {
      // Legacy 2D mode
      visibleKeys.forEach(key => {
        const div = plotDivs[key]
        if (!div) return
        Plotly.purge(div)

        const coords = getCoords(currentEmbeddings[key])
        if (!coords) return

        Plotly.newPlot(div, [{
          x: coords.d0, y: coords.d1,
          mode: 'markers', type: 'scattergl',
          marker: {
            size: 4,
            color: mc.color,
            colorscale: mc.colorscale,
            cmin: mc.cmin, cmax: mc.cmax,
            showscale: false,
          },
          hoverinfo: 'none',
          selected: {marker: {opacity: 1, size: 5, color: 'rgba(255, 100, 0, 0.9)'}},
          unselected: {marker: {opacity: 0.3, size: 3}},
        }], {
          title: {text: key, font: {size: 16, color: '#555'}, y: 0.98},
          xaxis: {zeroline: false, showgrid: false, showticklabels: false},
          yaxis: {zeroline: false, showgrid: false, showticklabels: false, scaleanchor: 'x'},
          margin: {l: 5, r: 5, t: 30, b: 5},
          hovermode: 'closest',
          dragmode: 'lasso',
        }, {responsive: true})
        divs.push(div)
      })
    }

    // Build overlap groups from the first visible embedding (all keys share the same point indices)
    const firstCoords = getCoords(currentEmbeddings[visibleKeys[0]])
    overlapGroups = firstCoords ? buildOverlapGroups(firstCoords) : null

    attachEventHandlers(divs)
    applyAnnotations(divs)

    // Re-apply selection state after re-render, or fall back to showing first point
    if (selectedPointIdx >= 0) {
      applySelection()
      showHoverText(selectedPointIdx)
    } else {
      const N = umapData.norms.length
      if (N > 0) {
        showHoverText(0)
      }
    }
  }

  function handleKeydown(event) {
    if (event.key === 'Escape' && selectedPointIdx >= 0) {
      deselectPoint()
    }
  }

  function attachEventHandlers(divs) {
    divs.forEach(div => {
      div.on('plotly_hover', eventData => {
        const pt = eventData.points[0]
        if (pt.curveNumber !== 0) return
        const rawIdx = pt.pointIndex != null ? pt.pointIndex : pt.pointNumber
        const idx = pickFromOverlap(overlapGroups, rawIdx)
        showHoverText(idx)
        if (is3D && !labelingMode) {
          highlightPoint3D(rawIdx)
        }
      })

      div.on('plotly_unhover', () => {
        // When a point is selected and user stops hovering, restore selected text
        if (selectedPointIdx >= 0) showHoverText(selectedPointIdx)
      })

      div.on('plotly_click', eventData => {
        if (labelingMode) return
        const pt = eventData.points[0]
        let idx
        if (pt.curveNumber === 0) {
          const rawIdx = pt.pointIndex != null ? pt.pointIndex : pt.pointNumber
          idx = pickFromOverlap(overlapGroups, rawIdx)
        } else if (pt.curveNumber === 1 && _lastHighlightIdx >= 0) {
          // Clicked the hover marker (trace 1) — select the cloud point it represents
          idx = _lastHighlightIdx
        } else {
          return
        }
        if (selectedPointIdx === idx) {
          deselectPoint()
        } else if (is3D) {
          // Defer to avoid re-entrant Plotly layout computation in 3D scenes
          requestAnimationFrame(() => selectPoint(idx))
        } else {
          selectPoint(idx)
        }
      })

      div.on('plotly_selected', eventData => {
        if (!eventData || !eventData.points || eventData.points.length === 0) return
        const indices = eventData.points.map(p => p.pointIndex)

        if (labelingMode) {
          const name = prompt(`Cluster name (${indices.length} points):`)
          if (name && name.trim()) {
            assignToCluster(name.trim(), indices)
          }
          divs.forEach(d => { if (d.data) Plotly.restyle(d, {selectedpoints: [null]}) })
        } else {
          divs.forEach(other => {
            if (other !== div && other.data) Plotly.restyle(other, {selectedpoints: [indices]})
          })
        }
      })

      div.on('plotly_deselect', () => {
        divs.forEach(other => {
          if (other !== div && other.data) Plotly.restyle(other, {selectedpoints: [null]})
        })
      })
    })
  }

  let _lastHighlightIdx = -1
  function highlightPoint3D(idx) {
    if (!currentEmbeddings || idx === _lastHighlightIdx) return
    if (selectedPointIdx >= 0) return
    _lastHighlightIdx = idx
    const divs = visibleKeys.map(k => plotDivs[k]).filter(Boolean)
    visibleKeys.forEach((key, ki) => {
      const coords = getCoords(currentEmbeddings?.[key])
      if (!coords || !divs[ki] || !divs[ki].data) return
      Plotly.restyle(divs[ki], {
        x: [[coords.d0[idx]]],
        y: [[coords.d1[idx]]],
        z: [[coords.d2[idx]]],
      }, [1])
    })
  }

  function showHoverText(idx) {
    if (!umapData || !textBox) return

    const seqIdx = umapData.seq_idx[idx]
    const qPos = umapData.top_q[idx]
    const kPos = umapData.top_k[idx]

    // Three-way token lookup: projected tokens → string seq_idx fallback → sequences.json
    let seqTokens
    if (projectedTokensMap.has(idx)) {
      seqTokens = projectedTokensMap.get(idx)
    } else if (typeof seqIdx === 'string') {
      const badge = compact ? '' : `<span class="seq-badge">${seqIdx}</span> `
      textBox.innerHTML = `${badge}<em>(no token data)</em>`
      return
    } else {
      seqTokens = sequences?.[seqIdx]
    }
    if (!seqTokens) return

    let html = compact ? '' : `<span class="seq-badge">${seqIdx}</span> `
    for (let pos = 0; pos < seqTokens.length; pos++) {
      let display = sanitizeToken(seqTokens[pos])
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\r/g, '')
        .replace(/\u2028/g, '')
        .replace(/\u2029/g, '')
        .replace(/\n/g, '\u23ce')
        .replace(/\t/g, '  ')

      if (pos === qPos && pos === kPos) {
        html += `<span class="tok-mark tok-qk">${display}<span class="tok-label" style="color:#7c3aed;">QK</span></span>`
      } else if (pos === qPos) {
        html += `<span class="tok-mark tok-q">${display}<span class="tok-label" style="color:#2563eb;">Q</span></span>`
      } else if (pos === kPos) {
        html += `<span class="tok-mark tok-k">${display}<span class="tok-label" style="color:#dc2626;">K</span></span>`
      } else {
        html += display
      }
    }

    textBox.innerHTML = html
    fitTextBox()
  }

  function fitTextBox() {
    if (!compact || !textBox) return
    textBox.style.fontSize = ''
    textBox.style.lineHeight = ''
    if (textBox.scrollHeight <= textBox.clientHeight) return
    let size = 12
    while (textBox.scrollHeight > textBox.clientHeight && size > 6) {
      size -= 0.5
      textBox.style.fontSize = `${size}px`
      textBox.style.lineHeight = `${Math.max(1.3, 1.7 * (size / 12))}`
    }
  }

  // --- Colorbar ---

  const VIRIDIS = [
    [0, '#440154'], [0.25, '#3b528b'], [0.5, '#21918c'],
    [0.75, '#5ec962'], [1, '#fde725'],
  ]

  function renderColorbar() {
    if (!colorbarCanvas) return
    const ctx = colorbarCanvas.getContext('2d')
    const w = colorbarCanvas.width
    const h = colorbarCanvas.height
    const grad = ctx.createLinearGradient(0, 0, w, 0)
    VIRIDIS.forEach(([stop, color]) => grad.addColorStop(stop, color))
    ctx.fillStyle = grad
    ctx.fillRect(0, 0, w, h)
  }

  // --- Cluster operations ---

  function indexToKey(i) {
    return `${umapData.seq_idx[i]},${umapData.top_q[i]},${umapData.top_k[i]}`
  }

  function indexToPoint(i) {
    return [umapData.seq_idx[i], umapData.top_q[i], umapData.top_k[i]]
  }

  function assignToCluster(name, indices) {
    const newPoints = indices.map(i => indexToPoint(i))
    const newKeys = new Set(indices.map(i => indexToKey(i)))

    const existing = clusters.find(c => c.name === name)
    if (existing) {
      // Merge: add new points, dedup by key
      const seen = new Set(existing.points.map(([s,q,k]) => `${s},${q},${k}`))
      for (const pt of newPoints) {
        const key = `${pt[0]},${pt[1]},${pt[2]}`
        if (!seen.has(key)) { existing.points.push(pt); seen.add(key) }
      }
      existing.point_indices = [...new Set([...existing.point_indices, ...indices])]
    } else {
      const ci = clusters.length
      clusters.push({
        name,
        color: CLUSTER_COLORS[ci % CLUSTER_COLORS.length],
        points: newPoints,
        point_indices: indices,
      })
    }

    // Remove reassigned points from other clusters
    clusters = clusters.map(c => {
      if (c.name !== name) {
        const filtered = c.points.map(([s,q,k], i) => [s,q,k,c.point_indices[i]])
          .filter(([s,q,k]) => !newKeys.has(`${s},${q},${k}`))
        return {
          ...c,
          points: filtered.map(([s,q,k]) => [s,q,k]),
          point_indices: filtered.map(([,,, idx]) => idx),
        }
      }
      return c
    }).filter(c => c.points.length > 0)

    colorMode = 'clusters'
    applyColors()
    persistClusters()
  }

  function deleteCluster(idx) {
    clusters = clusters.filter((_, i) => i !== idx)
    if (clusters.length === 0) {
      colorMode = 'rank'
    }
    applyColors()
    persistClusters()
  }

  function renameCluster(idx, newName) {
    if (newName && newName.trim()) {
      clusters[idx].name = newName.trim()
      clusters = [...clusters]
      applyColors()
      persistClusters()
    }
  }

  function applyColors() {
    if (!umapData) return

    const normRanks = computeNormRanks()
    if (!normRanks) return
    const mc = getPointColors(normRanks)
    const divs = visibleKeys.map(k => plotDivs[k]).filter(Boolean)

    divs.forEach(div => {
      if (!div || !div.data) return
      Plotly.restyle(div, {
        'marker.color': [mc.color],
        'marker.colorscale': mc.colorscale,
        'marker.cmin': mc.cmin,
        'marker.cmax': mc.cmax,
      }, [0])
    })

    applyAnnotations(divs)
  }

  function applyAnnotations(divs) {
    if (!divs) divs = visibleKeys.map(k => plotDivs[k]).filter(Boolean)
    if (!currentEmbeddings) return

    visibleKeys.forEach((key, ki) => {
      if (!divs[ki] || !divs[ki].data) return
      const annotations = []

      if (colorMode === 'clusters' && clusters.length > 0) {
        if (labelingMode && is3D) {
          const proj = projectedCoords[key]
          if (proj) {
            clusters.forEach((c, ci) => {
              const col = CLUSTER_COLORS[ci % CLUSTER_COLORS.length]
              const indices = c.point_indices || []
              let sx = 0, sy = 0, count = 0
              indices.forEach(i => {
                const x = proj.x[i], y = proj.y[i]
                if (x != null && y != null && isFinite(x) && isFinite(y)) {
                  sx += x; sy += y; count++
                }
              })
              if (count > 0) {
                annotations.push({
                  x: sx/count, y: sy/count,
                  text: c.name, showarrow: false,
                  font: {size: 10, color: col, family: 'sans-serif'},
                  bgcolor: 'rgba(255,255,255,0.8)', borderpad: 2,
                })
              }
            })
          }
          Plotly.relayout(divs[ki], {annotations})
        } else if (is3D) {
          const coords = getCoords(currentEmbeddings[key])
          if (coords) {
            clusters.forEach((c, ci) => {
              const col = CLUSTER_COLORS[ci % CLUSTER_COLORS.length]
              const indices = c.point_indices || []
              let sx = 0, sy = 0, sz = 0, count = 0
              indices.forEach(i => {
                const x = coords.d0[i], y = coords.d1[i], z = coords.d2[i]
                if (x != null && y != null && z != null && isFinite(x) && isFinite(y) && isFinite(z)) {
                  sx += x; sy += y; sz += z; count++
                }
              })
              if (count > 0) {
                annotations.push({
                  x: sx/count, y: sy/count, z: sz/count,
                  text: c.name, showarrow: false,
                  font: {size: 10, color: col, family: 'sans-serif'},
                  bgcolor: 'rgba(255,255,255,0.8)', borderpad: 2,
                })
              }
            })
          }
          Plotly.relayout(divs[ki], {'scene.annotations': annotations})
        } else {
          const coords = getCoords(currentEmbeddings[key])
          if (coords) {
            clusters.forEach((c, ci) => {
              const col = CLUSTER_COLORS[ci % CLUSTER_COLORS.length]
              const indices = c.point_indices || []
              let sx = 0, sy = 0, count = 0
              indices.forEach(i => {
                const x = coords.d0[i], y = coords.d1[i]
                if (x != null && y != null && isFinite(x) && isFinite(y)) {
                  sx += x; sy += y; count++
                }
              })
              if (count > 0) {
                annotations.push({
                  x: sx/count, y: sy/count,
                  text: c.name, showarrow: false,
                  font: {size: 10, color: col, family: 'sans-serif'},
                  bgcolor: 'rgba(255,255,255,0.8)', borderpad: 2,
                })
              }
            })
          }
          Plotly.relayout(divs[ki], {annotations})
        }
      } else {
        if (is3D && !labelingMode) {
          Plotly.relayout(divs[ki], {'scene.annotations': []})
        } else {
          Plotly.relayout(divs[ki], {annotations: []})
        }
      }
    })
  }

  async function persistClusters() {
    if (!onSaveClusters) return
    savingClusters = true
    try {
      const clusterPayload = clusters.map(c => ({
        name: c.name,
        color: c.color,
        points: c.points,
      }))
      await onSaveClusters(clusterPayload)
      // Persist to in-memory umapData so clusters survive tab switch
      if (umapData) umapData.clusters = clusterPayload
    } catch (e) {
      console.error('Failed to save clusters:', e)
    } finally {
      savingClusters = false
    }
  }

  let editingClusterIdx = $state(null)
  let editingClusterName = $state('')

  function startRename(idx) {
    editingClusterIdx = idx
    editingClusterName = clusters[idx].name
  }

  function commitRename() {
    if (editingClusterIdx !== null) {
      renameCluster(editingClusterIdx, editingClusterName)
      editingClusterIdx = null
    }
  }

  function cancelRename() {
    editingClusterIdx = null
  }

  // React to color mode changes
  $effect(() => {
    colorMode;
    untrack(() => {
      if (umapData) applyColors()
    })
  })

  // Re-render when view index or proj mode changes
  let prevViewIdx = $state(-1)
  let prevProjMode = $state('umap')
  $effect(() => {
    const idx = currentViewIdx
    const pm = projMode
    untrack(() => {
      if ((idx !== prevViewIdx || pm !== prevProjMode) && prevViewIdx >= 0 && umapData) {
        prevViewIdx = idx
        prevProjMode = pm
        tick().then(() => renderPlots())
      } else {
        prevViewIdx = idx
        prevProjMode = pm
      }
    })
  })

  // Re-render when panel visibility changes
  let prevVisibleKeys = $state('')
  $effect(() => {
    const vk = visibleKeys.join(',')
    untrack(() => {
      if (vk !== prevVisibleKeys && prevVisibleKeys !== '' && umapData) {
        prevVisibleKeys = vk
        tick().then(() => renderPlots())
      } else {
        prevVisibleKeys = vk
      }
    })
  })

  // Labeling mode toggle handler
  function onLabelingModeChange(checked) {
    if (checked && is3D) {
      visibleKeys.forEach(key => {
        const div = plotDivs[key]
        if (!div || !div._fullLayout) return
        const layout = div._fullLayout.scene
        if (layout && layout._scene) {
          const cam = layout._scene.getCamera()
          lastCameras[key] = {eye: cam.eye, up: cam.up, center: cam.center}
        }
        if (layout) {
          lastSceneInfos[key] = {
            xRange: layout.xaxis.range,
            yRange: layout.yaxis.range,
            zRange: layout.zaxis.range,
            aspect: layout.aspectratio,
          }
          const coords = getCoords(currentEmbeddings?.[key])
          if (coords) {
            projectedCoords[key] = projectToCamera(coords, lastCameras[key], lastSceneInfos[key])
          }
        }
      })
    }
    labelingMode = checked
    if (checked) {
      colorMode = 'clusters'
    }
    tick().then(() => renderPlots())
  }

  // Render colorbar when canvas becomes available
  $effect(() => {
    if (colorbarCanvas) {
      untrack(() => renderColorbar())
    }
  })

  // Panel toggle with at-least-one guard
  function togglePanel(key, checked) {
    const newVisible = {...panelVisible, [key]: checked}
    const anyVisible = ALL_KEYS.some(k => newVisible[k])
    if (!anyVisible) return
    panelVisible = newVisible
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="umap-container" class:compact>
  <div class="umap-top">
    <div class="umap-plots-wrapper">
      {#if views && views.length > 1}
        <div class="view-selector">
          <button class="view-nav" onclick={() => { currentViewIdx = Math.max(0, currentViewIdx - 1) }} disabled={currentViewIdx === 0}>&lsaquo;</button>
          <select bind:value={currentViewIdx}>
            {#each views as view, i}
              <option value={i}>nn={view.n_neighbors} md={view.min_dist}</option>
            {/each}
          </select>
          <button class="view-nav" onclick={() => { currentViewIdx = Math.min(views.length - 1, currentViewIdx + 1) }} disabled={currentViewIdx === views.length - 1}>&rsaquo;</button>
        </div>
      {/if}
      <div class="umap-plots">
        {#each ALL_KEYS as key}
          <div class="plot-cell" style:display={panelVisible[key] ? '' : 'none'}>
            <div bind:this={plotDivs[key]}></div>
          </div>
        {/each}
      </div>
      <div class="umap-text-box" bind:this={textBox}>
        Hover over a point to see the sequence
      </div>
    </div>
    {#if !compact}
      <button
        class="sidebar-toggle"
        onclick={() => sidebarCollapsed = !sidebarCollapsed}
        title={sidebarCollapsed ? 'Show settings' : 'Hide settings'}
      >
        {sidebarCollapsed ? '\u2039' : '\u203a'}
      </button>
    {/if}
    {#if !sidebarCollapsed && !compact}
      <div class="umap-sidebar">
        {#if hasPca}
          <div class="setting-group">
            <div class="setting-label">Projection</div>
            <div class="radio-group">
              <label><input type="radio" bind:group={projMode} value="umap"> UMAP</label>
              <label><input type="radio" bind:group={projMode} value="pca"> PCA</label>
            </div>
          </div>
        {/if}

        <div class="setting-group">
          <div class="setting-label">Panels</div>
          <div class="radio-group">
            {#each ALL_KEYS as key}
              <label>
                <input
                  type="checkbox"
                  checked={panelVisible[key]}
                  onchange={(e) => togglePanel(key, e.target.checked)}
                >
                {key === 'O' ? 'O (output)' : key === 'V' ? 'V (value)' : key === 'Q' ? 'Q (query)' : 'K (key)'}
              </label>
            {/each}
          </div>
        </div>

        <div class="setting-group">
          <div class="setting-label">Color by</div>
          <div class="radio-group">
            <label>
              <input type="radio" bind:group={colorMode} value="rank"> Rank
            </label>
            <label>
              <input type="radio" bind:group={colorMode} value="clusters"> Clusters
            </label>
          </div>
          {#if colorMode === 'rank'}
            <div class="inline-colorbar">
              <canvas bind:this={colorbarCanvas} width="160" height="10"></canvas>
              <div class="colorbar-labels">
                <span>0</span>
                <span>rank</span>
                <span>1</span>
              </div>
            </div>
          {/if}
        </div>

        {#if clusters.length > 0}
          <div class="setting-group">
            <div class="setting-label">Clusters {#if savingClusters}<span class="saving-indicator">saving...</span>{/if}</div>
            <div class="cluster-list">
              {#each clusters as cluster, i}
                <div class="cluster-item">
                  <div class="cluster-swatch" style="background: {CLUSTER_COLORS[i % CLUSTER_COLORS.length]}"></div>
                  {#if editingClusterIdx === i}
                    <input
                      class="cluster-name-input"
                      bind:value={editingClusterName}
                      onblur={commitRename}
                      onkeydown={(e) => {
                        if (e.key === 'Enter') { e.preventDefault(); commitRename(); }
                        if (e.key === 'Escape') cancelRename();
                      }}
                    >
                  {:else}
                    <span class="cluster-name" ondblclick={() => startRename(i)}>{cluster.name}</span>
                  {/if}
                  <span class="cluster-count">{(cluster.point_indices || []).length}</span>
                  <button class="cluster-delete" onclick={() => deleteCluster(i)}>&times;</button>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .umap-container {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .umap-top {
    display: flex;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  .umap-plots-wrapper {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
    min-height: 0;
  }

  .umap-plots {
    display: flex;
    flex: 0 1 auto;
    max-height: 70%;
    min-height: 0;
    gap: 1px;
    background: #eee;
  }

  .plot-cell {
    flex: 1;
    min-width: 0;
    min-height: 0;
    aspect-ratio: 10 / 11;
    position: relative;
    overflow: hidden;
    background: white;
  }
  .plot-cell > div { width: 100%; height: 100%; }

  /* Keep Plotly modebar always visible */
  .plot-cell :global(.modebar) { opacity: 1 !important; }

  /* Emphasize the lasso-label button with color + pulse */
  .plot-cell :global(.modebar-btn[data-title="Lasso label mode"]) {
    animation: pulse-lasso 3s ease-in-out infinite;
  }
  .plot-cell :global(.modebar-btn[data-title="Lasso label mode"] path) {
    fill: #e6194b !important;
  }
  .plot-cell :global(.modebar-btn[data-title="Lasso label mode"]:hover path) {
    fill: #b8152e !important;
  }
  /* Emphasize the back-to-3d button with color + pulse */
  .plot-cell :global(.modebar-btn[data-title="Back to 3D"]) {
    animation: pulse-lasso 3s ease-in-out infinite;
  }
  .plot-cell :global(.modebar-btn[data-title="Back to 3D"] path) {
    fill: #4363d8 !important;
  }
  .plot-cell :global(.modebar-btn[data-title="Back to 3D"]:hover path) {
    fill: #2d47a0 !important;
  }

  @keyframes pulse-lasso {
    0%, 100% { transform: scale(1); opacity: 1; }
    50% { transform: scale(1.25); opacity: 0.7; }
  }

  .umap-text-box {
    flex: 1;
    min-height: 60px;
    padding: 10px 12px;
    border-top: 1px solid #eee;
    overflow-y: auto;
    white-space: pre-wrap;
    word-wrap: break-word;
    font-family: sans-serif;
    font-size: 12px;
    line-height: 1.7;
    color: rgba(0, 0, 0, 0.3);
  }
  .umap-text-box :global(b) { color: rgba(0, 0, 0, 0.8); }
  .umap-text-box :global(.seq-badge) {
    display: inline-block;
    background: #2196f3;
    color: white;
    font-size: 10px;
    font-weight: 600;
    padding: 1px 5px;
    border-radius: 3px;
    vertical-align: middle;
    opacity: 0.9;
  }
  .umap-text-box :global(.tok-mark) {
    position: relative;
    display: inline-block;
    min-width: 6px;
    padding: 0 2px;
    border-radius: 3px;
    border-bottom: 2px solid;
    color: rgba(0, 0, 0, 0.9);
  }
  .umap-text-box :global(.tok-q) { background: #dbeafe; border-color: #2563eb; }
  .umap-text-box :global(.tok-k) { background: #fee2e2; border-color: #dc2626; }
  .umap-text-box :global(.tok-qk) { background: #ede9fe; border-color: #7c3aed; }
  .umap-text-box :global(.tok-label) {
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    font-size: 8px;
    font-weight: 700;
    line-height: 1;
    pointer-events: none;
    margin-bottom: -2px;
  }

  .sidebar-toggle {
    flex: 0 0 auto;
    width: 18px;
    padding: 0;
    border: none;
    border-left: 1px solid #eee;
    background: #fafafa;
    color: #999;
    font-size: 14px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .sidebar-toggle:hover { background: #eee; color: #555; }

  .umap-sidebar {
    flex: 0 0 195px;
    padding: 10px;
    border-left: 1px solid #eee;
    overflow-y: auto;
    min-height: 0;
  }

  .setting-group { margin-bottom: 14px; }
  .setting-label {
    font-size: 10px;
    color: #999;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .radio-group { display: flex; flex-direction: column; gap: 3px; }
  .radio-group label {
    font-size: 12px;
    color: #444;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .radio-group input[type="radio"] { margin: 0; cursor: pointer; }

  .cluster-list { margin-top: 6px; }
  .cluster-item {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    padding: 3px 0;
    border-bottom: 1px solid #f0f0f0;
  }
  .cluster-swatch {
    width: 8px;
    height: 8px;
    border-radius: 2px;
    flex-shrink: 0;
  }
  .cluster-name {
    flex: 1;
    color: #444;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    cursor: pointer;
  }
  .cluster-name-input {
    flex: 1;
    font: inherit;
    font-size: 10px;
    border: 1px solid #aaa;
    border-radius: 2px;
    padding: 0 2px;
    outline: none;
  }
  .cluster-count { color: #999; font-size: 10px; }
  .cluster-delete {
    cursor: pointer;
    color: #ccc;
    font-size: 13px;
    background: none;
    border: none;
    padding: 0 2px;
    transition: color 0.15s;
  }
  .cluster-delete:hover { color: #e55; }

  .saving-indicator {
    font-size: 9px;
    color: #aaa;
    font-style: italic;
  }

  .inline-colorbar {
    margin-top: 6px;
  }
  .inline-colorbar canvas {
    width: 100%;
    height: 10px;
    border-radius: 2px;
  }
  .colorbar-labels {
    display: flex;
    justify-content: space-between;
    font-size: 9px;
    color: #999;
    margin-top: 1px;
  }

  .view-selector {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 4px 8px;
    border-bottom: 1px solid #eee;
    background: #fafafa;
  }
  .view-selector select {
    font-size: 12px;
    padding: 2px 6px;
    border: 1px solid #ccc;
    border-radius: 3px;
    background: white;
  }
  .view-nav {
    font-size: 16px;
    line-height: 1;
    padding: 0 6px;
    border: 1px solid #ccc;
    border-radius: 3px;
    background: white;
    cursor: pointer;
    color: #444;
  }
  .view-nav:disabled {
    opacity: 0.3;
    cursor: default;
  }
  .view-nav:hover:not(:disabled) {
    background: #eee;
  }

  .compact .umap-plots {
    flex: 1;
    max-height: none;
  }

  .compact .umap-text-box {
    flex: 0 0 120px;
    min-height: auto;
    overflow-y: hidden;
  }
</style>
