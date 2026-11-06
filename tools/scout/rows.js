// After score.js finishes: builds pipe rows for the top 80 by views/day. Then read them 8 at a time:  window.__rows.slice(0,8).join('\n'), (8,16), ...
window.__rows = (window.__scoutItems || []).slice(0, 80).map(x => [x.code, x.user, x.views, x.likes, x.age_days, x.vpd, x.dur,
  x.audio_type === 'licensed_music' ? 'L' : 'O', (x.song || '').slice(0, 28).replace(/\|/g, ' '), x.audio_id, (x.srcs || []).join('+')].join('|'));
'rows ' + window.__rows.length
