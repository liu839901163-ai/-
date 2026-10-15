const $ = s => document.querySelector(s);
const form = $('#product'), canvas = $('#canvas'), ctx = canvas.getContext('2d');
let photo = null;
function render() {
  ctx.fillStyle = $('#background').value; ctx.fillRect(0, 0, 1200, 1200);
  if (photo) {const ratio = Math.min(1200 / photo.width, 1200 / photo.height) * Number($('#scale').value) / 100; const w = photo.width * ratio, h = photo.height * ratio; ctx.drawImage(photo, (1200-w)/2, (1200-h)/2, w, h);}
}
function status(message) { $('#status').textContent = message; }
function data() { return Object.fromEntries(new FormData(form)); }
async function request(url, options) {const response = await fetch(url, options); if (!response.ok) {let error; try {error = (await response.json()).error;} catch {error = '请求失败';} throw new Error(error);} return response;}
function jsonOptions() {return {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data())};}
function saveFile(blob, name) {const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href=url; a.download=name; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('#photo').addEventListener('change', async event => {
  const file = event.target.files[0]; if (!file) return;
  if (!['image/jpeg','image/png','image/webp'].includes(file.type) || file.size > 10*1024*1024) {status('请选择小于 10 MB 的 JPG、PNG 或 WebP 图片');return;}
  try {const next = await createImageBitmap(file); if (next.width * next.height > 40000000) {next.close();throw new Error('图片尺寸过大，请缩小到 4000 万像素以内');} if(photo) photo.close(); photo=next; $('#placeholder').hidden=true; $('#download').disabled=false; render(); status('照片已载入，可调整占比后下载主图。');} catch(e) {status(e.message || '无法读取图片');}
});
$('#background').addEventListener('input', render); $('#scale').addEventListener('input', render);
$('#download').addEventListener('click',()=>canvas.toBlob(blob=>{if(blob) saveFile(blob,'product-main-1200.png');},'image/png'));
$('#template').addEventListener('click',()=>{const d=data();if(!d.title.trim()){status('请先填写英文产品标题。');return;} if(d.description.trim() && !confirm('替换现有描述为资料模板？'))return;form.elements.description.value=[d.title, d.material ? `Material: ${d.material}` : '', d.moq ? `Minimum order quantity: ${d.moq}` : ''].filter(Boolean).join('\n\n');status('已按填写内容整理描述，请核对英文及产品事实。');});
form.addEventListener('submit', async event=>{event.preventDefault(); const button=form.querySelector('[type=submit]');button.disabled=true;try {await request('/api/drafts',jsonOptions());status('草稿已保存到当前环境，尚未发布。');await loadDrafts();}catch(e){status(e.message);}finally{button.disabled=false;}});
$('#export').addEventListener('click',async()=>{if(!form.reportValidity())return;try{const r=await request('/api/export',jsonOptions());saveFile(await r.blob(),'product-package.zip');status('资料包已导出；主图请单独下载。产品尚未发布。');}catch(e){status(e.message);}});
async function loadDrafts(){try{const rows=await (await request('/api/drafts')).json();const list=$('#draft-list');list.replaceChildren();if(!rows.length){list.textContent='还没有草稿，完成第一份产品资料后保存在这里。';return;}for(const row of rows){const item=document.createElement('div');item.className='draft';const info=document.createElement('div'), title=document.createElement('strong'),subtitle=document.createElement('small');title.textContent=row.name;subtitle.textContent=row.title;info.append(title,subtitle);const button=document.createElement('button');button.className='text-button';button.textContent='载入资料 ↗';button.addEventListener('click',()=>{if(Array.from(form.elements).some(el=>el.name && el.value.trim())&&!confirm('载入此草稿并替换当前文字资料？'))return;for(const key of ['name','title','material','moq','description','keywords'])form.elements[key].value=row[key]||'';status('已载入文字资料，请确认当前主图与该产品匹配。');$('#editor').scrollIntoView({behavior:'smooth'});});item.append(info,button);list.append(item);}}catch(e){$('#draft-list').textContent='草稿读取失败：'+e.message;}}
$('#refresh').addEventListener('click',loadDrafts);render();loadDrafts();
