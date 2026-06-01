// Listen for navigation errors
chrome.webNavigation.onErrorOccurred.addListener((details) => {
  // Only handle main frame errors
  if (details.frameId !== 0) return;

  // Check for DNS resolution errors
  const dnsErrors = [
    'net::ERR_NAME_NOT_RESOLVED',
    'net::ERR_NAME_RESOLUTION_FAILED'
  ];

  if (dnsErrors.includes(details.error)) {
    try {
      const url = new URL(details.url);
      // Check if it's a .local domain (Tailscale MagicDNS)
      if (url.hostname.endsWith('.local')) {
        // Redirect to our helpful page
        chrome.tabs.update(details.tabId, {
          url: chrome.runtime.getURL('tailscale-hint.html') +
               '?url=' + encodeURIComponent(details.url) +
               '&host=' + encodeURIComponent(url.hostname)
        });
      }
    } catch (e) {
      console.error('Tailscale hint extension error:', e);
    }
  }
});

console.log('Tailscale hint extension loaded');
