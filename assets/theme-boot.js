(() => {
  document.documentElement.classList.add('js');
  try {
    if (window.localStorage.getItem('claudiuschuster-design-world') === 'prismatic') {
      document.documentElement.dataset.world = 'prismatic';
      document.querySelector('#world-theme').href = 'concepts/prismatic/prismatic.css';
    }
  } catch (_) {
    // Data Flow Atelier remains the safe default when storage is unavailable.
  }
})();
