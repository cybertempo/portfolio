/* [LAPTOP] node scripts/check-spider.cjs [preview URL]
 * Build and start scripts/serve.py first. Requires Puppeteer 23.11.1 and its
 * Chrome 131 headless shell (the versions used for the recorded verification).
 * Test tooling only; no browser dependency is shipped with the portfolio.
 * PUPPETEER_MODULE can point to an existing Puppeteer installation;
 * BROWSER_EXECUTABLE can select its headless browser. Leave both unset when
 * Puppeteer is installed normally. Re-run these checks after upgrading either.
 * Writes disposable visual review and measurements under build/spider-check/.
 */
const puppeteer = require(process.env.PUPPETEER_MODULE || 'puppeteer');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const output = path.resolve(__dirname, '../build/spider-check');
fs.mkdirSync(output, {recursive:true});
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
(async () => {
 const browser = await puppeteer.launch({headless:true, executablePath:process.env.BROWSER_EXECUTABLE || undefined, args:['--no-sandbox','--disable-background-networking','--disable-sync','--no-first-run']});
 try {
 const page = await browser.newPage(), errors=[];
 page.on('pageerror', error => errors.push(String(error)));
 await page.setViewport({width:1440,height:960,deviceScaleFactor:1});
 await page.goto(process.argv[2] || 'http://127.0.0.1:8791/',{waitUntil:'networkidle0'});
 await page.evaluate(() => {
  document.documentElement.style.scrollBehavior='auto';
  window.pose=()=>{
   const svg=document.querySelector('.spider'), spider=document.querySelector('.rail-spider');
   const m=new DOMMatrix(getComputedStyle(svg).transform);
   const track=spider.parentElement.getBoundingClientRect();
   const silk=document.querySelector('.rail-silk').getBoundingClientRect();
   const rect=spider.getBoundingClientRect();
   const paths=[...svg.querySelectorAll('.legs path')];
   return {t:performance.now(), angle:Math.atan2(m.b,m.a)*180/Math.PI,det:m.a*m.d-m.b*m.c,
    position:rect.top+rect.height/2-track.top, silk:silk.bottom-track.top,
    classes:document.querySelector('.rail').className,
    paths:paths.map(p=>p.getAttribute('d')),
    feet:paths.map(p=> {const nums=p.getAttribute('d').match(/-?\d+(?:\.\d+)?/g).map(Number);const point=new DOMPoint(nums[4],nums[5]).matrixTransform(p.getScreenCTM()); return {x:point.x,y:point.y};}),
    lineX:track.left+track.width/2};
  };
  window.record=async(duration,velocity,stall=false)=>{
   const start=performance.now(), origin=scrollY, frames=[];
   window.snapshots=[];
   return new Promise(resolve=>{
    const tick=time=>{
     const elapsed=time-start;
     scrollTo({top:origin+elapsed*velocity,behavior:'instant'});
     frames.push(window.pose());
     if(window.snapshots.length<8 && elapsed>window.snapshots.length*140){
      const clone=document.querySelector('.spider').cloneNode(true);
      window.snapshots.push({svg:clone,rotation:clone.style.transform,time:Math.round(elapsed)});
     }
     if(stall && elapsed>500 && elapsed<550){const end=performance.now()+180;while(performance.now()<end){}}
     if(elapsed<duration)requestAnimationFrame(tick);else resolve(frames);
    };requestAnimationFrame(tick);
   });
  };
  scrollTo({top:document.documentElement.scrollHeight*.65,behavior:'instant'});
 });
 await wait(2200);
 const initial=await page.evaluate(()=>pose());
 assert(Math.abs(initial.angle-180)<.1,'initial descent points down');
 const climb=await page.evaluate(()=>record(1800,-1.2));
 assert(climb.some(s=>s.classes.includes('gripping')),'climb activates articulated legs');
 assert(climb.some(s=>s.angle>20 && s.angle<160),'intermediate turning poses are rendered');
 assert(climb.every(s=>Math.abs(s.det-1)<.00001),'turn preserves body area (no flattening/reflection)');
 assert(climb.every(s=>Math.abs(s.position-s.silk)<.1),'silk stays connected to spider');
 assert(new Set(climb.map(s=>s.paths.join(' '))).size>20,'legs have many distinct poses');
 const roots=[[16,16],[15,19],[15,22],[16,25],[24,16],[25,19],[25,22],[24,25]];
 for(const sample of climb)sample.paths.forEach((d,i)=>assert.deepEqual(d.match(/-?\d+(?:\.\d+)?/g).slice(0,2).map(Number),roots[i],'leg root stays attached'));
 const gripDrift=[];
 for(let i=1;i<climb.length;i++){
  const a=climb[i-1], b=climb[i];
  if(a.angle!==0 || b.angle!==0 || a.t-climb[0].t<850)continue;
  a.feet.forEach((f,j)=>{const g=b.feet[j];if(Math.abs(f.x-a.lineX)<1.2 && Math.abs(g.x-b.lineX)<1.2 && Math.abs(f.x-g.x)<.04)gripDrift.push(Math.abs(f.y-g.y));});
 }
 assert(gripDrift.length>30,'control: sampled planted feet throughout climb');
 assert(Math.max(...gripDrift)<.15,'planted feet hold their world position');
 const steadyClimb=climb.filter(s=>s.angle===0 && s.t-climb[0].t>900);
 assert(steadyClimb.length>15,'control: enough steady climbing frames');
 for(const i of [2,3,6,7]) {
  const tips=steadyClimb.map(s=>s.paths[i].match(/-?\d+(?:\.\d+)?/g).map(Number).slice(4));
  assert(tips.every(([x])=>Math.abs(x-20)>4),'rear feet stay clear of the silk');
  for(const axis of [0,1])assert(Math.max(...tips.map(p=>p[axis]))-Math.min(...tips.map(p=>p[axis]))<.1,'rear feet ride with the body, without stepping');
 }
 assert(new Set(steadyClimb.map(s=>s.paths[0])).size>15,'control: front legs still reach and pull');
 console.log('PASS front legs pull; rear legs remain tucked without phantom footholds');
 console.log('PASS climb: eight attached legs, planted feet, continuous rotation, connected silk; max foot drift',Math.max(...gripDrift).toFixed(3),'px');
 // Display frozen, enlarged poses for a visual review, without changing source.
 await page.evaluate(()=>{
  const panel=document.createElement('div');panel.id='pose-review';panel.className='rail';
  panel.style.cssText='position:fixed;left:40px;right:40px;top:180px;height:280px;transform:none;display:flex;gap:30px;background:var(--bg);border:1px solid var(--secondary);padding:40px;z-index:9999;opacity:1';
  snapshots.forEach(s=>{const tile=document.createElement('div');tile.style.cssText='width:120px;flex:1;color:var(--text);font:14px monospace';const label=document.createElement('div');label.textContent=`${s.time} ms`;const svg=s.svg.cloneNode(true);tile.append(svg,label);svg.style.transform=s.rotation;svg.style.width='120px';svg.style.height='160px';svg.querySelectorAll('*').forEach(el=>el.style.animation='none');panel.append(tile);});
  document.body.append(panel);
 });
 await page.screenshot({path:path.join(output,'poses.png')});
 await page.evaluate(()=>document.querySelector('#pose-review').remove());
 await page.mouse.move(100,100);
 await wait(2000);
 await page.evaluate(()=>{window.mutations=0;window.observer=new MutationObserver(records=>mutations+=records.length);observer.observe(document.querySelector('.rail-spider'),{attributes:true,subtree:true});});
 await wait(350);
 assert.equal(await page.evaluate(()=>mutations),0,'animation frame loop stops after settling');
 const quickDown=await page.evaluate(()=>record(150,1));
 const quickUp=await page.evaluate(()=>record(250,-1));
 assert([...quickDown,...quickUp].every(s=>Math.abs(s.det-1)<.00001),'mid-turn reversals preserve shape');
 const reverse=await page.evaluate(()=>record(1000,.8));
 assert(reverse.every(s=>Math.abs(s.det-1)<.00001),'reverse also preserves shape');
 // The motion clock caps delayed frames; on a busy machine a wall-clock
 // second of scrolling need not contain a full second of animation updates.
 await page.waitForFunction(()=>Math.abs(pose().angle-180)<.1,{timeout:6000});
 assert((await page.evaluate(()=>pose())).angle>179,'reverse finishes head down');
 assert(await page.evaluate(()=>mutations)>0,'control: observer sees active animation');
 await page.evaluate(()=>observer.disconnect());
 console.log('PASS turn in both directions; animation loop sleeps when settled');
 await wait(1800);
 await page.evaluate(async()=>{const y=scrollY;for(let i=0;i<12;i++){scrollTo({top:y+(i%2?0:3),behavior:'instant'});await new Promise(requestAnimationFrame);}});
 assert(!(await page.evaluate(()=>pose().classes)).includes('up'),'tiny scroll jitter does not reverse orientation');
 await page.setOfflineMode(true);
 const session=await page.createCDPSession();await session.send('Emulation.setCPUThrottlingRate',{rate:6});
 const slow=await page.evaluate(()=>record(2200,-.6,true));
 assert(slow.some(s=>s.classes.includes('gripping')),'climb runs offline under CPU load');
 assert(slow.every(s=>Math.abs(s.det-1)<.00001),'slow frames preserve shape');
 let maxJump=0;for(let i=1;i<slow.length;i++)maxJump=Math.max(maxJump,Math.abs(slow[i].position-slow[i-1].position));
 assert(maxJump<14,'busy frame cannot teleport spider');
 console.log('PASS offline, 6x CPU throttling and 180 ms stall; max travel/frame',maxJump.toFixed(3),'px');
 await session.send('Emulation.setCPUThrottlingRate',{rate:1});await page.setOfflineMode(false);
 await page.emulateMediaFeatures([{name:'prefers-reduced-motion',value:'reduce'}]);
 await page.evaluate(()=>scrollTo({top:1000,behavior:'instant'}));await wait(200);
 const reduced=await page.evaluate(()=>({pose:pose(),active:document.querySelector('.rail').getAnimations({subtree:true}).filter(a=>a.playState==='running').length}));
 assert.equal(reduced.active,0,'reduced motion disables animations');assert(!reduced.pose.classes.includes('gripping'));
 await page.emulateMediaFeatures([{name:'prefers-reduced-motion',value:'no-preference'}]);
 await page.setViewport({width:800,height:900});await wait(200);
 assert.equal(await page.evaluate(()=>getComputedStyle(document.querySelector('.rail')).display),'none');
 await page.setViewport({width:1440,height:960});await wait(1800);
 assert(Math.abs((await page.evaluate(()=>pose())).position-(await page.evaluate(()=>pose())).silk)<.1);
 console.log('PASS live reduced-motion preference and viewport resizing');
 // Advance the idle clock without waiting thirteen minutes.
 await page.evaluate(()=>{const now=Date.now.bind(Date);window.realNow=now;Date.now=()=>now()+781000;});
 await wait(1200);
 assert((await page.evaluate(()=>pose().classes)).includes('away'),'idle climb begins');
 await page.waitForFunction(()=>document.querySelector('.rail').classList.contains('doze'),{timeout:15000});
 assert((await page.evaluate(()=>pose())).position<.05,'idle climb reaches top before sleeping');
 await page.evaluate(()=>{Date.now=realNow;dispatchEvent(new Event('wheel'));});
 await wait(2500);
 assert(!(await page.evaluate(()=>pose().classes)).includes('away'),'input restores scroll position');
 await page.evaluate(()=>document.querySelector('.rail-spider').click());
 await page.waitForFunction(()=>scrollY===0,{timeout:10000});
 await wait(1800);
 assert((await page.evaluate(()=>pose())).position<.05,'click-to-top settles at top');
 console.log('PASS idle climb, sleep, wake and click-to-top');
 assert.deepEqual(errors,[],'browser console has no uncaught exceptions');
 fs.writeFileSync(path.join(output,'measurements.json'),JSON.stringify({climb,slow,errors},null,2));
 console.log('PASS all browser checks; artifacts:',output);
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
