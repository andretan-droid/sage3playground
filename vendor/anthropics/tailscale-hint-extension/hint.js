// Parse URL parameters
const params = new URLSearchParams(window.location.search);
const originalUrl = params.get('url') || '';
const hostname = params.get('host') || '';

// Display the hostname
const hostnameEl = document.getElementById('hostname');
if (hostname) {
  hostnameEl.textContent = hostname;
} else if (originalUrl) {
  try {
    const url = new URL(originalUrl);
    hostnameEl.textContent = url.hostname;
  } catch (e) {
    hostnameEl.textContent = originalUrl;
  }
} else {
  hostnameEl.textContent = 'Unknown .local domain';
}

function retry() {
  if (originalUrl) {
    window.location.href = originalUrl;
  } else {
    window.history.back();
  }
}

function copyText(text, btn) {
  navigator.clipboard.writeText(text).then(function() {
    var original = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(function() {
      btn.textContent = original;
    }, 1500);
  }).catch(function(err) {
    console.error('Copy failed:', err);
  });
}

// Connectivity monitor
const PING_INTERVAL_MIN = 200;  // Start fast
const PING_INTERVAL_MAX = 1000; // Back off to 1s
const GRAPH_POINTS = 60;
let currentPingInterval = PING_INTERVAL_MIN;
let pingCount = 0;

// Extract cluster from hostname (e.g., "foo.ns.svc.sodium-a.local" -> "sodium-a")
function getClusterFromHost(host) {
  // Try .svc.{cluster}.local pattern first
  let match = host.match(/\.svc\.([^.]+)\.local$/);
  if (match) return match[1];
  // Fallback: try .{cluster}.local pattern (second-to-last segment)
  match = host.match(/\.([^.]+)\.local$/);
  return match ? match[1] : null;
}

const cluster = getClusterFromHost(hostname);
// kcprr for the cluster, or kcprr.ant.dev as fallback
const DNS_URL = cluster
  ? `http://kcprr.infra.svc.${cluster}.local:8080/`
  : 'https://kcprr.ant.dev/health';
const DNS_LABEL = cluster ? `kcprr (${cluster})` : 'kcprr.ant.dev';
// The original URL they were trying to reach
const TARGET_URL = originalUrl;

console.log('Tailscale hint - cluster:', cluster, 'DNS_URL:', DNS_URL, 'TARGET_URL:', TARGET_URL);

let dnsHistory = [];
let targetHistory = [];
let pingInterval = null;
let displayFrozen = false;
let frozenDnsHistory = [];
let frozenTargetHistory = [];

function initGraph() {
  const monitor = document.querySelector('.ping-monitor');
  if (!monitor || (!DNS_URL && !TARGET_URL)) {
    if (monitor) monitor.style.display = 'none';
    return;
  }

  // Set dynamic DNS label
  const dnsLabelEl = document.getElementById('dns-label');
  if (dnsLabelEl) dnsLabelEl.textContent = DNS_LABEL;

  // Hide sections if URL not available
  const dnsSection = document.getElementById('ping-graph-dns')?.parentElement;
  const targetSection = document.getElementById('ping-graph-target')?.parentElement;
  if (!DNS_URL && dnsSection) dnsSection.style.display = 'none';
  if (!TARGET_URL && targetSection) targetSection.style.display = 'none';

  // Initialize with empty points
  for (let i = 0; i < GRAPH_POINTS; i++) {
    dnsHistory.push({ status: 'unknown', time: null });
    targetHistory.push({ status: 'unknown', time: null });
  }

  // Freeze display on hover
  const statusEl = document.getElementById('ping-status');
  let statusBeforeHover = '';
  monitor.addEventListener('mouseenter', () => {
    displayFrozen = true;
    frozenDnsHistory = [...dnsHistory];
    frozenTargetHistory = [...targetHistory];
    statusBeforeHover = statusEl.textContent;
    statusEl.textContent = 'Click to copy stats';
    statusEl.style.color = 'var(--green)';
  });
  monitor.addEventListener('mouseleave', () => {
    displayFrozen = false;
    renderGraph();
    updateStatus(dnsHistory[dnsHistory.length-1], targetHistory[targetHistory.length-1]);
  });

  // Click to copy trend data
  monitor.addEventListener('click', copyTrendData);

  renderGraph();
  startPinging();
}

function copyTrendData() {
  const hist = displayFrozen ? { dns: frozenDnsHistory, target: frozenTargetHistory }
                             : { dns: dnsHistory, target: targetHistory };

  const formatHistory = (h, label) => {
    const valid = h.filter(p => p.status !== 'unknown');
    if (valid.length === 0) return `${label}: no data`;
    const times = valid.filter(p => p.time !== null).map(p => p.time);
    const failures = valid.filter(p => p.status === 'down').length;
    const avg = times.length ? Math.round(times.reduce((a,b) => a+b, 0) / times.length) : 'N/A';
    const min = times.length ? Math.min(...times) : 'N/A';
    const max = times.length ? Math.max(...times) : 'N/A';
    return `${label}: avg=${avg}ms min=${min}ms max=${max}ms failures=${failures}/${valid.length}`;
  };

  const text = [
    formatHistory(hist.target, 'Target'),
    formatHistory(hist.dns, DNS_LABEL)
  ].join('\n');

  navigator.clipboard.writeText(text).then(() => {
    const statusEl = document.getElementById('ping-status');
    const orig = statusEl.textContent;
    statusEl.textContent = 'Copied!';
    setTimeout(() => { if (!displayFrozen) updateStatus(dnsHistory[dnsHistory.length-1], targetHistory[targetHistory.length-1]); else statusEl.textContent = orig; }, 1000);
  });
}

const MAX_LATENCY = 500; // ms, for scaling bar heights

function renderGraph() {
  if (displayFrozen) return; // Don't update display while frozen

  const dnsGraphEl = document.getElementById('ping-graph-dns');
  const targetGraphEl = document.getElementById('ping-graph-target');

  const renderBars = (history) => history.map((p, i) => {
    let color = '#1a1a1a';
    let height = '2px';
    if (p.status === 'up') {
      color = '#48d597';
      const pct = Math.min(100, Math.max(10, (p.time / MAX_LATENCY) * 100));
      height = pct + '%';
    } else if (p.status === 'down') {
      color = '#ff4444';
      height = '100%';
    }
    const tooltip = p.status === 'unknown' ? '' : (p.time ? p.time + 'ms' : 'timeout');
    return '<div class="ping-bar" data-idx="' + i + '" style="background:' + color + ';height:' + height + '"></div>';
  }).join('');

  if (dnsGraphEl && DNS_URL) {
    dnsGraphEl.innerHTML = renderBars(dnsHistory);
    addBarHoverListeners(dnsGraphEl, dnsHistory, 'dns');
  }

  if (targetGraphEl && TARGET_URL) {
    targetGraphEl.innerHTML = renderBars(targetHistory);
    addBarHoverListeners(targetGraphEl, targetHistory, 'target');
  }
}

function addBarHoverListeners(graphEl, history, type) {
  const tooltip = document.getElementById('ping-tooltip');
  graphEl.querySelectorAll('.ping-bar').forEach((bar) => {
    bar.addEventListener('mouseenter', (e) => {
      const idx = parseInt(bar.dataset.idx);
      const hist = displayFrozen ? (type === 'dns' ? frozenDnsHistory : frozenTargetHistory) : history;
      const p = hist[idx];
      if (p && p.status !== 'unknown') {
        tooltip.textContent = p.time ? p.time + 'ms' : 'timeout';
        tooltip.style.display = 'block';
        const rect = bar.getBoundingClientRect();
        tooltip.style.left = rect.left + rect.width/2 - tooltip.offsetWidth/2 + 'px';
        tooltip.style.top = rect.top - 24 + 'px';
      }
    });
    bar.addEventListener('mouseleave', () => {
      tooltip.style.display = 'none';
    });
  });
}

async function pingUrl(url) {
  const start = Date.now();
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2500);

    await fetch(url, {
      method: 'HEAD',
      mode: 'no-cors',
      cache: 'no-store',
      signal: controller.signal
    });

    clearTimeout(timeout);
    return { status: 'up', time: Date.now() - start };
  } catch (e) {
    return { status: 'down', time: null };
  }
}

async function doPing() {
  // Ping both in parallel
  const [dnsResult, targetResult] = await Promise.all([
    DNS_URL ? pingUrl(DNS_URL) : Promise.resolve({ status: 'unknown', time: null }),
    TARGET_URL ? pingUrl(TARGET_URL) : Promise.resolve({ status: 'unknown', time: null })
  ]);

  if (DNS_URL) {
    dnsHistory.shift();
    dnsHistory.push(dnsResult);
  }

  if (TARGET_URL) {
    targetHistory.shift();
    targetHistory.push(targetResult);
  }

  renderGraph();
  updateStatus(dnsResult, targetResult);

  // Auto-retry when target is up
  if (targetResult.status === 'up' && TARGET_URL) {
    stopPinging();
    document.getElementById('ping-status').textContent = 'Connected! Redirecting...';
    setTimeout(retry, 1000);
  }
}

const CONSISTENT_THRESHOLD = 5; // Number of consistent results to change header

function updateStatus(dnsResult, targetResult) {
  const statusEl = document.getElementById('ping-status');
  if (!statusEl) return;

  const dnsUp = dnsResult.status === 'up';
  const targetUp = targetResult.status === 'up';

  if (targetUp) {
    statusEl.textContent = 'Target reachable (' + targetResult.time + 'ms)';
    statusEl.style.color = '#48d597';
  } else if (dnsUp) {
    statusEl.textContent = 'Tailscale up, target unreachable';
    statusEl.style.color = '#f0ad4e';
  } else {
    statusEl.textContent = 'No Tailscale connection';
    statusEl.style.color = '#ff4444';
  }

  // Update header if pattern is consistent
  updateHeader();
}

function updateHeader() {
  const headerEl = document.querySelector('h1');
  const subtitleEl = document.querySelector('.subtitle');
  const helpEl = document.querySelector('.help');
  if (!headerEl) return;

  // Check last N results
  const recentDns = dnsHistory.slice(-CONSISTENT_THRESHOLD).filter(p => p.status !== 'unknown');
  const recentTarget = targetHistory.slice(-CONSISTENT_THRESHOLD).filter(p => p.status !== 'unknown');

  if (recentDns.length < CONSISTENT_THRESHOLD || recentTarget.length < CONSISTENT_THRESHOLD) return;

  const dnsAllUp = recentDns.every(p => p.status === 'up');
  const targetAllDown = recentTarget.every(p => p.status === 'down');
  const targetAllUp = recentTarget.every(p => p.status === 'up');

  if (dnsAllUp && targetAllDown) {
    headerEl.textContent = 'Service Unavailable';
    if (subtitleEl) {
      subtitleEl.innerHTML = 'Tailscale is connected, but the service is not responding. Check the URL or verify the service is running.';
    }
    if (helpEl) helpEl.style.display = 'none';
  } else if (!dnsAllUp) {
    headerEl.textContent = 'Tailscale Connection Required';
    if (helpEl) helpEl.style.display = 'block';
  } else if (targetAllUp) {
    headerEl.textContent = 'Connection Restored';
  }
}

let pingStopped = false;

function startPinging() {
  pingStopped = false;
  schedulePing();
}

async function schedulePing() {
  if (pingStopped) return;

  await doPing();

  if (pingStopped) return;

  pingCount++;
  // Back off: start at 200ms, reach 1000ms within ~5 seconds
  // 200, 300, 450, 600, 800, 1000 (roughly 10 pings in 5s)
  currentPingInterval = Math.min(PING_INTERVAL_MAX, PING_INTERVAL_MIN + pingCount * 100);
  pingInterval = setTimeout(schedulePing, currentPingInterval);
}

function stopPinging() {
  pingStopped = true;
  if (pingInterval) {
    clearTimeout(pingInterval);
    pingInterval = null;
  }
}

// Attach event listeners (inline onclick blocked by CSP)
document.addEventListener('DOMContentLoaded', function() {
  document.getElementById('btn-retry').addEventListener('click', retry);

  document.querySelectorAll('.copy-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      copyText(btn.dataset.cmd, btn);
    });
  });

  initGraph();
});
