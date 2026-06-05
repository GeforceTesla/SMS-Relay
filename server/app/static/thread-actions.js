(() => {
  const menu = document.getElementById('thread-context-menu');
  if (!menu) return;

  const deleteButton = menu.querySelector('.context-menu-delete');
  let selectedRow = null;

  function hideMenu() {
    menu.hidden = true;
    selectedRow = null;
  }

  function positionMenu(event) {
    menu.hidden = false;
    const bounds = menu.getBoundingClientRect();
    const left = Math.min(event.clientX, window.innerWidth - bounds.width - 8);
    const top = Math.min(event.clientY, window.innerHeight - bounds.height - 8);
    menu.style.left = `${Math.max(8, left)}px`;
    menu.style.top = `${Math.max(8, top)}px`;
  }

  document.addEventListener('contextmenu', (event) => {
    const row = event.target.closest('.thread-row[data-delete-url]');
    if (!row) {
      hideMenu();
      return;
    }

    event.preventDefault();
    selectedRow = row;
    positionMenu(event);
  });

  deleteButton?.addEventListener('click', () => {
    if (!selectedRow) return;

    const sender = selectedRow.dataset.sender || 'this sender';
    const confirmed = window.confirm(`Delete the entire message chain from ${sender}?`);
    if (!confirmed) {
      hideMenu();
      return;
    }

    const form = document.createElement('form');
    form.method = 'post';
    form.action = selectedRow.dataset.deleteUrl;
    document.body.appendChild(form);
    form.submit();
  });

  document.addEventListener('click', (event) => {
    if (!menu.contains(event.target)) hideMenu();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') hideMenu();
  });
})();
