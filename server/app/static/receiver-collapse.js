(() => {
  const storageKey = 'smsRelayCollapsedReceivers';

  function loadCollapsed() {
    try {
      return new Set(JSON.parse(window.localStorage.getItem(storageKey) || '[]'));
    } catch (_) {
      return new Set();
    }
  }

  function saveCollapsed(collapsed) {
    window.localStorage.setItem(storageKey, JSON.stringify([...collapsed]));
  }

  function rowsFor(button) {
    const rows = [];
    let node = button.nextElementSibling;
    while (node && !node.matches('[data-receiver-toggle]')) {
      if (node.matches('[data-receiver-row]')) rows.push(node);
      node = node.nextElementSibling;
    }
    return rows;
  }

  function apply(button, collapsed) {
    button.classList.toggle('collapsed', collapsed);
    button.setAttribute('aria-expanded', String(!collapsed));
    const icon = button.querySelector('.thread-divider-icon');
    if (icon) icon.textContent = collapsed ? '+' : '-';
    rowsFor(button).forEach((row) => {
      row.hidden = collapsed;
    });
  }

  const collapsed = loadCollapsed();
  const buttons = document.querySelectorAll('[data-receiver-toggle]');

  buttons.forEach((button) => {
    const receiver = button.dataset.receiver;
    apply(button, collapsed.has(receiver));

    button.addEventListener('click', () => {
      const nextCollapsed = !collapsed.has(receiver);
      if (nextCollapsed) {
        collapsed.add(receiver);
      } else {
        collapsed.delete(receiver);
      }
      saveCollapsed(collapsed);
      apply(button, nextCollapsed);
    });
  });
})();
