(() => {
  const translate = (key) => window.siteI18n?.t(key) || key;
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
  function notify(message) {
    const toast = document.getElementById('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(notify.timer);
    notify.timer = setTimeout(() => toast.classList.remove('show'), 5000);
  }
  document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-favorite], [data-subscription]');
    if (!button || button.disabled) return;
    const isFavorite = button.hasAttribute('data-favorite');
    const desired = button.getAttribute('aria-pressed') !== 'true';
    const endpoint = isFavorite
      ? `/api/favorites/${button.dataset.favorite}/${button.dataset.entityId}`
      : `/api/subscriptions/${button.dataset.subscription}`;
    button.disabled = true;
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        body: JSON.stringify(isFavorite ? { saved: desired } : { subscribed: desired }),
      });
      const data = await response.json();
      if (!response.ok) {
        if (response.status === 401) {
          window.showLoginModal?.();
          notify(translate('memberRequired'));
        } else notify(translate(data.message_key || 'genericError'));
        return;
      }
      button.setAttribute('aria-pressed', String(desired));
      const key = isFavorite ? (desired ? 'savedFavorite' : 'saveFavorite') : (desired ? 'subscribedTeam' : 'subscribeTeam');
      const label = button.querySelector('[data-member-label]');
      label.dataset.i18n = key;
      label.textContent = translate(key);
      if (isFavorite) button.querySelector('[aria-hidden]').textContent = desired ? '★' : '☆';
      notify(translate(isFavorite ? (desired ? 'favoriteAdded' : 'favoriteRemoved') : (desired ? 'subscriptionAdded' : 'subscriptionRemoved')));
      if (location.pathname === '/profile/saved') {
        // Refresh server-rendered empty states and the combined schedule.
        location.reload();
      }
    } catch (_) {
      notify(translate('connectionError'));
    } finally {
      button.disabled = false;
    }
  });
})();
