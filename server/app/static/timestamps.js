(() => {
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
  const localFormatter = new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });

  function relativeTime(date, now) {
    const seconds = Math.round((date.getTime() - now.getTime()) / 1000);
    const abs = Math.abs(seconds);
    if (abs < 45) return rtf.format(seconds, 'second');
    const minutes = Math.round(seconds / 60);
    if (Math.abs(minutes) < 45) return rtf.format(minutes, 'minute');
    const hours = Math.round(minutes / 60);
    if (Math.abs(hours) < 36) return rtf.format(hours, 'hour');
    const days = Math.round(hours / 24);
    if (Math.abs(days) < 30) return rtf.format(days, 'day');
    const months = Math.round(days / 30);
    if (Math.abs(months) < 18) return rtf.format(months, 'month');
    return rtf.format(Math.round(months / 12), 'year');
  }

  function renderTimestamps() {
    const now = new Date();
    document.querySelectorAll('time[data-epoch-ms]').forEach((node) => {
      const epoch = Number(node.dataset.epochMs);
      if (!Number.isFinite(epoch)) return;
      const date = new Date(epoch);
      const local = localFormatter.format(date);
      const relative = relativeTime(date, now);
      node.dateTime = date.toISOString();
      node.title = `${local} (${relative})`;
      node.textContent = node.dataset.timeFormat === 'compact'
        ? relative
        : `${local} · ${relative}`;
    });
  }

  function scrollToBottom() {
    document.querySelectorAll('[data-scroll-bottom]').forEach((node) => {
      const top = Math.max(0, node.scrollHeight - node.clientHeight);
      node.scrollTo({ top, behavior: 'instant' });
      node.scrollTop = top;
    });
  }

  function scheduleScrollToBottom() {
    scrollToBottom();
    requestAnimationFrame(() => {
      scrollToBottom();
      requestAnimationFrame(scrollToBottom);
    });
    window.setTimeout(scrollToBottom, 100);
  }

  renderTimestamps();
  scheduleScrollToBottom();
  window.setInterval(renderTimestamps, 60_000);
  window.addEventListener('load', scheduleScrollToBottom);
  window.addEventListener('pageshow', scheduleScrollToBottom);
})();
