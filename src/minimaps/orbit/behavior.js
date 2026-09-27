(function () {
  'use strict';
  /* Orbit map: measured section positions are mapped to equally spaced stops.
     Scroll drives a damped instrument; dragging reverses the same mapping. */
  const navAnchors = [...document.querySelectorAll('.nav-links a[href^="#"]')];
  const orbit = document.querySelector('.orbit');
  if (orbit) {
    const button = orbit.querySelector('.orbit-toggle');
    const panel = document.getElementById('orbitPanel');
    const scrub = orbit.querySelector('.orbit-scrub');
    const stops = [...orbit.querySelectorAll('.orbit-stops a')];
    const targets = stops.map(a => document.getElementById(a.hash.slice(1)));
    const readout = orbit.querySelector('.orbit-label');
    const index = orbit.querySelector('.orbit-index');
    const motion = matchMedia('(prefers-reduced-motion: reduce)');
    let offsets = [], maxScroll = 0, current = 0, preview = null;
    let position = 0, destination = 0, velocity = 0, raf = 0, last = 0;
    let dragging = false;
    const clamp = (n, min, max) => Math.max(min, Math.min(max, n));
    const paint = () => {
      orbit.style.setProperty('--orbit-angle', `${135 + position * 270}deg`);
      orbit.style.setProperty('--orbit-progress', position);
      orbit.style.setProperty('--gyro-angle', `${-position * 180}deg`);
    };
    const animate = time => {
      const dt = Math.min((time - (last || time - 16)) / 1000, .032);
      last = time;
      velocity += ((destination - position) * 150 - velocity * 24) * dt;
      position = clamp(position + velocity * dt, 0, 1);
      if (Math.abs(destination - position) < .0001 && Math.abs(velocity) < .001) {
        position = destination; velocity = 0; raf = 0; last = 0; paint();
      } else { paint(); raf = requestAnimationFrame(animate); }
    };
    const showLabel = () => {
      const i = preview === null ? current : preview;
      readout.textContent = stops[i].dataset.label;
      index.textContent = String(i).padStart(2, '0');
    };
    const update = () => {
      const y = clamp(scrollY, 0, maxScroll);
      let i = 0;
      while (i < offsets.length - 1 && y >= offsets[i + 1] - 1) i++;
      current = i;
      const fraction = i < offsets.length - 1
        ? clamp((y - offsets[i]) / Math.max(1, offsets[i + 1] - offsets[i]), 0, 1) : 0;
      destination = (i + fraction) / (stops.length - 1);
      const pct = maxScroll > 0 ? Math.round(y / maxScroll * 100) : 0;
      orbit.querySelectorAll('.orbit-percent').forEach(el => { el.textContent = `${String(pct).padStart(2, '0')}%`; });
      scrub.setAttribute('aria-valuenow', pct);
      scrub.setAttribute('aria-valuetext', `${pct}% · ${stops[current].dataset.label}`);
      [...stops, ...navAnchors].forEach(a => {
        if (a.hash === stops[current].hash) a.setAttribute('aria-current', 'location');
        else a.removeAttribute('aria-current');
      });
      stops.forEach((a, n) => a.toggleAttribute('data-passed', n < current));
      showLabel();
      if (motion.matches || dragging) {
        cancelAnimationFrame(raf); raf = 0; last = 0; velocity = 0;
        position = destination; paint();
      } else if (!raf) raf = requestAnimationFrame(animate);
    };
    const measure = () => {
      maxScroll = Math.max(0, document.documentElement.scrollHeight - innerHeight);
      // Layout coordinates exclude the section reveal's temporary transform.
      const layoutTop = el => {
        let top = 0;
        for (let node = el; node; node = node.offsetParent) top += node.offsetTop;
        return top;
      };
      offsets = targets.map((el, i) => i === 0 ? 0 : clamp(
        layoutTop(el) - (parseFloat(getComputedStyle(el).scrollMarginTop) || 0), 0, maxScroll));
      update();
    };
    stops.forEach((a, i) => {
      const angle = (135 + i / (stops.length - 1) * 270) * Math.PI / 180;
      a.style.setProperty('--stop-x', `${112 + Math.cos(angle) * 84}px`);
      a.style.setProperty('--stop-y', `${112 + Math.sin(angle) * 84}px`);
      a.addEventListener('pointerenter', () => { preview = i; showLabel(); });
      a.addEventListener('pointerleave', () => { preview = null; showLabel(); });
      a.addEventListener('focus', () => { preview = i; showLabel(); });
      a.addEventListener('blur', () => { preview = null; showLabel(); });
    });
    const setOpen = (open, restoreFocus = false) => {
      panel.hidden = !open;
      button.setAttribute('aria-expanded', String(open));
      preview = null; showLabel();
      if (restoreFocus) button.focus({ preventScroll: true });
    };
    button.addEventListener('click', () => setOpen(panel.hidden));
    document.addEventListener('pointerdown', e => {
      if (!panel.hidden && !orbit.contains(e.target)) setOpen(false, panel.contains(document.activeElement));
    });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && !panel.hidden) { setOpen(false, true); e.preventDefault(); }
    });
    orbit.addEventListener('focusout', e => {
      if (e.relatedTarget && !orbit.contains(e.relatedTarget)) setOpen(false);
    });
    const seek = e => {
      const rect = scrub.getBoundingClientRect();
      const angle = Math.atan2(e.clientY - rect.top - rect.height / 2,
        e.clientX - rect.left - rect.width / 2) * 180 / Math.PI;
      let sweep = (angle - 135 + 360) % 360;
      if (sweep > 270) sweep = sweep > 315 ? 0 : 270;
      const step = sweep / 270 * (stops.length - 1);
      const i = Math.min(Math.floor(step), offsets.length - 2);
      const y = offsets[i] + (offsets[i + 1] - offsets[i]) * (step - i);
      scrollTo({ top: y, behavior: 'instant' }); update();
    };
    scrub.addEventListener('pointerdown', e => {
      if (!e.isPrimary || e.button !== 0) return;
      dragging = true; preview = null;
      scrub.setPointerCapture(e.pointerId); scrub.focus({ preventScroll: true }); seek(e);
    });
    scrub.addEventListener('pointermove', e => { if (dragging) seek(e); });
    const release = () => { dragging = false; };
    scrub.addEventListener('pointerup', release);
    scrub.addEventListener('pointercancel', release);
    scrub.addEventListener('lostpointercapture', release);
    scrub.addEventListener('keydown', e => {
      const steps = { ArrowRight: .02, ArrowUp: .02, ArrowLeft: -.02, ArrowDown: -.02, PageUp: -.1, PageDown: .1 };
      let y;
      if (e.key === 'Home') y = 0;
      else if (e.key === 'End') y = maxScroll;
      else if (e.key in steps) y = scrollY + maxScroll * steps[e.key];
      else return;
      e.preventDefault(); scrollTo({ top: clamp(y, 0, maxScroll), behavior: 'instant' });
    });
    addEventListener('scroll', update, { passive: true });
    addEventListener('resize', measure);
    addEventListener('load', measure);
    motion.addEventListener('change', update);
    if ('ResizeObserver' in window) new ResizeObserver(measure).observe(document.querySelector('main'));
    if (document.fonts) document.fonts.ready.then(measure);
    measure();
  }

})();
