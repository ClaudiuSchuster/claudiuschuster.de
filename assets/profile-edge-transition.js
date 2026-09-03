(() => {
  const cores = [...document.querySelectorAll('.signal-core')];

  if (!cores.length) {
    return;
  }

  const canvas = document.createElement('canvas');
  const size = 128;
  const context = canvas.getContext('2d', { willReadFrequently: false });
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let lastFrameTime = 0;

  canvas.width = size;
  canvas.height = size;

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const smoothStep = (value) => {
    const normalized = clamp(value, 0, 1);

    return normalized * normalized * (3 - 2 * normalized);
  };
  const frameBlend = (x, y, left, right, top, bottom, radius) => {
    const outsideX = Math.max(left - x, 0, x - right);
    const outsideY = Math.max(top - y, 0, y - bottom);
    const outsideDistance = Math.hypot(outsideX, outsideY);

    if (outsideDistance > 0) {
      return smoothStep(-outsideDistance / radius);
    }

    const insideDistance = Math.min(x - left, right - x, y - top, bottom - y);

    return smoothStep(insideDistance / radius);
  };
  const entryCornerGate = (distanceX, distanceY, radius) => {
    const safeRadius = Math.max(radius, 1);
    const transitionRadius = Math.min(1, 4 / safeRadius);
    const normalizedDistance = Math.hypot(
      (distanceX - safeRadius) / safeRadius,
      (distanceY - safeRadius) / safeRadius
    );
    const radialGate = smoothStep((1 - normalizedDistance) / transitionRadius);
    const axisTransition = Math.min(2, safeRadius * 0.25);
    const axisGate = (distance) => smoothStep(
      (distance - safeRadius + axisTransition) / axisTransition
    );
    const edgeGate = 1 - (1 - axisGate(distanceX)) * (1 - axisGate(distanceY));

    return Math.max(radialGate, edgeGate);
  };
  const entryEdgePresence = (position, extent, transition) => {
    const outsideDistance = Math.max(-position, position - extent, 0);

    return 1 - smoothStep(outsideDistance / Math.max(transition, 1));
  };
  const cornerAlpha = (distanceX, distanceY, frameCoverage, radiusX, radiusY) => {
    if (distanceX >= radiusX || distanceY >= radiusY) {
      return 1;
    }

    const transitionRadius = Math.min(1, 4 / Math.max(radiusX, radiusY));
    const normalizedDistance = Math.hypot(
      (distanceX - radiusX) / Math.max(radiusX, 1),
      (distanceY - radiusY) / Math.max(radiusY, 1)
    );
    const arcProgress = smoothStep((1 - normalizedDistance) / transitionRadius);

    return 1 - frameCoverage * (1 - arcProgress);
  };

  const transformValues = (element) => {
    const transform = getComputedStyle(element).transform;

    if (transform === 'none') {
      return { scaleX: 1, scaleY: 1, translateX: 0, translateY: 0 };
    }

    const matrix = new DOMMatrixReadOnly(transform);

    return {
      scaleX: Math.hypot(matrix.a, matrix.b) || 1,
      scaleY: Math.hypot(matrix.c, matrix.d) || 1,
      translateX: matrix.e,
      translateY: matrix.f
    };
  };

  const updateMask = (core) => {
    const image = core.querySelector(':scope > img');
    const frame = core.querySelector(':scope > .signal-shadow-frame');
    const width = core.clientWidth;
    const height = core.clientHeight;

    if (!image || !frame || !width || !height || !context) {
      return;
    }

    const { scaleX, scaleY, translateX, translateY } = transformValues(frame);
    const [originX, originY] = getComputedStyle(frame).transformOrigin
      .split(' ')
      .map(parseFloat);
    const frameWidth = frame.offsetWidth;
    const frameHeight = frame.offsetHeight;
    const frameLeft = frame.offsetLeft + originX + scaleX * (0 - originX) + translateX;
    const frameRight = frame.offsetLeft + originX + scaleX * (frameWidth - originX) + translateX;
    const frameTop = frame.offsetTop + originY + scaleY * (0 - originY) + translateY;
    const frameBottom = frame.offsetTop + originY + scaleY * (frameHeight - originY) + translateY;
    const maxFade = Math.min(16, Math.min(width, height) * 0.1);
    const fadeHandoffDistance = Math.min(4, maxFade);
    const leftProtrusion = Math.max(0, -frameLeft);
    const rightProtrusion = Math.max(0, frameRight - width);
    const topProtrusion = Math.max(0, -frameTop);
    const bottomProtrusion = Math.max(0, frameBottom - height);
    const leftFade = clamp(leftProtrusion, 0, maxFade);
    const rightFade = clamp(rightProtrusion, 0, maxFade);
    const topFade = clamp(topProtrusion, 0, maxFade);
    const bottomFade = clamp(bottomProtrusion, 0, maxFade);
    const leftStrength = smoothStep(leftProtrusion / fadeHandoffDistance);
    const rightStrength = smoothStep(rightProtrusion / fadeHandoffDistance);
    const topStrength = smoothStep(topProtrusion / fadeHandoffDistance);
    const bottomStrength = smoothStep(bottomProtrusion / fadeHandoffDistance);
    const frameEntryRadius = Math.min(2, Math.min(width, height) * 0.015);
    const entryCornerRadius = Math.min(10, Math.min(width, height) * 0.07);
    const entryCornerTransition = Math.min(4, Math.max(1, entryCornerRadius));
    const frameLeftPresence = entryEdgePresence(frameLeft, width, entryCornerTransition);
    const frameRightPresence = entryEdgePresence(frameRight, width, entryCornerTransition);
    const frameTopPresence = entryEdgePresence(frameTop, height, entryCornerTransition);
    const frameBottomPresence = entryEdgePresence(frameBottom, height, entryCornerTransition);
    // Align both upper side-entry gates with the visible frame contact. The
    // previous zero offset kept their rounded handoff about 2px too low.
    const topEntryOffset = -2;
    // Preserve the confirmed R45 top-left local shift while the other five
    // tentative R47 micro-shifts remain out of the active baseline.
    const topLeftEntryShiftX = 1;
    const topLeftEntryShiftY = 1;
    const topRightEntryShiftX = 1; // 1px right at the upper edge.
    const topRightEntryShiftY = 1; // 1px lower at the upper edge.
    const penetratedTopRightLeftEntryShift = frameTop > 0 && frameRight < width ? 2 : 0;
    const bottomRightBottomEntryShiftX = 1; // 1px right at the lower edge.
    const bottomRightBottomEntryShiftY = 1; // 1px higher at the lower edge.
    const bottomRightRightEntryShiftY = 1; // 1px lower at the right edge.
    const pixels = context.createImageData(size, size);

    for (let pixelY = 0; pixelY < size; pixelY += 1) {
      const y = ((pixelY + 0.5) / size) * height;

      for (let pixelX = 0; pixelX < size; pixelX += 1) {
        const x = ((pixelX + 0.5) / size) * width;
        let alpha = 1;
        const frameCoverage = frameBlend(
          x,
          y,
          frameLeft,
          frameRight,
          frameTop,
          frameBottom,
          frameEntryRadius
        );
        let leftFrameCoverage = frameCoverage;
        let rightFrameCoverage = frameCoverage;
        let topFrameCoverage = frameCoverage;
        let bottomFrameCoverage = frameCoverage;

        if (leftFade > 0) {
          const leftTopGate = entryCornerGate(
            leftFade - x,
            y - frameTop - topEntryOffset + penetratedTopRightLeftEntryShift,
            Math.min(leftFade, entryCornerRadius)
          );
          const leftBottomGate = entryCornerGate(
            leftFade - x,
            frameBottom - y,
            Math.min(leftFade, entryCornerRadius)
          );

          leftFrameCoverage *= 1 - frameTopPresence * (1 - leftTopGate);
          leftFrameCoverage *= 1 - frameBottomPresence * (1 - leftBottomGate);
        }

        if (rightFade > 0) {
          const rightTopGate = entryCornerGate(
            x - (width - rightFade),
            y - frameTop - topEntryOffset,
            Math.min(rightFade, entryCornerRadius)
          );
          const rightBottomGate = entryCornerGate(
            x - (width - rightFade),
            frameBottom - y + bottomRightRightEntryShiftY,
            Math.min(rightFade, entryCornerRadius)
          );

          rightFrameCoverage *= 1 - frameTopPresence * (1 - rightTopGate);
          rightFrameCoverage *= 1 - frameBottomPresence * (1 - rightBottomGate);
        }

        if (topFade > 0) {
          const topLeftGate = entryCornerGate(
            x - frameLeft + topLeftEntryShiftX,
            topFade - y + topLeftEntryShiftY,
            Math.min(topFade, entryCornerRadius)
          );
          const topRightGate = entryCornerGate(
            frameRight - x + topRightEntryShiftX,
            topFade - y + topRightEntryShiftY,
            Math.min(topFade, entryCornerRadius)
          );

          topFrameCoverage *= 1 - frameLeftPresence * (1 - topLeftGate);
          topFrameCoverage *= 1 - frameRightPresence * (1 - topRightGate);
        }

        if (bottomFade > 0) {
          const bottomLeftGate = entryCornerGate(
            x - frameLeft,
            y - (height - bottomFade),
            Math.min(bottomFade, entryCornerRadius)
          );
          const bottomRightGate = entryCornerGate(
            frameRight - x + bottomRightBottomEntryShiftX,
            y - (height - bottomFade) + bottomRightBottomEntryShiftY,
            Math.min(bottomFade, entryCornerRadius)
          );

          bottomFrameCoverage *= 1 - frameLeftPresence * (1 - bottomLeftGate);
          bottomFrameCoverage *= 1 - frameRightPresence * (1 - bottomRightGate);
        }

        if (leftFade > 0) {
          alpha *= 1 - leftStrength * leftFrameCoverage * (1 - clamp(x / leftFade, 0, 1));
        }

        if (rightFade > 0) {
          alpha *= 1 - rightStrength * rightFrameCoverage * (1 - clamp((width - x) / rightFade, 0, 1));
        }

        if (topFade > 0) {
          alpha *= 1 - topStrength * topFrameCoverage * (1 - clamp(y / topFade, 0, 1));
        }

        if (bottomFade > 0) {
          alpha *= 1 - bottomStrength * bottomFrameCoverage * (1 - clamp((height - y) / bottomFade, 0, 1));
        }

        if (leftFade > 0 && topFade > 0) {
          alpha = Math.min(alpha, cornerAlpha(x, y, frameCoverage, leftFade, topFade));
        }

        if (rightFade > 0 && topFade > 0) {
          alpha = Math.min(alpha, cornerAlpha(width - x, y, frameCoverage, rightFade, topFade));
        }

        if (leftFade > 0 && bottomFade > 0) {
          alpha = Math.min(alpha, cornerAlpha(x, height - y, frameCoverage, leftFade, bottomFade));
        }

        if (rightFade > 0 && bottomFade > 0) {
          alpha = Math.min(alpha, cornerAlpha(width - x, height - y, frameCoverage, rightFade, bottomFade));
        }

        const index = (pixelY * size + pixelX) * 4;
        pixels.data[index] = 255;
        pixels.data[index + 1] = 255;
        pixels.data[index + 2] = 255;
        pixels.data[index + 3] = Math.round(alpha * 255);
      }
    }

    context.putImageData(pixels, 0, 0);
    core.style.setProperty('--profile-edge-alpha-mask', `url("${canvas.toDataURL('image/png')}")`);
  };

  const updateAll = () => cores.forEach(updateMask);

  const tick = (time) => {
    if (reducedMotion || time - lastFrameTime >= 33) {
      updateAll();
      lastFrameTime = time;
    }

    if (!reducedMotion) {
      window.requestAnimationFrame(tick);
    }
  };

  updateAll();

  if (!reducedMotion) {
    window.requestAnimationFrame(tick);
  }
})();
