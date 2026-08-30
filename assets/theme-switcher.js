(() => {
  const root = document.documentElement;
  const stylesheet = document.querySelector('#world-theme');
  const controls = document.querySelectorAll('[data-world-target]');
  const liveRegion = document.querySelector('#world-status');
  const description = document.querySelector('meta[name="description"]');
  const themeColor = document.querySelector('#theme-color');
  const locale = root.lang === 'en' ? 'en' : 'de';
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const storageKey = 'claudiuschuster-design-world';
  let busy = false;

  const worlds = {
    atelier: {
      href: 'concepts/atelier/atelier.css',
      title: 'Claudiu Schuster — Feel the data flow',
      description: {
        de: 'Claudiu Schuster verbindet Cloud, Automation und Open Source mit technischer Tiefe und menschlicher Neugier.',
        en: 'Claudiu Schuster connects cloud, automation and open source with technical depth and human curiosity.',
      },
      status: { de: 'Data Flow Atelier aktiv.', en: 'Data Flow Atelier active.' },
      themeColor: '#090711',
    },
    prismatic: {
      href: 'concepts/prismatic/prismatic.css',
      title: {
        de: 'Claudiu Schuster — Neugier, die liefert',
        en: 'Claudiu Schuster — Curiosity that ships',
      },
      description: {
        de: 'Claudiu Schuster macht aus technischer Neugier robuste Cloud-, Automation- und Open-Source-Systeme.',
        en: 'Claudiu Schuster turns technical curiosity into robust cloud, automation and open-source systems.',
      },
      status: { de: 'Prismatic Workshop aktiv.', en: 'Prismatic Workshop active.' },
      themeColor: '#f3efe6',
    },
  };

  function worldTitle(world) {
    return typeof world.title === 'string' ? world.title : world.title[locale];
  }

  function updateDocument(worldName, announce = false) {
    const world = worlds[worldName];
    document.title = worldTitle(world);
    if (description) description.content = world.description[locale];
    if (themeColor) themeColor.content = world.themeColor;
    controls.forEach((control) => {
      const isPrismatic = worldName === 'prismatic';
      control.setAttribute('aria-checked', String(isPrismatic));
    });
    if (announce && liveRegion) liveRegion.textContent = world.status[locale];
  }

  function loadStylesheet(worldName) {
    return new Promise((resolve, reject) => {
      const world = worlds[worldName];
      const nextHref = new URL(world.href, document.baseURI).href;
      if (stylesheet.href === nextHref) {
        resolve();
        return;
      }
      const timeout = window.setTimeout(() => reject(new Error('Theme stylesheet timed out.')), 5000);
      stylesheet.addEventListener('load', () => {
        window.clearTimeout(timeout);
        resolve();
      }, { once: true });
      stylesheet.addEventListener('error', () => {
        window.clearTimeout(timeout);
        reject(new Error('Theme stylesheet failed to load.'));
      }, { once: true });
      stylesheet.href = world.href;
    });
  }

  async function activate(worldName) {
    if (busy || !worlds[worldName] || root.dataset.world === worldName) return;
    busy = true;
    root.classList.add('world-switching');
    controls.forEach((control) => { control.disabled = true; });

    try {
      await loadStylesheet(worldName);
      root.dataset.world = worldName;
      updateDocument(worldName, true);
      try {
        window.localStorage.setItem(storageKey, worldName);
      } catch (_) {
        // The design switch still works when storage is unavailable.
      }
    } catch (error) {
      console.error(error);
    } finally {
      const delay = reducedMotion.matches ? 0 : 620;
      window.setTimeout(() => {
        root.classList.remove('world-switching');
        controls.forEach((control) => { control.disabled = false; });
        busy = false;
      }, delay);
    }
  }

  controls.forEach((control) => {
    control.addEventListener('click', () => activate(control.dataset.worldTarget));
  });

  updateDocument(root.dataset.world || 'atelier');
})();
