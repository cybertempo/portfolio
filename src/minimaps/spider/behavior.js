/* Minimap module "spider" — behaviour. Self-contained: no dependencies, no
   network, respects reduced motion. The main script marks the active section
   on every [href^="#"] link inside .rail-stops via aria-current. */
(function () {
  'use strict';
  const motionPreference = matchMedia('(prefers-reduced-motion: reduce)');
  let reduced = motionPreference.matches;
  const railFill = document.getElementById('railFill');
  const railSpider = document.getElementById('railSpider');
  const rail = document.querySelector('.rail');
  /* true while the spider has left its scroll position to climb home; the scroll
     handler must not drag it back down until the reader is back */
  let away = false;
  const pctNow = () => {
    const max = document.documentElement.scrollHeight - innerHeight;
    return max > 0 ? Math.max(0, Math.min(100, scrollY / max * 100)) : 0;
  };
  let syncSpider = () => {};
  if (railFill && railSpider && rail) {
    const drawing = railSpider.querySelector('.spider');
    const rig = railSpider.querySelector('.rig');
    const track = railSpider.parentElement;
    /* The front two pairs pull on the silk with jointed legs. The rear two
       pairs fold beside the abdomen and ride with it; there is no supporting
       strand below the body for them to step on. All roots stay attached. */
    const legs = [...railSpider.querySelectorAll('.legs path')].map((path, i) => {
      const points = path.getAttribute('d').match(/-?\d+(?:\.\d+)?/g).map(Number);
      const pair = i % 4;
      return { path, rest: path.getAttribute('d'), points, pair, side: i < 4 ? -1 : 1,
        upper: [11, 12][pair], lower: [14, 13][pair],
        reach: [-6, 0][pair], phase: pair * .5 + (i < 4 ? 0 : .5) };
    });
    let height = track.clientHeight, visible = track.getClientRects().length > 0;
    let spiderPx = railSpider.clientHeight || 44;   /* the drawing is 40 units across this many pixels; measured, so resizing the spider needs no code change */
    let position = pctNow() / 100 * height, target = position;
    let angle = 180, turnVelocity = 0, phase = 0, grip = 0, frame = 0, previousTime = 0;
    let posed = false;
    let lastY = scrollY, directionTravel = 0;
    const ease = t => t * t * (3 - 2 * t);
    const paintLegs = () => {
      if (grip < .001) {
        if (posed) {
          legs.forEach(leg => leg.path.setAttribute('d', leg.rest));
          rig.removeAttribute('transform');
          posed = false;
        }
        return;
      }
      posed = true;
      const bob = Math.sin(phase * Math.PI * 4) * .45 * grip;
      rig.setAttribute('transform', `translate(0 ${bob.toFixed(3)})`);
      legs.forEach(leg => {
        const [x, y, restKx, restKy, restFx, restFy] = leg.points;
        const pose = (kx, ky, fx, fy) => {
          const mix = (a, b) => (a + (b - a) * grip).toFixed(3);
          leg.path.setAttribute('d', `M${x} ${y} L${mix(restKx, kx)} ${mix(restKy, ky)} L${mix(restFx, fx)} ${mix(restFy, fy)}`);
        };
        if (leg.pair >= 2) {
          /* Folded, visibly clear of the thread. These legs have no step
             phase or planted foot: they move only with the suspended body. */
          const rear = leg.pair === 3;
          pose(20 + leg.side * (rear ? 8 : 10), rear ? 31 : 26,
            20 + leg.side * (rear ? 4.5 : 6.5), rear ? 35 : 30);
          return;
        }
        const p = (phase + leg.phase) % 1;
        const hold = .68;
        /* During the hold, the foot moves down relative to the rising body:
           it stays on the same point of silk. Recovery arcs out to the side
           before reaching up again. At least one leg of each pair holds. */
        const swing = Math.max(0, (p - hold) / (1 - hold));
        const fx = 20 + leg.side * (.8 + Math.sin(swing * Math.PI) * 6);
        const fy = leg.reach + (p < hold ? p * 20 : (1 - ease(swing)) * hold * 20) - bob;
        const dx = fx - x, dy = fy - y;
        const distance = Math.max(.01, Math.hypot(dx, dy));
        const along = (leg.upper ** 2 - leg.lower ** 2 + distance ** 2) / (2 * distance);
        const bend = Math.sqrt(Math.max(0, leg.upper ** 2 - along ** 2));
        const outward = leg.side * (dy < 0 ? 1 : -1);
        const kx = x + along * dx / distance + outward * -dy / distance * bend;
        const ky = y + along * dy / distance + outward * dx / distance * bend;
        pose(kx, ky, fx, fy);
      });
    };
    const paint = () => {
      railSpider.style.transform = `translate3d(0,${position.toFixed(3)}px,0)`;
      railFill.style.transform = `scaleY(${height ? position / height : 0})`;
      drawing.style.transform = `rotate(${angle.toFixed(3)}deg)`;
      drawing.style.setProperty('--turn', `${angle.toFixed(3)}deg`);   /* the abdomen's number cancels this, so it always reads upright */
      paintLegs();
    };
    const animate = time => {
      frame = 0;
      /* No catch-up jump after a busy frame or a suspended tab. The gait is
         driven by distance actually rendered, not by an independent timer. */
      const dt = Math.min(32, previousTime ? time - previousTime : 16.7);
      previousTime = time;
      const facing = rail.classList.contains('up') ? 0 : 180;
      /* A damped pivot eases both into and out of a turn, and retains angular
         velocity if the reader reverses midway. Never squash or mirror. */
      const offset = angle - facing, decay = Math.exp(-dt / 75);
      const impulse = turnVelocity + offset / 75;
      angle = facing + (offset + impulse * dt) * decay;
      turnVelocity = (turnVelocity - impulse * dt / 75) * decay;
      if (Math.abs(facing - angle) < .1 && Math.abs(turnVelocity) < .01) {
        angle = facing; turnVelocity = 0;
      }
      const turning = Math.abs(facing - angle) > 2;
      const distance = target - position;
      const speed = away ? 48 : 420;
      /* Keep a light hold while pivoting; travel resumes as the head lines up. */
      const turnSpeed = .2 + .8 * (1 - Math.abs(facing - angle) / 180);
      const step = Math.sign(distance) * Math.min(Math.abs(distance) * (1 - Math.exp(-dt / 95)), speed * dt / 1000) * turnSpeed;
      position += step;
      if (Math.abs(target - position) < .04) position = target;
      const moving = Math.abs(target - position) > .04;
      if (facing === 0) phase = (phase + Math.abs(step) * 40 / spiderPx / 20) % 1;
      const desiredGrip = facing === 0 && (moving || turning) ? 1 : 0;
      grip += (desiredGrip - grip) * (1 - Math.exp(-dt / 100));
      if (Math.abs(desiredGrip - grip) < .001) grip = desiredGrip;
      rail.classList.toggle('moving', moving);
      rail.classList.toggle('turning', turning);
      rail.classList.toggle('gripping', grip > 0);
      paint();
      if (moving || angle !== facing || grip !== desiredGrip) frame = requestAnimationFrame(animate);
      else {
        previousTime = 0;
        if (away) { rail.classList.remove('climbing'); rail.classList.add('doze'); }
      }
    };
    syncSpider = () => {
      target = away ? 0 : pctNow() / 100 * height;
      if (reduced || !visible || document.hidden) {
        cancelAnimationFrame(frame); frame = 0; previousTime = 0;
        position = target; grip = 0;
        angle = rail.classList.contains('up') && !reduced ? 0 : 180; turnVelocity = 0;
        rail.classList.remove('moving', 'turning', 'gripping');
        paint();
      } else if (!frame) frame = requestAnimationFrame(animate);
    };
    addEventListener('scroll', () => {
      const dy = scrollY - lastY;
      lastY = scrollY;
      if (!away && !reduced && dy) {
        directionTravel = Math.sign(dy) === Math.sign(directionTravel) ? directionTravel + dy : dy;
        /* Accumulate small deltas, but ignore trackpad bounce and tiny layout
           corrections. A turn can reverse smoothly from its current angle. */
        if (Math.abs(directionTravel) >= 18) rail.classList.toggle('up', directionTravel < 0);
      }
      syncSpider();
    }, { passive: true });
    const measure = () => {
      const nextHeight = track.clientHeight;
      if (height) position *= nextHeight / height;
      height = nextHeight; visible = track.getClientRects().length > 0;
      spiderPx = railSpider.clientHeight || spiderPx;
      syncSpider();
    };
    addEventListener('resize', measure);
    if ('ResizeObserver' in window) new ResizeObserver(measure).observe(document.body);
    document.addEventListener('visibilitychange', syncSpider);
    motionPreference.addEventListener('change', event => {
      reduced = event.matches;
      away = false;
      rail.classList.remove('away', 'climbing', 'up', 'doze', 'idle', 'groom', 'eat', 'pluck', 'startled');
      rail.classList.toggle('still', reduced);
      syncSpider();
    });
    paint();
  }

  /* stops at real positions; the lit diamond is decided from scroll position, not intersection */
  const stops = [...document.querySelectorAll('.rail-stops li')].map(li => {
    const a = li.querySelector('a[href^="#"]');
    return a ? { li, a, target: document.querySelector(a.getAttribute('href')) } : null;
  }).filter(s => s && s.target);
  const navH = () => (document.querySelector('.nav')?.offsetHeight || 0);
  const place = () => {
    const max = document.documentElement.scrollHeight - innerHeight;
    stops.forEach(s => {
      const y = s.target.id === 'top' ? 0 : s.target.getBoundingClientRect().top + scrollY - navH();
      s.li.style.setProperty('--at', max > 0 ? String(Math.max(0, Math.min(100, y / max * 100))) : '0');
    });
  };
  /* a diamond is "passed" when the spider (scroll %) has reached its position — the same
     rule as the path dots, so it never lights before the last dot in front of it; the
     latest passed diamond is the one that glows */
  const light = () => {
    const max = document.documentElement.scrollHeight - innerHeight;
    const pct = max > 0 ? Math.min(100, scrollY / max * 100) : 0;
    let on = null;
    stops.forEach(s => {
      const at = parseFloat(s.li.style.getPropertyValue('--at')) || 0;
      const passed = at <= pct + 0.01;
      s.a.toggleAttribute('data-passed', passed);
      if (passed) on = s;
    });
    stops.forEach(s => s.a.toggleAttribute('data-on', s === on));
  };
  /* the dotted path: one dot every ~2.5% of the thread, skipping where a diamond sits */
  const path = document.querySelector('.rail-path');
  const dots = [];
  const layPath = () => {
    if (!path) return;
    path.textContent = ''; dots.length = 0;
    const at = stops.map(s => parseFloat(s.li.style.getPropertyValue('--at')) || 0);
    for (let p = 2.5; p < 100; p += 2.5) {
      if (at.some(a => Math.abs(a - p) < 2)) continue;
      const i = document.createElement('i');
      i.style.setProperty('--at', String(p));
      i.dataset.at = String(p);
      path.appendChild(i); dots.push(i);
    }
  };
  const litPath = () => {
    const max = document.documentElement.scrollHeight - innerHeight;
    const pct = max > 0 ? scrollY / max * 100 : 0;
    dots.forEach(d => d.classList.toggle('lit', parseFloat(d.dataset.at) <= pct + 0.01));
  };
  if (stops.length) {
    place(); layPath(); light(); litPath();
    addEventListener('scroll', litPath, { passive: true });
    addEventListener('scroll', light, { passive: true });
    addEventListener('resize', () => { place(); layPath(); light(); litPath(); });
    if ('ResizeObserver' in window) new ResizeObserver(() => { place(); layPath(); light(); litPath(); }).observe(document.body);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => { place(); layPath(); light(); litPath(); });
  }
  /* Moods. Everything below is time-since-you-last-did-anything: the spider
     settles, then grooms, then eats, then tests its thread, then dozes, and
     after thirteen minutes gives up on you and climbs home up its own silk.
     Any scroll, pointer move, key or touch brings it straight back down. */
  const railEl = document.querySelector('.rail');
  const spiderEl = document.getElementById('railSpider');
  if (railEl && spiderEl) {
    const AFTER = {                       /* milliseconds of stillness */
      settle:   8e3,                      /* breathing and the odd blink */
      groom:   30e3,                      /* rubs its head with a front leg */
      eat:     75e3,                      /* unwraps a morsel and chews it */
      pluck:  18e4,                       /* 3 min — tugs the thread to see if anything is on it */
      doze:   36e4,                       /* 6 min — eyes shut, swaying */
      home:   78e4                        /* 13 min — climbs back up to the top */
    };
    const BURSTS = { groom: 4400, eat: 6600, pluck: 2100 };   /* how long each one lasts */
    const names = Object.keys(BURSTS);
    let active = Date.now(), burstEnd = 0, nextBurst = 0;
    const clearBursts = () => names.forEach(n => railEl.classList.remove(n));
    const wake = () => {
      active = Date.now(); burstEnd = 0; nextBurst = active + 12e3;
      railEl.classList.remove('idle', 'doze'); clearBursts();
      if (away) {                          /* it was up at the top: let it fall back to where you are reading */
        away = false;
        railEl.classList.remove('away', 'climbing', 'up');
        syncSpider();
      }
    };
    const goHome = () => {
      if (away) return;
      away = true; clearBursts();
      railEl.classList.remove('doze', 'idle');
      railEl.classList.add('away', 'climbing', 'up');
      syncSpider();                                  /* sleeps only once it has actually arrived */
    };
    const tick = () => {
      if (document.hidden || reduced) return;
      const now = Date.now(), still = now - active;
      if (still < AFTER.settle) return;
      if (still >= AFTER.home) { goHome(); return; }
      railEl.classList.add('idle');
      if (still >= AFTER.doze) { clearBursts(); railEl.classList.add('doze'); return; }
      railEl.classList.remove('doze');
      if (burstEnd) {                                   /* one thing at a time, then a pause */
        if (now < burstEnd) return;
        clearBursts(); burstEnd = 0; nextBurst = now + 11e3 + Math.random() * 15e3;
        return;
      }
      if (now < nextBurst) return;
      const pool = still >= AFTER.pluck ? names : still >= AFTER.eat ? ['groom', 'eat'] : still >= AFTER.groom ? ['groom'] : null;
      if (!pool) return;
      const pick = pool[Math.floor(Math.random() * pool.length)];
      railEl.classList.add(pick);
      burstEnd = now + BURSTS[pick];
    };
    setInterval(tick, 1000);

    /* The idle clock is driven by *input*, never by the scroll event: a page can
       scroll itself (reflow plus Chrome's scroll anchoring), and a spider that
       treats that as company would never be left alone long enough to do
       anything. Every way a human scrolls sends one of these first. */
    ['wheel', 'keydown', 'pointerdown', 'touchmove'].forEach(e => addEventListener(e, wake, { passive: true }));
    /* eyes follow the pointer, a little */
    addEventListener('pointermove', e => {
      if (reduced || !railEl.getClientRects().length) return;
      const r = spiderEl.getBoundingClientRect();
      const dx = Math.max(-1, Math.min(1, (e.clientX - (r.left + r.width / 2)) / 300));
      const dy = Math.max(-1, Math.min(1, (e.clientY - (r.top + r.height / 2)) / 300));
      const facing = railEl.classList.contains('up') ? 1 : -1;
      spiderEl.style.setProperty('--ex', (dx * facing).toFixed(2));
      spiderEl.style.setProperty('--ey', (dy * facing).toFixed(2));
      wake();
    }, { passive: true });
    document.addEventListener('visibilitychange', () => { if (!document.hidden) wake(); });
    /* a click startles it, then it climbs home (to the top of the page) */
    spiderEl.addEventListener('click', () => {
      wake();
      if (!reduced) {
        railEl.classList.add('startled', 'up');
        setTimeout(() => railEl.classList.remove('startled'), 500);
      }
      scrollTo({ top: 0, behavior: reduced ? 'instant' : 'smooth' });
      syncSpider();
    });
    /* no tooltip, no label: what it is doing has to read from the movement alone */
    wake();
  }
  if (reduced) { const r = document.querySelector('.rail'); if (r) r.classList.add('still'); }
})();
