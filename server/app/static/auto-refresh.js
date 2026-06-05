(() => {
  const intervalMs = 5000;
  let initialState = null;

  async function fetchState() {
    const response = await fetch('/api/v1/inbox-state', {
      cache: 'no-store',
      headers: { 'Accept': 'application/json' },
    });
    if (!response.ok) return null;
    return response.json();
  }

  function changed(a, b) {
    return a.message_count !== b.message_count ||
      a.sender_count !== b.sender_count ||
      a.newest_received_at_server !== b.newest_received_at_server;
  }

  async function checkForUpdates() {
    try {
      const state = await fetchState();
      if (!state) return;
      if (!initialState) {
        initialState = state;
        return;
      }
      if (changed(initialState, state)) {
        window.location.reload();
      }
    } catch (_) {
      // Keep the page usable if the server is briefly unavailable.
    }
  }

  checkForUpdates();
  window.setInterval(checkForUpdates, intervalMs);
})();
