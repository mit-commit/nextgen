// Data source: data/people.xml; edit that file to update members.
function logDebug(...args){
  console.log(...args);
  const log = document.getElementById('debug-log');
  if (log) log.textContent += args.map(a=>typeof a==='string'?a:JSON.stringify(a,null,2)).join(' ') + "\n";
}

function byLastName(a,b){
  const al=(a.name||'').split(/\s+/).slice(-1)[0].toLowerCase();
  const bl=(b.name||'').split(/\s+/).slice(-1)[0].toLowerCase();
  return al.localeCompare(bl);
}

function bucketFor(title){
  const t=(title||'').toLowerCase();
  if (t.includes('professor')) return 'faculty';
  if (t.includes('graduate')) return 'grad';
  if (t.includes('meng')) return 'meng';
  if (t.includes('urop')) return 'urop';
  if (t.includes('visiting')) return 'visiting';
  if (t.includes('postdoc')) return 'researchers';
  if (t.includes('research scientist') || t.includes('affiliate')) return 'researchers';
  return 'researchers';
}

function personLink(p){
  const url = p.url || p.oldurl || p.nourl;
  return url ? `<a href="${url}" target="_blank" rel="noopener">${p.name}</a>` : p.name;
}

(async function(){
  try {
    const xmlText = await getText('data/people.xml');
    const xml = new DOMParser().parseFromString(xmlText, 'application/xml');

    // --- Current people ---
    const current = Array.from(xml.querySelectorAll('current > person')).map(p=>({
      name: p.getAttribute('name'),
      title: p.getAttribute('title')||'',
      url: p.getAttribute('url'),
      oldurl: p.getAttribute('oldurl'),
      nourl: p.getAttribute('nourl')
    }));
    current.sort((a,b)=> (a.title||'').localeCompare(b.title||'') || byLastName(a,b));

    const buckets={
      faculty: document.getElementById('faculty'),
      researchers: document.getElementById('researchers'),
      grad: document.getElementById('grad'),
      meng: document.getElementById('meng'),
      urop: document.getElementById('urop'),
      visiting: document.getElementById('visiting')
    };

    current.forEach(p=>{
      const li=document.createElement('li');
      li.className='person';
      li.innerHTML=`<strong>${personLink(p)}</strong>${p.title?` — ${p.title}`:''}`;
      (buckets[bucketFor(p.title)]||buckets.researchers).appendChild(li);
    });

      // --- Alumni: group by year with subheaders (double column), most->least ---
const alumni = Array.from(xml.querySelectorAll('alumni > person')).map(p=>({
  name: p.getAttribute('name'),
  title: p.getAttribute('title')||'',
  year: parseInt(p.getAttribute('year')||'0',10) || 0,
  startyear: parseInt(p.getAttribute('startyear')||'0',10) || 0,
  title2: p.getAttribute('title2')||'',
  year2: parseInt(p.getAttribute('year2')||'0',10) || 0,
  position: p.getAttribute('position')||'',
  url: p.getAttribute('url'),
  oldurl: p.getAttribute('oldurl'),
  nourl: p.getAttribute('nourl')
}));

// Group by year
const groups = new Map();
for (const a of alumni) {
  const y = a.year || 0; // 0 = unknown year
  if (!groups.has(y)) groups.set(y, []);
  groups.get(y).push(a);
}

// Sort years desc (0/unknown last)
const years = Array.from(groups.keys()).sort((a,b) => {
  if (a===0 && b!==0) return 1;
  if (b===0 && a!==0) return -1;
  return b - a;
});

const mount = document.getElementById('alumni');
mount.innerHTML = ''; // clear

years.forEach(y=>{
  // Year subheader
  const h = document.createElement('h3');
  h.textContent = y ? String(y) : 'Other';
  mount.appendChild(h);

  // Container with two ULs
  const container = document.createElement('div');
  container.className = 'grid2';
  const left = document.createElement('ul'); left.className='person';
  const right = document.createElement('ul'); right.className='person';
  container.appendChild(left); container.appendChild(right);

  // Fill two columns
  groups.get(y).sort(byLastName).forEach((p,i)=>{
    // display only the highest role; the year comes from the section header
    // (title2/year2/startyear stay in the data for the roster, his ruling 2026-08-27)
    const li=document.createElement('li'); li.className='person';
    li.innerHTML=`${personLink(p)} — <em>${p.title||''}</em>`;
    if (p.position){
      const pos=document.createElement('div');
      pos.className='person-position';
      pos.textContent=p.position;
      li.appendChild(pos);
    }
    (i%2? right:left).appendChild(li);
  });

  mount.appendChild(container);
});

logDebug('Rendered alumni groups',{years: years.length});


    logDebug('Rendered', {current: current.length, alumni: alumni.length, yearBuckets: years.length});
  } catch (error){
    console.error(error);
    const mount=document.getElementById('alumni')||document.body;
    const p=document.createElement('p');
    p.style.color='#b00';
    p.textContent='Could not load people.xml. Run with a local server (e.g., python -m http.server) and check console for details.';
    mount.prepend(p);
  }
})();
