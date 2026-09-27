/* Rift module. No framework or network calls. Section measurements drive a
   spring-following shard; pointer drag reverses the same piecewise mapping. */
(function () {
  'use strict';
  const map = document.querySelector('.rift');
  if (!map) return;
  const track = map.querySelector('.rift-track');
  const shard = map.querySelector('.rift-shard');
  const svg = map.querySelector('.rift-threads');
  const stops = [...map.querySelectorAll('.rift-stops a')];
  const nav = [...document.querySelectorAll('.nav-links a')];
  const targets = stops.map(a => document.getElementById(a.hash.slice(1)));
  const percent = map.querySelector('.rift-percent');
  const label = map.querySelector('.rift-label');
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const guide = svg.querySelector('.rift-guide');
  const lattice = svg.querySelector('.rift-lattice');
  const silks = [...svg.querySelectorAll('.rift-silk')];
  const reach = svg.querySelector('.rift-reach');
  const clamp = (n, min, max) => Math.max(min, Math.min(max, n));
  let offsets = [], maxScroll = 0, current = 0, preview = null;
  let position = 0, destination = 0, velocity = 0, sway = 0, aim = 0, swayVelocity = 0;
  let height = 1, spine = 42, nodeX = 86, raf = 0, last = 0;
  let pointer = null, grabOffset = 0;
  const paint = () => {
    const y = position * height;
    const x = spine + sway;
    map.style.setProperty('--shard-y', `${position * 100}%`);
    map.style.setProperty('--shard-sway', `${sway}px`);
    map.style.setProperty('--shard-lean', `${motion.matches ? 0 : sway * 1.2 + clamp(velocity * 12, -12, 12)}deg`);
    map.style.setProperty('--halo-turn', `${motion.matches ? 0 : position * 150 + sway * 2}deg`);
    map.style.setProperty('--scatter', `${motion.matches ? 0 : Math.min(8, Math.abs(velocity) * 9 + Math.abs(sway) * .4 + (pointer !== null ? 3 : 0))}px`);
    const seam = `M${spine} 0 C${spine} ${y * .35} ${x + sway} ${y * .7} ${x} ${y}`;
    silks.forEach(path => path.setAttribute('d', seam));
    if (preview !== null) {
      const stopY = preview / (stops.length - 1) * height;
      reach.setAttribute('d', `M${x} ${y} Q${nodeX - 10} ${(y + stopY) / 2} ${nodeX} ${stopY}`);
    }
  };
  const animate = time => {
    const dt = Math.min((time - (last || time - 16)) / 1000, .032);
    last = time;
    velocity += ((destination - position) * 150 - velocity * 24) * dt;
    swayVelocity += ((aim - sway) * 170 - swayVelocity * 19) * dt;
    position = clamp(position + velocity * dt, 0, 1);
    sway += swayVelocity * dt;
    if (Math.abs(destination - position) < .0001 && Math.abs(velocity) < .001 && Math.abs(aim - sway) < .01 && Math.abs(swayVelocity) < .01) {
      position = destination; sway = aim; velocity = swayVelocity = 0; raf = last = 0;
      paint();
    } else { paint(); raf = requestAnimationFrame(animate); }
  };
  const wake = () => {
    if (motion.matches || pointer !== null) {
      cancelAnimationFrame(raf); raf = last = 0; velocity = swayVelocity = 0;
      position = destination; sway = motion.matches ? 0 : aim; paint();
    } else if (!raf && !document.hidden) raf = requestAnimationFrame(animate);
  };
  const showLabel = () => {
    label.textContent = stops[preview === null ? current : preview].dataset.label;
    map.toggleAttribute('data-preview', preview !== null);
    paint();
  };
  const update = () => {
    const y = clamp(scrollY, 0, maxScroll);
    current = 0;
    while (current < offsets.length - 1 && y >= offsets[current + 1] - 1) current++;
    const fraction = current < offsets.length - 1
      ? clamp((y - offsets[current]) / Math.max(1, offsets[current + 1] - offsets[current]), 0, 1) : 0;
    destination = (current + fraction) / (stops.length - 1);
    const pct = maxScroll > 0 ? Math.round(y / maxScroll * 100) : 0;
    percent.textContent = `${String(pct).padStart(2, '0')}%`;
    shard.setAttribute('aria-valuenow', pct);
    shard.setAttribute('aria-valuetext', `${pct}% · ${stops[current].dataset.label}`);
    [...stops, ...nav].forEach(a => {
      if (a.hash === stops[current].hash) a.setAttribute('aria-current', 'location');
      else a.removeAttribute('aria-current');
    });
    stops.forEach((a, i) => a.toggleAttribute('data-passed', i < current));
    showLabel(); wake();
  };
  const measure = () => {
    maxScroll = Math.max(0, document.documentElement.scrollHeight - innerHeight);
    const layoutTop = el => {
      let top = 0;
      for (let node = el; node; node = node.offsetParent) top += node.offsetTop;
      return top;
    };
    offsets = targets.map((el, i) => i === 0 ? 0 : clamp(layoutTop(el) - (parseFloat(getComputedStyle(el).scrollMarginTop) || 0), 0, maxScroll));
    height = track.clientHeight || 1;
    spine = parseFloat(getComputedStyle(map).getPropertyValue('--spine'));
    nodeX = track.clientWidth - 22;
    svg.setAttribute('viewBox', `0 0 ${track.clientWidth || 1} ${height}`);
    guide.setAttribute('d', `M${spine} 0 V${height}`);
    lattice.setAttribute('d', stops.map((_, i) => {
      const y = i / (stops.length - 1) * height;
      return `M${spine + 8} ${y} H${nodeX - 8}`;
    }).join(' '));
    update();
  };
  stops.forEach((a, i) => {
    a.style.setProperty('--stop-y', `${i / (stops.length - 1) * 100}%`);
    const enter = () => { preview = i; showLabel(); };
    const leave = () => { preview = null; showLabel(); };
    a.addEventListener('pointerenter', enter); a.addEventListener('pointerleave', leave);
    a.addEventListener('focus', enter); a.addEventListener('blur', leave);
  });
  const seek = e => {
    const rect = track.getBoundingClientRect();
    const step = clamp((e.clientY - rect.top - grabOffset) / height, 0, 1) * (stops.length - 1);
    const i = Math.min(Math.floor(step), offsets.length - 2);
    scrollTo({ top: offsets[i] + (offsets[i + 1] - offsets[i]) * (step - i), behavior: 'instant' });
    update();
  };
  track.addEventListener('pointerdown', e => {
    if (!e.isPrimary || e.button !== 0 || e.target.closest('a')) return;
    pointer = e.pointerId;
    grabOffset = shard.contains(e.target) ? e.clientY - track.getBoundingClientRect().top - position * height : 0;
    preview = null; aim = 0; map.setAttribute('data-dragging', '');
    track.setPointerCapture(pointer); shard.focus({ preventScroll: true }); seek(e);
  });
  track.addEventListener('pointermove', e => {
    if (pointer !== null) { if (pointer === e.pointerId) seek(e); return; }
    if (e.pointerType === 'touch') return;
    const rect = track.getBoundingClientRect();
    aim = clamp((e.clientX - rect.left - spine) * .2, -9, 9);
    wake();
  });
  track.addEventListener('pointerleave', () => { if (pointer === null) { aim = 0; wake(); } });
  const release = () => {
    pointer = null; aim = 0; map.removeAttribute('data-dragging'); wake();
  };
  track.addEventListener('pointerup', release);
  track.addEventListener('pointercancel', release);
  track.addEventListener('lostpointercapture', release);
  shard.addEventListener('keydown', e => {
    const steps = { ArrowRight: .02, ArrowUp: .02, ArrowLeft: -.02, ArrowDown: -.02, PageUp: -.1, PageDown: .1 };
    let y;
    if (e.key === 'Home') y = 0;
    else if (e.key === 'End') y = maxScroll;
    else if (e.key in steps) y = scrollY + maxScroll * steps[e.key];
    else return;
    e.preventDefault(); scrollTo({ top: clamp(y, 0, maxScroll), behavior: 'instant' });
  });
  addEventListener('scroll', update, { passive: true });
  addEventListener('resize', measure); addEventListener('load', measure);
  motion.addEventListener('change', () => { aim = 0; update(); });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { cancelAnimationFrame(raf); raf = last = 0; }
    else measure();
  });
  if ('ResizeObserver' in window) new ResizeObserver(measure).observe(document.querySelector('main'));
  if (document.fonts) document.fonts.ready.then(measure);
  measure();
})();
