/* Nocturne module. No framework or network calls. Section measurements drive a
   transforming moth; pointer drag reverses the same piecewise mapping. */
(function () {
  'use strict';
  const map = document.querySelector('.nocturne');
  if (!map) return;
  const track = map.querySelector('.nocturne-track');
  const familiar = map.querySelector('.nocturne-familiar');
  const svg = map.querySelector('.nocturne-vine');
  const stops = [...map.querySelectorAll('.nocturne-stops a')];
  const nav = [...document.querySelectorAll('.nav-links a')];
  const targets = stops.map(a => document.getElementById(a.hash.slice(1)));
  const percent = map.querySelector('.nocturne-percent');
  const label = map.querySelector('.nocturne-label');
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const guide = svg.querySelector('.nocturne-guide');
  const lattice = svg.querySelector('.nocturne-branches');
  const growth = svg.querySelector('.nocturne-growth');
  const reach = svg.querySelector('.nocturne-reach');
  const clamp = (n, min, max) => Math.max(min, Math.min(max, n));
  let offsets = [], maxScroll = 0, current = 0, preview = null;
  let position = 0, destination = 0, velocity = 0, sway = 0, aim = 0, swayVelocity = 0;
  let height = 1, spine = 42, nodeX = 86, raf = 0, last = 0;
  let pointer = null, grabOffset = 0, hovering = false, bloom = .06;
  const targetBloom = () => clamp(.06 + destination * 1.08 + (hovering ? .35 : 0), 0, 1);
  // Identical cubic command topology lets the cocoon unfurl continuously.
  const shapes = {
    fore: [[58,64,46,52,42,36,56,16,65,30,63,49,59,68,57,73,54,70,58,64],
           [58,64,40,36,12,22,5,16,0,47,10,73,52,84,55,78,58,71,58,64]],
    hind: [[58,72,42,80,48,97,56,119,54,95,56,83,58,72],
           [58,72,18,64,7,90,28,124,22,91,55,107,58,72]],
    vein: [[58,68,53,46,54,29,56,20], [58,68,38,55,17,34,8,22]],
    'vein-lower': [[58,76,52,86,55,103,56,110], [58,76,39,81,26,91,28,113]]
  };
  const morph = (name, amount) => {
    const [closed, open] = shapes[name];
    const values = closed.map((v, i) => (v + (open[i] - v) * amount).toFixed(2));
    let d = `M${values[0]} ${values[1]}`;
    for (let i = 2; i < values.length; i += 6) d += ` C${values.slice(i, i + 6).join(' ')}`;
    if (name === 'fore' || name === 'hind') d += ' Z';
    map.querySelectorAll(`.moth-${name}`).forEach(path => path.setAttribute('d', d));
  };
  const paint = () => {
    const y = position * height;
    const vineSway = Math.sin(position * Math.PI * 2) * 7;
    const x = spine + vineSway + sway;
    map.style.setProperty('--familiar-y', `${position * 100}%`);
    map.style.setProperty('--familiar-sway', `${vineSway + sway}px`);
    map.style.setProperty('--familiar-lean', `${motion.matches ? 0 : sway * 1.2 + clamp(velocity * 10, -9, 9)}deg`);
    map.style.setProperty('--seal-turn', `${motion.matches ? 0 : position * 90 + sway}deg`);
    map.style.setProperty('--dust-rise', `${motion.matches ? 0 : -Math.abs(velocity) * 12}px`);
    map.style.setProperty('--bloom', bloom.toFixed(4));
    Object.keys(shapes).forEach(name => morph(name, bloom));
    const width = 16 - bloom * 12;
    map.querySelector('.moth-body').setAttribute('d', `M60 38 C${60+width} 48 ${60+width*.7} 85 60 105 C${60-width*.7} 85 ${60-width} 48 60 38Z`);
    growth.style.strokeDasharray = `${position} 1`;
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
    bloom += (targetBloom() - bloom) * Math.min(1, dt * 8);
    if (Math.abs(destination - position) < .0001 && Math.abs(velocity) < .001 && Math.abs(aim - sway) < .01 && Math.abs(swayVelocity) < .01 && Math.abs(targetBloom() - bloom) < .001) {
      position = destination; sway = aim; bloom = targetBloom(); velocity = swayVelocity = 0; raf = last = 0;
      paint();
    } else { paint(); raf = requestAnimationFrame(animate); }
  };
  const wake = () => {
    if (motion.matches || pointer !== null) {
      cancelAnimationFrame(raf); raf = last = 0; velocity = swayVelocity = 0;
      position = destination; sway = motion.matches ? 0 : aim; bloom = targetBloom(); paint();
    } else if (!raf && !document.hidden) raf = requestAnimationFrame(animate);
  };
  const showLabel = () => {
    label.textContent = stops[preview === null ? current : preview].dataset.label;
    map.toggleAttribute('data-preview', preview !== null);
    paint();
  };
  const update = () => {
    // Document overflow can settle between resize notifications (fonts/reveals).
    maxScroll = Math.max(0, document.documentElement.scrollHeight - innerHeight);
    const y = clamp(scrollY, 0, maxScroll);
    current = 0;
    while (current < offsets.length - 1 && y >= Math.min(maxScroll, offsets[current + 1]) - 1) current++;
    // The final section can begin below the viewport's maximum scroll position.
    // Give the last reachable stretch to its final leaf rather than leaving the
    // familiar on the penultimate section at 100%.
    if (maxScroll > 0 && maxScroll - y <= Math.max(32, innerHeight * .04)) current = offsets.length - 1;
    const fraction = current < offsets.length - 1
      ? clamp((y - offsets[current]) / Math.max(1, offsets[current + 1] - offsets[current]), 0, 1) : 0;
    destination = (current + fraction) / (stops.length - 1);
    const pct = maxScroll > 0 ? Math.round(y / maxScroll * 100) : 0;
    percent.textContent = `${String(pct).padStart(2, '0')}%`;
    familiar.setAttribute('aria-valuenow', pct);
    familiar.setAttribute('aria-valuetext', `${pct}% · ${stops[current].dataset.label}`);
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
    const vine = Array.from({ length: 65 }, (_, i) => {
      const t = i / 64;
      return `${i ? 'L' : 'M'}${spine + Math.sin(t * Math.PI * 2) * 7} ${t * height}`;
    }).join(' ');
    guide.setAttribute('d', vine); growth.setAttribute('d', vine);
    lattice.setAttribute('d', stops.map((_, i) => {
      const y = i / (stops.length - 1) * height;
      const x = spine + Math.sin(y / height * Math.PI * 2) * 7;
      return `M${x} ${y} Q${(x+nodeX)/2} ${y-10} ${nodeX-7} ${y}`;
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
  familiar.addEventListener('pointerenter', () => { hovering = true; wake(); });
  familiar.addEventListener('pointerleave', () => { hovering = false; wake(); });
  familiar.addEventListener('focus', () => { hovering = true; wake(); });
  familiar.addEventListener('blur', () => { hovering = false; wake(); });
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
    grabOffset = familiar.contains(e.target) ? e.clientY - track.getBoundingClientRect().top - position * height : 0;
    preview = null; aim = 0; map.setAttribute('data-dragging', '');
    track.setPointerCapture(pointer); familiar.focus({ preventScroll: true }); seek(e);
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
  familiar.addEventListener('keydown', e => {
    const steps = { ArrowRight: .02, ArrowUp: .02, ArrowLeft: -.02, ArrowDown: -.02, PageUp: -.1, PageDown: .1 };
    let y;
    if (e.key === 'Home') y = 0;
    else if (e.key === 'End') y = document.documentElement.scrollHeight;
    else if (e.key in steps) y = scrollY + maxScroll * steps[e.key];
    else return;
    e.preventDefault();
    const smooth = document.documentElement.classList.contains('smooth');
    document.documentElement.classList.remove('smooth');
    scrollTo({ top: clamp(y, 0, document.documentElement.scrollHeight), behavior: 'auto' });
    if (smooth) requestAnimationFrame(() => document.documentElement.classList.add('smooth'));
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
