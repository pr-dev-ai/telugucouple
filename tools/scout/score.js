// Paste once after all grabs (CFG = filters + seen list). Runs in the background; poll with:  JSON.stringify(window.__scoutState)
(() => {
  const CFG = __CFG__;
  const A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
  const pk = c => { let n = 0n; for (const ch of c.slice(0, 11)) n = n * 64n + BigInt(A.indexOf(ch)); return n.toString(); };
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const box = JSON.parse(sessionStorage.getItem('__scoutCodes') || '{}');
  const codes = Object.keys(box).filter(c => !(CFG.seen || []).includes(c));
  const S = window.__scoutState = { done: false, total: codes.length, n: 0, kept: 0, rejected: {} }; window.__scoutItems = [];
  const rej = w => S.rejected[w] = (S.rejected[w] || 0) + 1;
  (async () => {
    for (const c of codes) {
      try {
        const r = await fetch('/api/v1/media/' + pk(c) + '/info/', { headers: { 'X-IG-App-ID': '936619743392459' }, credentials: 'include' });
        S.n++;
        if (!r.ok) { rej('http' + r.status); if (r.status === 429) { await sleep(30000); } continue; }
        const it = ((await r.json()).items || [])[0] || {}; const cm = it.clips_metadata || {};
        const mi = (cm.music_info || {}).music_asset_info || {}; const os = cm.original_sound_info || {};
        const now = Date.now() / 1000, age = (now - (it.taken_at || now)) / 86400, views = it.play_count || it.ig_play_count || 0;
        const x = { code: c, url: 'https://www.instagram.com/reel/' + c + '/', user: (it.user || {}).username, views, likes: it.like_count || 0,
          comments: it.comment_count || 0, taken_at: it.taken_at, age_days: +age.toFixed(1), vpd: Math.round(views / Math.max(1, age)),
          dur: +(it.video_duration || 0).toFixed(1), audio_type: cm.audio_type || '', song: mi.title || os.original_audio_title || '',
          artist: mi.display_artist || '', audio_id: mi.audio_asset_id || os.audio_asset_id || '', w: it.original_width, h: it.original_height,
          caption: ((it.caption || {}).text || '').slice(0, 120).replace(/\s+/g, ' '), srcs: box[c] };
        if (it.media_type !== 2) rej('not video');
        else if ((CFG.exclude_users || []).includes(x.user)) rej('own account');
        else if (it.is_paid_partnership) rej('paid partnership');
        else if (views < CFG.min_views) rej('under ' + CFG.min_views + ' views');
        else if (age > CFG.max_age_days) rej('older than ' + CFG.max_age_days + ' days');
        else if (x.dur < CFG.min_dur || x.dur > CFG.max_dur) rej('length outside ' + CFG.min_dur + '-' + CFG.max_dur + ' s');
        else if ((it.coauthor_producers || []).length > 1) rej('collab');
        else { window.__scoutItems.push(x); S.kept++; }
      } catch (e) { rej('error'); }
      await sleep(450 + Math.random() * 400);
    }
    window.__scoutItems.sort((a, b) => b.vpd - a.vpd); S.done = true;
  })();
  return JSON.stringify(S);
})()
