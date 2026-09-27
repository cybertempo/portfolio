/* Portfolio behaviour. Progressive enhancement only: every piece of content is
   already in the HTML; this file adds motion, the mobile menu, and assembles
   the e-mail link so the address is not sitting in the page for scrapers.
   No network calls, no storage, no third parties — the CSP forbids them. */
(function () {
  'use strict';
  document.documentElement.classList.add('js');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const pal = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  /* land on the #hash target instantly, then allow smooth scrolling for clicks */
  addEventListener('load', () => {
    const target = location.hash && document.getElementById(location.hash.slice(1));
    if (target) target.scrollIntoView({ behavior: 'instant', block: 'start' });
    document.documentElement.classList.add('smooth');
  });

  /* mobile menu */
  const toggle = document.querySelector('.nav-toggle');
  const links = document.getElementById('nav-links');
  if (toggle && links) {
    toggle.addEventListener('click', () => {
      const open = links.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(open));
    });
    links.addEventListener('click', e => {
      if (e.target.tagName === 'A') { links.classList.remove('open'); toggle.setAttribute('aria-expanded', 'false'); }
    });
  }

  /* e-mail: the address is stored reversed in two data attributes and joined
     here on load. A trivial obstacle, but it defeats the dumb harvesters that
     grep pages for mailto: and @. */
  const rev = s => s.split('').reverse().join('');
  document.querySelectorAll('a.email[data-u][data-d]').forEach(a => {
    const addr = rev(a.dataset.u) + '@' + rev(a.dataset.d);
    a.href = 'mailto:' + addr;
    a.title = addr;
  });

  /* current section in the nav */
  const navAnchors = [...document.querySelectorAll('.nav-links a[href^="#"]')];
  const sections = navAnchors.map(a => document.querySelector(a.getAttribute('href'))).filter(Boolean);
  if ('IntersectionObserver' in window && sections.length) {
    const spy = new IntersectionObserver(entries => {
      entries.forEach(en => {
        if (!en.isIntersecting) return;
        navAnchors.forEach(a => a.removeAttribute('aria-current'));
        navAnchors.filter(x => x.getAttribute('href') === '#' + en.target.id)
          .forEach(a => a.setAttribute('aria-current', 'true'));
      });
    }, { rootMargin: '-40% 0px -55% 0px' });
    sections.forEach(s => spy.observe(s));
  }

  /* reveal on scroll */
  const revealEls = document.querySelectorAll('.reveal');
  if (reduced || !('IntersectionObserver' in window)) {
    revealEls.forEach(el => el.classList.add('in'));
  } else {
    const io = new IntersectionObserver(es => {
      es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
    }, { threshold: 0.1 });
    revealEls.forEach(el => io.observe(el));
  }

  if (reduced) return;   /* everything below is decoration */

  /* typing line: phrases come from the data attribute the build wrote */
  const tl = document.getElementById('typeline');
  if (tl) {
    let phrases = [];
    try { phrases = JSON.parse(tl.dataset.phrases || '[]'); } catch (_) { phrases = []; }
    if (phrases.length > 1) {
      let pi = 0, ci = phrases[0].length, del = false;
      const step = () => {
        const cur = phrases[pi];
        tl.textContent = cur.slice(0, ci);
        let wait;
        if (!del && ci < cur.length) { ci++; wait = 42; }
        else if (!del) { del = true; wait = 2200; }
        else if (ci > 0) { ci--; wait = 16; }
        else { del = false; pi = (pi + 1) % phrases.length; wait = 350; }
        setTimeout(step, wait);
      };
      setTimeout(step, 2200);
    }
  }

  /* photo: parallax + fade on scroll, tilt toward the pointer */
  const photo = document.getElementById('heroPhoto');
  const hero = document.querySelector('.hero');
  if (photo && hero) {
    let tx = 0, ty = 0, sy = 0, ticking = false;
    const apply = () => {
      ticking = false;
      const h = hero.offsetHeight || 1;
      const p = Math.min(1, sy / h);
      photo.style.transform = `translate3d(${tx * 6}px, ${sy * 0.18}px, 0) rotateY(${tx * 5}deg) rotateX(${-ty * 3}deg) scale(${1 - p * 0.08})`;
      photo.style.opacity = String(1 - p * 1.1);
      photo.style.setProperty('--tx', tx.toFixed(2));
    };
    const queue = () => { if (!ticking) { ticking = true; requestAnimationFrame(apply); } };
    addEventListener('scroll', () => { sy = scrollY; queue(); }, { passive: true });
    hero.addEventListener('pointermove', e => {
      const r = hero.getBoundingClientRect();
      tx = ((e.clientX - r.left) / r.width - 0.5) * 2;
      ty = ((e.clientY - r.top) / r.height - 0.5) * 2;
      queue();
    });
    hero.addEventListener('pointerleave', () => { tx = 0; ty = 0; queue(); });
    apply();
  }

  /* glyph rain: one canvas, throttled to ~18 fps, paused when the tab is hidden */
  const cv = document.getElementById('rain');
  if (cv && cv.getContext) {
    const cx = cv.getContext('2d');
    /* the streams spell a message in hex when the build supplies one (data-hex on
       the canvas: the UTF-8 bytes of [design] rain_text); otherwise glyph noise */
    const hex = (cv.dataset.hex || '').replace(/[^0-9A-F]/g, '');
    const glyphs = 'アイウエオカキクケコサシスセソ0123456789ABCDEF<>/\\{}[]$#@!?';
    const cell = 16;
    let drops = [], offsets = [], last = 0, raf = 0;
    /* Nothing about the canvas's size is remembered. Every frame measures the
       element's own box and compares it with the element's own backing store:
       two live readings, so there is no variable that can go stale and no
       assumption about when a resize was noticed. The box is capped at the
       window because a <canvas> is a replaced element — if the stylesheet ever
       stopped giving it a box it would lay out at its width attribute, and a
       measurement written back into that attribute would double every frame. */
    const box = () => {
      const bw = cv.clientWidth, bh = cv.clientHeight;
      return [bw > 0 && bw <= innerWidth ? bw : innerWidth, bh > 0 && bh <= innerHeight ? bh : innerHeight];
    };
    const fit = () => {
      const [bw, bh] = box(), dpr = Math.min(devicePixelRatio || 1, 2);
      const pw = Math.round(bw * dpr), ph = Math.round(bh * dpr);
      if (cv.width === pw && cv.height === ph) return [bw, bh];   /* already correct */
      cv.width = pw; cv.height = ph;                              /* this also clears the canvas */
      cx.setTransform(dpr, 0, 0, dpr, 0, 0);
      cx.font = '14px "JetBrains Mono", monospace';
      const cols = Math.ceil(bw / cell);
      for (let i = drops.length; i < cols; i++) {                 /* grow in place: a resize adds columns, it does not wipe the rain */
        drops[i] = Math.random() * -60;
        offsets[i] = hex ? 2 * Math.floor(Math.random() * hex.length / 2) : 0;  /* each column starts on a byte */
      }
      return [bw, bh];
    };
    const frame = t => {
      raf = requestAnimationFrame(frame);
      if (t - last < 55) return;
      last = t;
      const [w, h] = fit();
      const cols = Math.ceil(w / cell);
      const fade = `rgba(${pal('--bg-rgb')},.1)`, main = `rgba(${pal('--primary-rgb')},.9)`, hi1 = pal('--warning'), hi2 = pal('--danger');
      cx.fillStyle = fade;
      cx.fillRect(0, 0, w, h);
      for (let i = 0; i < cols; i++) {
        if (drops[i] === undefined) { drops[i] = Math.random() * -60; offsets[i] = hex ? 2 * Math.floor(Math.random() * hex.length / 2) : 0; }
        const r = Math.random();
        cx.fillStyle = r > .985 ? hi1 : r > .97 ? hi2 : main;
        const row = Math.floor(drops[i]);
        const ch = hex ? hex[((offsets[i] + row) % hex.length + hex.length) % hex.length] : glyphs[Math.random() * glyphs.length | 0];
        cx.fillText(ch, i * cell, drops[i] * cell);
        if (drops[i] * cell > h && Math.random() > .976) drops[i] = 0;
        drops[i]++;
      }
    };
    const start = () => { if (!raf) raf = requestAnimationFrame(frame); };
    const stop = () => { cancelAnimationFrame(raf); raf = 0; };
    fit();
    document.addEventListener('visibilitychange', () => document.hidden ? stop() : start());
    start();
  }

  /* the 404 ghost: a failed request flickers somewhere on the page now and
     then, in a different spot each time. Nothing depends on it, and if the
     content file leaves [design] ghost_text empty it is not even rendered. */
  const ghost = document.getElementById('ghost');
  if (ghost && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
    let timer = 0;
    const again = () => { clearTimeout(timer); timer = setTimeout(flicker, 26000 + Math.random() * 44000); };
    const flicker = () => {
      if (document.hidden) return again();                 /* not while nobody is looking */
      ghost.style.setProperty('--gx', (14 + Math.random() * 72).toFixed(1) + 'vw');
      ghost.style.setProperty('--gy', (16 + Math.random() * 68).toFixed(1) + 'vh');
      ghost.classList.remove('on');
      void ghost.offsetWidth;                              /* restart the animation from the top */
      ghost.classList.add('on');
      setTimeout(() => ghost.classList.remove('on'), 1400);
      again();
    };
    setTimeout(flicker, 9000 + Math.random() * 12000);     /* the first one early enough to be seen */
  }

  /* logo scramble on hover */
  const logo = document.querySelector('.logo');
  if (logo) {
    const parts = [...logo.querySelectorAll('span:not(.logo-cursor)')];
    const originals = parts.map(p => p.textContent);
    const chars = '!<>-_\\/[]{}=+*^?#';
    let busy = false;
    logo.addEventListener('mouseenter', () => {
      if (busy) return; busy = true;
      let f = 0; const total = originals.join('').length;
      const iv = setInterval(() => {
        let seen = 0;
        parts.forEach((p, i) => {
          p.textContent = originals[i].split('').map(c => (seen++ < f) ? c : chars[Math.random() * chars.length | 0]).join('');
        });
        if (f++ >= total) { clearInterval(iv); parts.forEach((p, i) => p.textContent = originals[i]); busy = false; }
      }, 30);
    });
  }
})();
