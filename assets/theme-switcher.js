(() => {
  let initialized = false;

  function setupHeaderScroll() {
    if (initialized) return;
    const header = document.querySelector('.site-header');
    if (!header) return;
    initialized = true;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let framePending = false;

    function updateHeader() {
      const scrollY = Math.max(window.scrollY, 0);
      const progress = Math.min(scrollY / 180, 1);
      header.classList.toggle('is-scrolled', scrollY > 24);
      header.style.setProperty('--header-scale', (1 - progress * 0.025).toFixed(3));
      header.style.setProperty('--header-lift', `${(progress * 0.15).toFixed(3)}rem`);
      framePending = false;
    }

    function requestHeaderUpdate() {
      if (framePending) return;
      framePending = true;
      window.requestAnimationFrame(updateHeader);
    }

    header.style.setProperty('--header-scale', '1');
    header.style.setProperty('--header-lift', '0rem');
    window.addEventListener('scroll', requestHeaderUpdate, { passive: true });
    reducedMotion.addEventListener('change', requestHeaderUpdate);
    updateHeader();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupHeaderScroll, { once: true });
    window.addEventListener('load', setupHeaderScroll, { once: true });
  } else {
    setupHeaderScroll();
  }
})();

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
      href: 'assets/atelier.css',
      title: 'Claudiu Schuster — Feel the data flow ...',
      description: {
        de: 'Claudiu Schuster verbindet Cloud, Automation und Open Source mit technischer Tiefe und menschlicher Neugier.',
        en: 'Claudiu Schuster connects cloud, automation and open source with technical depth and human curiosity.',
      },
      status: { de: 'Data Flow Atelier aktiv.', en: 'Data Flow Atelier active.' },
      themeColor: '#090711',
    },
    prismatic: {
      href: 'assets/prismatic.css',
      title: 'Claudiu Schuster — Feel the data flow ...',
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
    if (!root.hasAttribute('data-static-meta')) {
      document.title = worldTitle(world);
      if (description) description.content = world.description[locale];
    }
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

(() => {
  const languageLinks = document.querySelectorAll('.language-link');
  if (!languageLinks.length) return;

  const storageKey = 'claudiuschuster-language-scroll-position';
  const sectionSelector = 'main > section';
  let restoreScheduled = false;

  function sectionName(section) {
    return section.id || 'hero';
  }

  function sectionTop(section) {
    return section.getBoundingClientRect().top + window.scrollY;
  }

  function viewportFocusOffset() {
    const header = document.querySelector('.site-header');
    const headerHeight = header?.offsetHeight || 0;
    return headerHeight + Math.max(0, window.innerHeight - headerHeight) * 0.4;
  }

  function currentPosition() {
    const sections = Array.from(document.querySelectorAll(sectionSelector));
    if (!sections.length) return null;

    const focusOffset = viewportFocusOffset();
    const focusLine = window.scrollY + focusOffset;
    let current = sections[0];
    for (const section of sections) {
      if (sectionTop(section) > focusLine) break;
      current = section;
    }

    return {
      section: sectionName(current),
      offset: Math.max(0, focusLine - sectionTop(current)),
    };
  }

  function savePosition(event) {
    if (event.defaultPrevented
      || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

    const position = currentPosition();
    if (!position) return;

    try {
      const targetPath = new URL(event.currentTarget.href, document.baseURI).pathname;
      sessionStorage.setItem(storageKey, JSON.stringify({
        targetPath,
        ...position,
        savedAt: Date.now(),
      }));
    } catch (_) {
      // The language switch still works when session storage is unavailable.
    }
  }

  function restorePosition() {
    if (restoreScheduled) return;

    let saved;
    try {
      const raw = sessionStorage.getItem(storageKey);
      if (!raw) return;
      saved = JSON.parse(raw);
      if (!saved.savedAt || Date.now() - saved.savedAt > 30000) {
        sessionStorage.removeItem(storageKey);
        return;
      }
    } catch (_) {
      try {
        sessionStorage.removeItem(storageKey);
      } catch (__) {
        // Ignore storage failures and keep the normal page load intact.
      }
      return;
    }

    if (saved.targetPath !== window.location.pathname) return;

    const offset = Number(saved.offset);
    const targetSection = Array.from(document.querySelectorAll(sectionSelector))
      .find((section) => sectionName(section) === saved.section);
    if (!targetSection || !Number.isFinite(offset) || offset < 0) {
      try {
        sessionStorage.removeItem(storageKey);
      } catch (_) {
        // Ignore storage failures and keep the normal page load intact.
      }
      return;
    }

    restoreScheduled = true;
    try {
      sessionStorage.removeItem(storageKey);
    } catch (_) {
      // The position has already been validated; continue without storage.
    }

    const restore = () => {
      const maxScroll = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
      const targetY = Math.min(
        Math.max(0, sectionTop(targetSection) + offset - viewportFocusOffset()),
        maxScroll,
      );
      window.scrollTo(0, targetY);
    };
    window.requestAnimationFrame(() => window.requestAnimationFrame(restore));
  }

  languageLinks.forEach((link) => link.addEventListener('click', savePosition));
  window.addEventListener('pageshow', restorePosition, { once: true });
  if (document.readyState === 'complete') restorePosition();
})();

(() => {
  const root = document.documentElement;
  const canvas = document.querySelector('.flow-canvas');
  if (!canvas) return;

  const paths = Array.from(canvas.querySelectorAll('.flow-line'));
  const nodes = Array.from(canvas.querySelectorAll('.flow-node'));
  const tags = Array.from(canvas.querySelectorAll('.signal-tag'));
  const core = canvas.querySelector('.signal-core');
  if (paths.length !== 2 || nodes.length < 4 || tags.length !== 4 || !core) return;

  const originalNodeCount = nodes.length;
  const svg = canvas.querySelector('svg');
  while (nodes.length < 8) {
    const node = nodes[nodes.length % originalNodeCount].cloneNode(false);
    svg.appendChild(node);
    nodes.push(node);
  }

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const localPreview = ['127.0.0.1', 'localhost'].includes(window.location.hostname);
  const previewQuery = localPreview ? new URLSearchParams(window.location.search) : null;
  const requestedVariant = previewQuery?.get('motion');
  const requestedAtelierNodes = previewQuery?.get('atelier-nodes');
  const requestedSurface = previewQuery?.get('surface');
  const requestedLineColor = previewQuery?.get('line-color');
  const variant = ['halo', 'weave', 'orbit'].includes(requestedVariant) ? requestedVariant : 'orbit';
  const atelierNodeVariant = ['glimmer', 'aurora', 'spark'].includes(requestedAtelierNodes)
    ? requestedAtelierNodes
    : 'aurora';
  const surfaceVariant = ['calm', 'vivid'].includes(requestedSurface) ? requestedSurface : 'vivid';
  const lineColorVariant = ['ink', 'rainbow', 'frame'].includes(requestedLineColor)
    ? requestedLineColor
    : 'frame';
  const shapeSpectrum = document.createElement('div');
  const shapeStripes = document.createElement('div');
  shapeSpectrum.className = 'flow-shape flow-shape-spectrum';
  shapeStripes.className = 'flow-shape flow-shape-stripes';
  canvas.insertBefore(shapeSpectrum, core);
  canvas.insertBefore(shapeStripes, core);
  canvas.classList.add('flow-canvas--interactive');
  canvas.dataset.flowVariant = variant;
  canvas.dataset.atelierNodes = atelierNodeVariant;
  canvas.dataset.surfaceVariant = surfaceVariant;
  canvas.dataset.lineColor = lineColorVariant;

  const svgNamespace = 'http://www.w3.org/2000/svg';
  const definitions = svg.querySelector('defs') || svg.insertBefore(
    document.createElementNS(svgNamespace, 'defs'),
    svg.firstChild,
  );
  const lineGradients = paths.map((_, index) => {
    const gradient = document.createElementNS(svgNamespace, 'linearGradient');
    gradient.id = `flowFrameGradient${index + 1}`;
    gradient.setAttribute('gradientUnits', 'userSpaceOnUse');
    const stops = [0, 0.5, 1].map((offset) => {
      const stop = document.createElementNS(svgNamespace, 'stop');
      stop.setAttribute('offset', String(offset));
      gradient.appendChild(stop);
      return stop;
    });
    definitions.appendChild(gradient);
    return { gradient, stops };
  });
  const linePalettes = [null, null];
  const markerPhases = [0.06, 0.16, 0.31, 0.42, 0.57, 0.68, 0.82, 0.93];
  const startTime = window.performance.now();
  let inView = true;
  let framePending = false;
  let lastDraw = 0;

  function transformState(element) {
    const transform = window.getComputedStyle(element).transform;
    if (!transform || transform === 'none') return { x: 0, y: 0, rotation: 0 };
    try {
      const matrix = new DOMMatrixReadOnly(transform);
      return {
        x: matrix.m41,
        y: matrix.m42,
        rotation: Math.atan2(matrix.m12, matrix.m11) * 180 / Math.PI,
      };
    } catch (_) {
      return { x: 0, y: 0, rotation: 0 };
    }
  }

  function elementRect(element, scaleX, scaleY) {
    const transform = transformState(element);
    return {
      x: (element.offsetLeft + element.offsetWidth / 2 + transform.x) * scaleX,
      y: (element.offsetTop + element.offsetHeight / 2 + transform.y) * scaleY,
      width: element.offsetWidth * scaleX,
      height: element.offsetHeight * scaleY,
      rotation: transform.rotation,
    };
  }

  function routePath(startRect, endRect, coreRect, side, wave) {
    const verticalRoute = side === 'above' || side === 'below';
    const direction = side === 'above' || side === 'left' ? -1 : 1;
    const clearance = variant === 'halo' ? 38 : 28;
    const reachX = coreRect.width / 2 + 42;
    const reachY = coreRect.height / 2 + 42;
    const axisWave = wave * 0.55;
    const axis = verticalRoute
      ? coreRect.y + direction * (coreRect.height / 2 + clearance) + axisWave
      : coreRect.x + direction * (coreRect.width / 2 + clearance) + axisWave;
    const waypoints = verticalRoute
      ? [
          { x: coreRect.x - reachX, y: axis },
          { x: coreRect.x + wave * 0.75, y: axis },
          { x: coreRect.x + reachX, y: axis },
        ]
      : [
          { x: axis, y: coreRect.y - reachY },
          { x: axis, y: coreRect.y + wave * 0.75 },
          { x: axis, y: coreRect.y + reachY },
        ];
    // Bury both endpoints beneath their boxes. The higher stacking layer clips
    // the excess line visually, so contact survives rotation and responsive scaling.
    const start = { x: startRect.x, y: startRect.y };
    const end = { x: endRect.x, y: endRect.y };
    const points = [start, ...waypoints, end];
    let data = `M${start.x.toFixed(2)} ${start.y.toFixed(2)}`;
    for (let index = 0; index < points.length - 1; index += 1) {
      const previous = points[Math.max(0, index - 1)];
      const current = points[index];
      const next = points[index + 1];
      const after = points[Math.min(points.length - 1, index + 2)];
      const controlOne = {
        x: current.x + (next.x - previous.x) / 6,
        y: current.y + (next.y - previous.y) / 6,
      };
      const controlTwo = {
        x: next.x - (after.x - current.x) / 6,
        y: next.y - (after.y - current.y) / 6,
      };
      data += ` C${controlOne.x.toFixed(2)} ${controlOne.y.toFixed(2)} ${controlTwo.x.toFixed(2)} ${controlTwo.y.toFixed(2)} ${next.x.toFixed(2)} ${next.y.toFixed(2)}`;
    }
    return data;
  }

  function tangentPath(points, tangents) {
    let data = `M${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;
    for (let index = 0; index < points.length - 1; index += 1) {
      const current = points[index];
      const next = points[index + 1];
      const currentTangent = tangents[index];
      const nextTangent = tangents[index + 1];
      data += ` C${(current.x + currentTangent.x).toFixed(2)} ${(current.y + currentTangent.y).toFixed(2)} ${(next.x - nextTangent.x).toFixed(2)} ${(next.y - nextTangent.y).toFixed(2)} ${next.x.toFixed(2)} ${next.y.toFixed(2)}`;
    }
    return data;
  }

  function framePoint(distance) {
    const perimeter = 2400;
    const position = ((distance % perimeter) + perimeter) % perimeter;
    if (position < 600) return { x: position, y: 0 };
    if (position < 1200) return { x: 600, y: position - 600 };
    if (position < 1800) return { x: 1800 - position, y: 600 };
    return { x: 0, y: 2400 - position };
  }

  function circlePoint(angleDegrees, radius = 340) {
    const angle = angleDegrees / 180 * Math.PI;
    return {
      x: 300 + Math.cos(angle) * radius,
      y: 300 + Math.sin(angle) * radius,
    };
  }

  function frameTangent(point, entering) {
    const reach = 92;
    if (point.y === 0) return { x: 0, y: entering ? reach : -reach };
    if (point.x === 600) return { x: entering ? -reach : reach, y: 0 };
    if (point.y === 600) return { x: 0, y: entering ? -reach : reach };
    return { x: entering ? reach : -reach, y: 0 };
  }

  function tangentToward(from, to, reach = 92) {
    const x = to.x - from.x;
    const y = to.y - from.y;
    const length = Math.hypot(x, y) || 1;
    return { x: x / length * reach, y: y / length * reach };
  }

  function prismaticPath(index, edgeDrift, wave, elapsedSeconds, moving, profileRect) {
    if (variant === 'halo') {
      return index === 0
        ? `M0 ${(430 + edgeDrift).toFixed(2)} C115 ${(420 + wave * 0.45).toFixed(2)} 82 ${(238 - wave).toFixed(2)} 270 ${(188 + wave * 0.35).toFixed(2)} C390 ${(158 + wave * 0.5).toFixed(2)} 452 ${(468 - wave * 0.7).toFixed(2)} 600 ${(315 - edgeDrift).toFixed(2)}`
        : `M0 ${(185 - edgeDrift).toFixed(2)} C132 ${(264 + wave * 0.55).toFixed(2)} 182 ${(72 - wave * 0.8).toFixed(2)} 330 ${(122 + wave * 0.4).toFixed(2)} C452 ${(176 - wave * 0.45).toFixed(2)} 420 ${(418 + wave * 0.75).toFixed(2)} 600 ${(458 + edgeDrift).toFixed(2)}`;
    }
    if (variant === 'weave') {
      return index === 0
        ? `M0 ${(365 + edgeDrift).toFixed(2)} C126 ${(330 + wave).toFixed(2)} 112 ${(92 - wave * 0.7).toFixed(2)} 292 ${(142 + wave * 0.35).toFixed(2)} C455 ${(198 - wave * 0.5).toFixed(2)} 430 ${(486 + wave * 0.8).toFixed(2)} 600 ${(402 - edgeDrift).toFixed(2)}`
        : `M0 ${(188 - edgeDrift).toFixed(2)} C158 ${(112 - wave * 0.7).toFixed(2)} 162 ${(410 + wave).toFixed(2)} 310 ${(438 - wave * 0.35).toFixed(2)} C450 ${(465 + wave * 0.45).toFixed(2)} 475 ${(170 - wave * 0.8).toFixed(2)} 600 ${(220 + edgeDrift).toFixed(2)}`;
    }
    const noise = (seed, amplitude, period) => moving * flowingNoise(seed, elapsedSeconds, period) * amplitude;
    const above = index === 0;
    const clearance = 34;
    const leftGateX = Math.max(135, profileRect.x - profileRect.width / 2 - clearance);
    const rightGateX = Math.min(465, profileRect.x + profileRect.width / 2 + clearance);
    const corridorY = above
      ? Math.max(54, profileRect.y - profileRect.height / 2 - clearance)
      : Math.min(546, profileRect.y + profileRect.height / 2 + clearance);
    // Choose endpoints as a compatible pair. The second endpoint inherits a
    // generous perimeter span from the first, so crossing a frame corner never
    // creates a short hairpin back toward the same side.
    const startDistance = (above ? 2250 : 1950)
      + noise(2003 + index * 101, above ? 330 : 300, 9.7 + index * 0.8);
    const rawSpan = 800 + noise(2039 + index * 103, 180, 10.4 + index * 0.9);
    const span = above
      ? Math.min(rawSpan, 3350 - startDistance)
      : Math.max(rawSpan, startDistance - 1420);
    const endDistance = above ? startDistance + span : startDistance - span;
    const start = framePoint(startDistance);
    const end = framePoint(endDistance);
    const sideDirection = above ? -1 : 1;
    const leftGate = { x: leftGateX, y: corridorY };
    const rightGate = { x: rightGateX, y: corridorY };
    const center = {
      x: (leftGateX + rightGateX) / 2 + noise(1871 + index * 227, 26, 6.2),
      y: Math.max(28, Math.min(572, corridorY + sideDirection * (62 + noise(1973 + index * 229, 30, 6.8)))),
    };
    const points = [start, leftGate, center, rightGate, end];
    const tangents = [
      tangentToward(start, leftGate),
      { x: 54, y: 0 },
      { x: 48, y: 0 },
      { x: 54, y: 0 },
      tangentToward(rightGate, end),
    ];
    return tangentPath(points, tangents);
  }

  function placeShape(element, x, y, rotation, canvasWidth, canvasHeight) {
    const xPixels = x / 600 * canvasWidth - element.offsetWidth / 2;
    const yPixels = y / 600 * canvasHeight - element.offsetHeight / 2;
    element.style.transform = `translate3d(${xPixels.toFixed(2)}px, ${yPixels.toFixed(2)}px, 0) rotate(${rotation.toFixed(2)}deg)`;
  }

  function randomUnit(seed) {
    let value = seed | 0;
    value ^= value >>> 16;
    value = Math.imul(value, 0x7feb352d);
    value ^= value >>> 15;
    value = Math.imul(value, 0x846ca68b);
    value ^= value >>> 16;
    return (value >>> 0) / 4294967295 * 2 - 1;
  }

  function smoothNoise(seed, elapsedSeconds, period) {
    const position = elapsedSeconds / period;
    const step = Math.floor(position);
    const fraction = position - step;
    const eased = fraction * fraction * (3 - 2 * fraction);
    const from = randomUnit(seed + step * 1013);
    const to = randomUnit(seed + (step + 1) * 1013);
    return from + (to - from) * eased;
  }

  function flowingNoise(seed, elapsedSeconds, period) {
    const phaseOne = (randomUnit(seed) + 1) * Math.PI;
    const phaseTwo = (randomUnit(seed + 431) + 1) * Math.PI;
    const phaseThree = (randomUnit(seed + 887) + 1) * Math.PI;
    return Math.sin(elapsedSeconds / period * Math.PI * 2 + phaseOne) * 0.58
      + Math.sin(elapsedSeconds / (period * 1.71) * Math.PI * 2 + phaseTwo) * 0.28
      + Math.sin(elapsedSeconds / (period * 2.63) * Math.PI * 2 + phaseThree) * 0.14;
  }

  function hslColor(hue, saturation = 92, lightness = 62, alpha = 1) {
    const normalizedHue = ((hue % 360) + 360) % 360;
    return alpha === 1
      ? `hsl(${normalizedHue.toFixed(1)} ${saturation}% ${lightness}%)`
      : `hsl(${normalizedHue.toFixed(1)} ${saturation}% ${lightness}% / ${alpha})`;
  }

  function interpolateHue(from, to, progress) {
    const distance = ((to - from + 540) % 360) - 180;
    return from + distance * progress;
  }

  function paletteHueAt(palette, progress) {
    if (!palette) return progress * 360;
    if (progress <= 0.5) return interpolateHue(palette[0], palette[1], progress * 2);
    return interpolateHue(palette[1], palette[2], (progress - 0.5) * 2);
  }

  function frameDistance(point) {
    if (Math.abs(point.y) < 0.25) return point.x;
    if (Math.abs(point.x - 600) < 0.25) return 600 + point.y;
    if (Math.abs(point.y - 600) < 0.25) return 1800 - point.x;
    return 2400 - point.y;
  }

  function updateLineColors(world) {
    paths.forEach((path, index) => {
      if (world !== 'prismatic' || lineColorVariant === 'ink') {
        path.style.removeProperty('stroke');
        path.style.removeProperty('filter');
        linePalettes[index] = null;
        return;
      }

      const length = path.getTotalLength();
      const start = path.getPointAtLength(0);
      const end = path.getPointAtLength(length);
      let startHue;
      let middleHue;
      let endHue;

      if (lineColorVariant === 'rainbow') {
        startHue = 15 + index * 145;
        middleHue = startHue + 175;
        endHue = startHue + 335;
      } else {
        startHue = 278 + frameDistance(start) / 2400 * 360;
        endHue = 278 + frameDistance(end) / 2400 * 360;
        const frameSweep = (endHue - startHue + 360) % 360;
        middleHue = startHue + frameSweep / 2 + (index === 0 ? 34 : -34);
      }

      const { gradient, stops } = lineGradients[index];
      gradient.setAttribute('x1', start.x.toFixed(2));
      gradient.setAttribute('y1', start.y.toFixed(2));
      gradient.setAttribute('x2', end.x.toFixed(2));
      gradient.setAttribute('y2', end.y.toFixed(2));
      [startHue, middleHue, endHue].forEach((hue, stopIndex) => {
        stops[stopIndex].setAttribute('stop-color', hslColor(hue));
      });
      path.style.stroke = `url(#${gradient.id})`;
      path.style.filter = `drop-shadow(0 0 2.5px ${hslColor(middleHue, 92, 62, 0.42)})`;
      linePalettes[index] = [startHue, middleHue, endHue];
    });
  }

  function updateMarkers(elapsedSeconds) {
    const world = root.dataset.world || 'atelier';
    const atelierPalettes = [[174, 34, 333], [265, 34, 174]];
    nodes.forEach((node, index) => {
      const pathIndex = index % paths.length;
      const path = paths[pathIndex];
      const length = path.getTotalLength();
      const speedBase = variant === 'halo'
        ? 19
        : variant === 'weave'
          ? 12
          : world === 'atelier'
            ? 52
            : 34;
      const speedOffset = variant === 'orbit' ? (world === 'atelier' ? 8 : 6) : 3;
      const speed = speedBase + (index % 2 === 0 ? 0 : speedOffset);
      const progress = reducedMotion.matches
        ? markerPhases[index % markerPhases.length]
        : (markerPhases[index % markerPhases.length] + elapsedSeconds / speed) % 1;
      const point = path.getPointAtLength(length * progress);
      node.setAttribute('cx', point.x.toFixed(2));
      node.setAttribute('cy', point.y.toFixed(2));

      if (world === 'prismatic') {
        const randomHueStart = (randomUnit(3109 + index * 137) + 1) * 180;
        const hue = randomHueStart
          + progress * 360
          + (reducedMotion.matches ? 0 : elapsedSeconds * 11);
        const color = hslColor(hue);
        node.setAttribute('r', '4');
        node.style.fill = color;
        node.style.opacity = '1';
        node.style.filter = `drop-shadow(0 0 5px ${color})`;
        return;
      }

      const phaseTime = reducedMotion.matches ? index * 0.7 : elapsedSeconds * 0.72 + index * 0.7;
      const pulse = (Math.sin(progress * Math.PI * 4 + phaseTime) + 1) / 2;
      let hue = 34;
      let radius = 3.6 + pulse * 1.05;
      let opacity = 0.76 + pulse * 0.24;
      let glow = 4 + pulse * 8;

      if (atelierNodeVariant !== 'glimmer') {
        const randomHueStart = (randomUnit(4219 + index * 173) + 1) * 180;
        hue = randomHueStart
          + progress * 360
          + (reducedMotion.matches ? 0 : elapsedSeconds * 8);
      }
      if (atelierNodeVariant === 'aurora') {
        radius = 3.8 + pulse * 0.7;
        glow = 6 + pulse * 7;
      } else if (atelierNodeVariant === 'spark') {
        const spark = pulse ** 3;
        radius = 3.25 + spark * 2.15;
        opacity = 0.58 + spark * 0.42;
        glow = 4 + spark * 14;
      }

      const color = hslColor(hue, atelierNodeVariant === 'glimmer' ? 84 : 72, 72);
      node.setAttribute('r', radius.toFixed(2));
      node.style.fill = color;
      node.style.opacity = opacity.toFixed(2);
      node.style.filter = `drop-shadow(0 0 ${glow.toFixed(1)}px ${color})`;
    });
  }

  function draw(now) {
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (!width || !height) return;

    const scaleX = 600 / width;
    const scaleY = 600 / height;
    const elapsedSeconds = (now - startTime) / 1000;
    const moving = reducedMotion.matches ? 0 : 1;
    const world = root.dataset.world || 'atelier';
    const lineElapsedSeconds = variant === 'orbit'
      ? elapsedSeconds * (world === 'atelier' ? 0.15 : 0.2)
      : elapsedSeconds;
    const profileRect = elementRect(core, scaleX, scaleY);
    const coreRect = { ...profileRect };
    coreRect.width += 58;
    coreRect.height += 58;

    let startOne;
    let endOne;
    let startTwo;
    let endTwo;
    let sideOne;
    let sideTwo;

    if (world === 'prismatic') {
      const colorCycle = Math.floor(lineElapsedSeconds / 9.5);
      const colorsSwapped = variant === 'orbit'
        && moving
        && randomUnit(2309 + colorCycle * 1013) >= 0;
      canvas.dataset.flowColors = colorsSwapped ? 'swapped' : 'native';
      const drift = variant === 'halo' ? 0.72 : variant === 'weave' ? 1.35 : 1;
      const spectrumX = 468 + moving * smoothNoise(701, elapsedSeconds, 6.3) * 10 * drift;
      const spectrumY = 142 + moving * smoothNoise(733, elapsedSeconds, 7.1) * 9 * drift;
      const stripesX = 112 + moving * smoothNoise(809, elapsedSeconds, 6.8) * 9 * drift;
      const stripesY = 430 + moving * smoothNoise(853, elapsedSeconds, 7.6) * 11 * drift;
      const rotationDrift = variant === 'weave' ? 2.8 : variant === 'orbit' ? 2.2 : 1.3;
      const spectrumRotation = 12 + moving * smoothNoise(907, elapsedSeconds, 8.2) * rotationDrift;
      const stripesRotation = -8 + moving * smoothNoise(953, elapsedSeconds, 8.7) * rotationDrift;
      placeShape(shapeSpectrum, spectrumX, spectrumY, spectrumRotation, width, height);
      placeShape(shapeStripes, stripesX, stripesY, stripesRotation, width, height);

      const surfaceEnergy = surfaceVariant === 'vivid' ? 1.75 : 1;
      const surfaceTime = moving * elapsedSeconds;
      const stripePeriod = 20.8;
      const stripeBand = stripePeriod / 2;
      // Keep the first repeated tile entirely before the visible origin. This
      // preserves the diagonal travel while preventing a finite-gradient seam
      // from sliding in across the shape from its left edge.
      const stripePhase = (surfaceTime * 1.15 * surfaceEnergy) % stripePeriod - stripePeriod;
      const spectrumCenterX = 50 + moving * smoothNoise(2603, elapsedSeconds, 11.8) * 7 * surfaceEnergy;
      const spectrumCenterY = 50 + moving * smoothNoise(2633, elapsedSeconds, 13.1) * 6.5 * surfaceEnergy;
      const spectrumAngle = 35
        + surfaceTime * 3.1 * surfaceEnergy
        + moving * smoothNoise(2671, elapsedSeconds, 10.6) * 9 * surfaceEnergy;
      const wedgePulse = moving * smoothNoise(2711, elapsedSeconds, 7.9) * 18 * surfaceEnergy;
      const yellowStop = 82 + wedgePulse;
      const tealStop = 174 - wedgePulse * 0.42;
      const violetStop = 270 + wedgePulse * 0.6;
      shapeStripes.style.background = `repeating-linear-gradient(-45deg, #17131c ${stripePhase.toFixed(2)}px ${(stripePhase + stripeBand).toFixed(2)}px, #62e9dd ${(stripePhase + stripeBand).toFixed(2)}px ${(stripePhase + stripePeriod).toFixed(2)}px)`;
      shapeSpectrum.style.background = `conic-gradient(from ${spectrumAngle.toFixed(2)}deg at ${spectrumCenterX.toFixed(2)}% ${spectrumCenterY.toFixed(2)}%, #ff3f9b 0deg, #ffdf4e ${yellowStop.toFixed(2)}deg, #62e9dd ${tealStop.toFixed(2)}deg, #a980ff ${violetStop.toFixed(2)}deg, #ff3f9b 360deg)`;
    } else {
      canvas.dataset.flowColors = 'native';
    }

    const edgeDrift = moving * smoothNoise(1103, elapsedSeconds, 5.9) * 16;
    if (variant === 'halo') {
      startOne = { x: 0, y: 205 + edgeDrift };
      endOne = { x: 600, y: 205 - edgeDrift };
      startTwo = { x: 0, y: 425 - edgeDrift };
      endTwo = { x: 600, y: 425 + edgeDrift };
      [sideOne, sideTwo] = ['above', 'below'];
    } else if (variant === 'orbit' && world === 'atelier') {
      const perimeterDrift = moving * flowingNoise(3301, lineElapsedSeconds, 8.8) * 68;
      const counterDrift = moving * flowingNoise(3371, lineElapsedSeconds, 10.7) * 24;
      startOne = circlePoint(200 + perimeterDrift);
      endOne = circlePoint(40 + perimeterDrift + counterDrift);
      startTwo = circlePoint(160 - perimeterDrift + counterDrift);
      endTwo = circlePoint(320 - perimeterDrift);
      [sideOne, sideTwo] = ['above', 'below'];
    } else if (variant === 'orbit') {
      startOne = { x: 185 + edgeDrift, y: 0 };
      endOne = { x: 185 - edgeDrift, y: 600 };
      startTwo = { x: 415 - edgeDrift, y: 0 };
      endTwo = { x: 415 + edgeDrift, y: 600 };
      [sideOne, sideTwo] = ['left', 'right'];
    } else {
      startOne = { x: 0, y: 150 + edgeDrift };
      endOne = { x: 600, y: 445 - edgeDrift };
      startTwo = { x: 0, y: 445 - edgeDrift };
      endTwo = { x: 600, y: 150 + edgeDrift };
      [sideOne, sideTwo] = ['above', 'below'];
    }

    const waveAmplitude = variant === 'halo'
      ? 10
      : variant === 'weave'
        ? 24
        : world === 'atelier'
          ? 32
          : 16;
    const waveOne = moving * smoothNoise(1201, elapsedSeconds, 5.1) * waveAmplitude;
    const waveTwo = moving * smoothNoise(1301, elapsedSeconds, 5.6) * waveAmplitude;
    if (world === 'prismatic') {
      paths[0].setAttribute('d', prismaticPath(0, edgeDrift, waveOne, lineElapsedSeconds, moving, profileRect));
      paths[1].setAttribute('d', prismaticPath(1, edgeDrift, waveTwo, lineElapsedSeconds, moving, profileRect));
    } else {
      paths[0].setAttribute('d', routePath(startOne, endOne, coreRect, sideOne, waveOne));
      paths[1].setAttribute('d', routePath(startTwo, endTwo, coreRect, sideTwo, waveTwo));
    }
    updateLineColors(world);
    updateMarkers(elapsedSeconds);
    canvas.dataset.flowMotion = reducedMotion.matches ? 'resting' : 'active';
  }

  function scheduleFrame() {
    if (framePending || !inView || document.hidden) return;
    framePending = true;
    window.requestAnimationFrame((now) => {
      framePending = false;
      if (now - lastDraw < 30 && !reducedMotion.matches) {
        scheduleFrame();
        return;
      }
      lastDraw = now;
      draw(now);
      if (!reducedMotion.matches) scheduleFrame();
    });
  }

  const observer = new IntersectionObserver((entries) => {
    inView = entries[0]?.isIntersecting ?? true;
    if (inView) scheduleFrame();
  }, { rootMargin: '120px' });
  observer.observe(canvas);

  const resizeObserver = new ResizeObserver(scheduleFrame);
  resizeObserver.observe(canvas);

  const worldObserver = new MutationObserver(scheduleFrame);
  worldObserver.observe(root, { attributes: true, attributeFilter: ['data-world'] });

  reducedMotion.addEventListener('change', scheduleFrame);
  document.addEventListener('visibilitychange', scheduleFrame);
  scheduleFrame();
})();
