const {chromium}=require('playwright');
(async()=>{
  const options={headless:true,args:['--no-sandbox']};
  if(process.env.CHROMIUM_PATH) options.executablePath=process.env.CHROMIUM_PATH;
  const browser=await chromium.launch(options);
  for(const [name,width,height] of [['desktop',1440,900],['mobile',390,844]]){
    const page=await browser.newPage({viewport:{width,height}}), errors=[], failures=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('response',r=>{if(r.url().includes('/privacy-observatory/')&&r.status()>=400)failures.push(`${r.status()} ${r.url()}`)});
    await page.goto('http://127.0.0.1:8765/privacy-observatory/',{waitUntil:'networkidle'});
    await page.reload({waitUntil:'networkidle'});
    await page.locator('canvas').first().waitFor();
    const size=await page.evaluate(()=>[document.documentElement.scrollWidth,innerWidth]);
    const count=await page.locator('canvas').count();
    if(size[0]!==size[1]||count!==2||errors.length||failures.length)throw Error(JSON.stringify({name,size,count,errors,failures}));
    if(await page.locator('.warning').count()) throw Error('missing data');
    await page.getByRole('button',{name:'交易活动'}).click();
    if((await page.getByRole('button',{name:'交易活动'}).getAttribute('class'))!=='active')throw Error('switch');
    console.log(name,'reload, data, charts, layout, switch OK');
    await page.close();
  }
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
