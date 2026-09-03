(() => {
  const root = document.documentElement;
  root.classList.add('js');
  try {
    if (window.localStorage.getItem('claudiuschuster-design-world') === 'prismatic') {
      root.dataset.world = 'prismatic';
      document.querySelector('#world-theme').href = 'assets/prismatic.css';
    }
  } catch (_) {
    // Data Flow Atelier remains the safe default when storage is unavailable.
  }

  if (!root.hasAttribute('data-bilingual')) return;

  const storageKey = 'claudiuschuster-language';
  let requestedLanguage = '';
  try {
    const url = new URL(window.location.href);
    const requested = url.searchParams.get('lang');
    requestedLanguage = requested === 'en' || requested === 'de' ? requested : '';
    if (requestedLanguage) {
      url.searchParams.delete('lang');
      window.history.replaceState(
        window.history.state,
        '',
        `${url.pathname}${url.search}${url.hash}`,
      );
    }
  } catch (_) {
    requestedLanguage = '';
  }

  let storedLanguage = '';
  try {
    storedLanguage = window.sessionStorage.getItem(storageKey) || '';
  } catch (_) {
    storedLanguage = '';
  }

  const language = requestedLanguage || storedLanguage;
  if (language === 'en' || language === 'de') {
    root.lang = language;
    try {
      window.sessionStorage.setItem(storageKey, language);
    } catch (_) {
      // The selected language still applies when storage is unavailable.
    }
  }
})();
