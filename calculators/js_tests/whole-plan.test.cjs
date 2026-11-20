const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');

test('autosave action input cannot shadow destination URL; network failure preserves displayed state',async()=>{
 const handlers={};let destination;let feedbackText='';
 const select={value:'tile',dataset:{previous:'laminate'}};
 const root={dataset:{language:'ru'},classList:{add(){}},querySelectorAll:()=>[],setAttribute(){},removeAttribute(){}};
 const feedback={set textContent(v){feedbackText=v},get textContent(){return feedbackText},setAttribute(){},removeAttribute(){}};
 const form={action:{value:'update'},getAttribute:()=>null,reportValidity:()=>true,querySelector:()=>select};
 const target={closest:()=>form,matches:()=>true};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../static/js/whole-plan.js'),'utf8'),{
  document:{querySelector:()=>null,getElementById:id=>id==='whole-result'?root:feedback,addEventListener:(n,f)=>handlers[n]=f},
  window:{scrollY:42,scrollTo(){},addEventListener(){}},location:{href:'http://127.0.0.1/projects/1/whole/'},
  FormData:class{},AbortController,setTimeout,clearTimeout,
  fetch:async url=>{destination=url;throw new Error('synthetic disconnected transport')}
 });
 handlers.change({target});await new Promise(resolve=>setImmediate(resolve));
 assert.equal(destination,'http://127.0.0.1/projects/1/whole/');
 assert.equal(select.value,'laminate');
 assert.match(feedbackText,/Показан прежний результат/);
 assert(!feedbackText.includes('synthetic disconnected transport'));
});

test('file picker validates suffix and size locally, resets on a supported choice, and speaks RU/KK',()=>{
 const handlers={}; let error=''; let reportCount=0;
 const file={files:[],dataset:{analysisMaxBytes:String(5*1024*1024)},
  addEventListener:(n,f)=>handlers[n]=f,setCustomValidity:m=>error=m,reportValidity:()=>{reportCount++}};
 const document={documentElement:{lang:'ru'},querySelector:()=>file,addEventListener(){},getElementById:()=>null};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../static/js/whole-plan.js'),'utf8'),{document,window:{addEventListener(){}}});
 file.files=[{name:'plan.heic',size:100}]; handlers.change(); assert.match(error,/Выберите PDF/);
 document.documentElement.lang='kk';file.files=[{name:'plan.pdf',size:6*1024*1024}]; handlers.change(); assert.match(error,/5 МБ/);
 file.files=[{name:'plan.WEBP',size:100}]; handlers.change(); assert.equal(error,'');
 assert.equal(reportCount,2);
});
