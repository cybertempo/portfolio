/* [LAPTOP] node scripts/check-security.cjs [--local | HTTPS URL]
 * Optional browser check using Puppeteer 23.11.1 / Chrome 131 headless shell.
 * PUPPETEER_MODULE and BROWSER_EXECUTABLE may select existing test tooling.
 * --local serves dist/ through browser interception: no listening port opens.
 * Security probes run in this browser only; no production writes are made.
 */
const puppeteer = require(process.env.PUPPETEER_MODULE || 'puppeteer');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const dist = path.resolve(__dirname, '../dist');
const local = process.argv[2] === '--local';
const target = local ? 'https://portfolio.test/' : (process.argv[2] || 'https://sreenandan-pradeep.vercel.app/');
const headers = Object.fromEntries(JSON.parse(fs.readFileSync(path.join(dist,'vercel.json'))).headers[0].headers.map(h=>[h.key.toLowerCase(),h.value]));
const types = {'.html':'text/html','.css':'text/css','.js':'text/javascript','.svg':'image/svg+xml','.woff2':'font/woff2','.webp':'image/webp','.pdf':'application/pdf','.txt':'text/plain'};
(async()=>{
 const browser = await puppeteer.launch({headless:true,executablePath:process.env.BROWSER_EXECUTABLE||undefined,args:['--no-sandbox','--disable-background-networking','--disable-sync','--no-first-run']});
 try {
  const page = await browser.newPage();
  const errors=[], violations=[], requests=[];
  page.on('pageerror',error=>errors.push(String(error)));
  page.on('request',request=>requests.push(request.url()));
  await page.exposeFunction('recordViolation',directive=>violations.push(directive));
  await page.evaluateOnNewDocument(()=>addEventListener('securitypolicyviolation',event=>window.recordViolation(event.effectiveDirective)));
  if(local){
   await page.setRequestInterception(true);
   page.on('request',request=>{
    const url=new URL(request.url());
    const relative=decodeURIComponent(url.pathname==='/'?'/index.html':url.pathname);
    const file=path.resolve(dist,'.'+relative);
    if(url.origin!==new URL(target).origin || !file.startsWith(dist+path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile())return request.respond({status:404,headers,body:'Not found'});
    return request.respond({status:200,headers:{...headers,'content-type':types[path.extname(file)]||'application/octet-stream'},body:fs.readFileSync(file)});
   });
  }
  await page.setViewport({width:1440,height:960});
  const response=await page.goto(target,{waitUntil:'networkidle0'});
  assert.equal(response.status(),200);
  for(const [key,value] of Object.entries(headers))assert.equal(response.headers()[key],value,`${key} matches configured protection`);
  await page.waitForFunction(()=>document.documentElement.classList.contains('js') && document.querySelector('.rail-spider').style.transform);
  await page.evaluate(()=>scrollTo({top:1600,behavior:'instant'}));
  await page.waitForFunction(()=>document.querySelector('.rail-spider').getBoundingClientRect().top>innerHeight*.3);
  await page.setViewport({width:390,height:844});
  await page.click('.nav-toggle');
  assert.equal(await page.$eval('.nav-toggle',el=>el.getAttribute('aria-expanded')),'true');
  await page.click('.nav-toggle');
  assert.equal(await page.$eval('.nav-toggle',el=>el.getAttribute('aria-expanded')),'false');
  const topic=await page.goto(new URL('topics/security.html',target).href,{waitUntil:'networkidle0'});
  assert.equal(topic.status(),200);
  assert(await page.$eval('h1',el=>el.textContent.length>0));
  assert.deepEqual(errors,[],'normal page scripts have no exceptions');
  assert.deepEqual(violations,[],'normal page and topic have no security-policy violations');
  assert(requests.every(url=>new URL(url).protocol==='data:' || new URL(url).origin===new URL(target).origin),'normal browsing uses only own resources');
  console.log('PASS normal desktop, mobile menu and topic page; no console errors, CSP violations or external requests');
  const protections=await page.evaluate(async()=>{
   const el=document.createElement('div');
   el.textContent='safe text';
   const safe=el.textContent==='safe text';
   let htmlBlocked=false,policyBlocked=false,evalBlocked=false;
   try{el.innerHTML='<b>untrusted markup</b>';}catch(error){htmlBlocked=error instanceof TypeError;}
   try{trustedTypes.createPolicy('audit',{createHTML:value=>value});}catch(error){policyBlocked=error instanceof TypeError;}
   try{(0,eval)('window.__auditEvalRan=true');}catch(error){evalBlocked=error instanceof EvalError || error instanceof TypeError;}
   const script=document.createElement('script');
   script.appendChild(document.createTextNode('window.__auditInlineRan=true'));
   document.head.append(script);
   let connectionBlocked=false;
   try{await fetch(new URL('robots.txt',location.origin));}catch{connectionBlocked=true;}
   await new Promise(resolve=>setTimeout(resolve,150));
   return {safe,htmlBlocked,policyBlocked,evalBlocked,inlineBlocked:!window.__auditInlineRan,connectionBlocked};
  });
  for(const [name,passed] of Object.entries(protections))assert(passed,name);
  assert(violations.includes('connect-src'),'connection was blocked by CSP, not a network failure');
  assert(violations.includes('require-trusted-types-for'),'browser enforced HTML sink protection');
  console.log('PASS safe text allowed; HTML injection, policy bypass, eval, inline scripts and script connections blocked');
  console.log(`check-security: PASS — ${local?'local build (no open ports)':target}`);
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
