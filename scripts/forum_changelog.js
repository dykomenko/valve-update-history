// Deadlock forum changelog -> per-thread line counts (data/deadlock_forum.psv).
//
// The forum sits behind a "checking your browser" page, so it is read from a real browser session instead of a script:
// open https://forums.playdeadlock.com/forums/changelog.10/ in a normal browser tab, paste this into the console,
// and copy the printed table. Only counts are kept, never the posts' text.
//
// Columns: title|post_ts|chars|entries|fix|new|tune|other|embed   (embed = the post is just a link card to Steam News)
// The classifier is the same as classify() in build_data.py.

(async () => {
  const HEADER = /^(\[.*\]|=+|-{3,}|[A-Za-z0-9 &\/'’\-]{2,40}:)$/;
  function classify(text) {
    const out = { entries: 0, fix: 0, nw: 0, tune: 0, other: 0 };
    for (const raw of text.split('\n')) {
      const line = raw.replace(/^[\s\-•*–·]+/, '').trim();
      if (!line || HEADER.test(line)) continue;
      out.entries++;
      if (/\bfix(ed|es|ing)?\b/i.test(line)) out.fix++;
      else if (/^(added|adding|new|introduced|re-?added|enabled|unlocked|released)\b/i.test(line)) out.nw++;
      else if (/\d/.test(line) || /\b(increased|decreased|reduced|lowered|raised|buffed|nerfed|rebalanced|adjusted|tweaked|changed|improved|no longer|now)\b/i.test(line)) out.tune++;
      else out.other++;
    }
    return out;
  }
  // 1. thread list (the forum clamps page numbers, so stop when a page repeats)
  const threads = new Map();
  for (let p = 1; p <= 8; p++) {
    const html = await (await fetch(`/forums/changelog.10/page-${p}`)).text();
    const doc = new DOMParser().parseFromString(html, 'text/html');
    let added = 0;
    doc.querySelectorAll('.structItem--thread').forEach(el => {
      if (el.querySelector('.structItem-status--sticky')) return;
      const a = [...el.querySelectorAll('.structItem-title a')].pop();
      if (!threads.has(a.getAttribute('href'))) { threads.set(a.getAttribute('href'), a.textContent.trim()); added++; }
    });
    if (!added) break;
  }
  // 2. first post of every thread
  const rows = [];
  const list = [...threads];
  for (let i = 0; i < list.length; i += 8) {
    rows.push(...await Promise.all(list.slice(i, i + 8).map(async ([href, title]) => {
      const doc = new DOMParser().parseFromString(await (await fetch(href)).text(), 'text/html');
      const art = doc.querySelector('article.message');
      const text = art.querySelector('.bbWrapper').innerText.replace(/[ \t]+\n/g, '\n').trim();
      const st = classify(text);
      const first = text.split('\n')[0].trim();
      const embed = /Steam News\s*$/.test(first) ? first.replace(/ - Steam News$/, '').replace(/^Deadlock - /, '') : '';
      const ts = art.querySelector('time.u-dt').getAttribute('data-timestamp');
      return [title.replace(/ Update/, ''), ts, text.length, st.entries, st.fix, st.nw, st.tune, st.other, embed].join('|');
    })));
  }
  console.log('title|post_ts|chars|entries|fix|new|tune|other|embed\n' + rows.join('\n'));
})();
