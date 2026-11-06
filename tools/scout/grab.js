// Paste on every hashtag / audio page (full page loads wipe window state, so codes live in sessionStorage). Replace SRC.
await (async (SRC) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  for (let i = 0; i < 4; i++) { window.scrollTo(0, document.body.scrollHeight); await sleep(1400); }
  const box = JSON.parse(sessionStorage.getItem('__scoutCodes') || '{}');
  const codes = [...new Set([...document.querySelectorAll('a[href*="/reel/"], a[href*="/p/"]')].map(a => a.getAttribute('href').split('/').filter(Boolean).pop()))];
  for (const c of codes) if (/^[A-Za-z0-9_-]{11}$/.test(c)) (box[c] = box[c] || []).includes(SRC) || box[c].push(SRC);
  sessionStorage.setItem('__scoutCodes', JSON.stringify(box));
  return JSON.stringify({ src: SRC, found: codes.length, total: Object.keys(box).length });
})('SRC')
