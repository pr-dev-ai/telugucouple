"""Pronunciation guard for Padma's voice (Pradeep, 4 Nov: "make sure we did not repeat that pronunciation mistake ... the entire conversations").

Every TTS take is transcribed with ElevenLabs Scribe (Telugu) and compared with the script, character by character, word by word.
A Telugu word the listener would hear differently (ఈరోజు heard as "ఈ లోహీ") is flagged. English words are not scored
(Scribe writes them in either script), only Telugu ones.

  python pron_check.py <audio.mp3> <script.txt>      # prints the per-word check, exit 1 if anything is flagged
"""
import json, pathlib, re, sys, unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
TE = re.compile(r"[ఀ-౿]")
VIRAMA, ZW = "్", "‌‍"
_re_letter = re.compile("[\u0C15-\u0C39]")   # a consonant
PASS = 0.86            # matched share of the word's characters; one wrong consonant in a 5-char word = 0.8 -> flagged
# spelling variants that sound the same (Scribe and the script may write either)
SAME = [("ళ్ళ", "ళ్ల"), ("ఁ", ""), ("ౕ", ""), ("ౖ", "ై"), ("శ", "స"),
        ("య్యిం", "యిం"), ("డటం", "డడం"), ("డటమ", "డడమ")]   # అయ్యింది/అయింది, చూడటం/చూడడం: same word, two spellings   # శ/స: both are normal Hyderabad speech


def key():
    for line in open(ROOT / ".env"):
        if line.startswith("ELEVENLABS_API_KEY="): return line.split("=", 1)[1].strip().strip('"')
    sys.exit("ELEVENLABS_API_KEY missing in .env")


def scribe(audio, tries=4):
    """ElevenLabs speech-to-text, Telugu. Returns the response dict (text, words[...] with start/end). Retries the VM's network blips."""
    import requests, time
    err = None
    for i in range(tries):
        try:
            with open(audio, "rb") as f:
                r = requests.post("https://api.elevenlabs.io/v1/speech-to-text", headers={"xi-api-key": key()}, timeout=120,
                                  data={"model_id": "scribe_v1", "language_code": "tel", "tag_audio_events": "false"},
                                  files={"file": (pathlib.Path(audio).name, f, "audio/mpeg")})
            if r.ok and "text" in r.json(): return r.json()
            err = f"{r.status_code} {r.text[:200]}"
        except Exception as e:
            err = repr(e)
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"scribe failed: {err}")


def tel(s):
    """Telugu letters only, normalized, no spaces/punctuation/Latin (so ఈ రోజు == ఈరోజు and transliterated English is just an insertion)."""
    s = unicodedata.normalize("NFC", s)
    for a, b in SAME: s = s.replace(a, b)
    return "".join(c for c in s if TE.match(c) and c not in ZW)


def words_of(script):
    return [w for w in re.split(r"\s+", script) if w.strip()]


VSIGN = dict(zip("ఆఇఈఉఊఎఏఐఒఓఔ", "ాిీుూెేైొోౌ"))


def elide(ws):
    """Second spoken form: a vowel-ending word before a vowel-starting word drops its vowel (ని అండి -> నండి, officer ని అండి)."""
    ws = list(ws); signs = set(VSIGN.values())
    for i in range(len(ws) - 1):
        a, b = tel(ws[i]), tel(ws[i + 1])
        if a and b[:1] in VSIGN.keys() | {"అ"} and not a.endswith(VIRAMA) and TE.match(a[-1]):
            core_end = len(ws[i].rstrip("?!.,।…"))
            w = ws[i][:core_end]; tail = ws[i][core_end:]
            if w[-1] in signs: w = w[:-1]
            elif not ("\u0C15" <= w[-1] <= "\u0C39"): continue          # ends in an independent vowel / anusvara: leave it
            ws[i] = w + ("" if b[0] == "అ" else VSIGN[b[0]]) + tail
            first = next(j for j, c in enumerate(ws[i + 1]) if TE.match(c))
            ws[i + 1] = ws[i + 1][:first] + ws[i + 1][first + 1:]
    return ws


def sandhi(ws):
    """Spoken joins the listener expects: చేశావ్ అని is said చేశావని. Letters move to where they are heard; nothing is lost."""
    ws = list(ws)
    for i in range(len(ws) - 1):
        a, b = tel(ws[i]), tel(ws[i + 1])
        if a.endswith(VIRAMA) and b[:1] in VSIGN.keys() | {"అ"}:
            k = ws[i].rfind(VIRAMA)                                   # drop the final virama: the consonant takes the vowel
            ws[i] = ws[i][:k] + ("" if b[0] == "అ" else VSIGN[b[0]]) + ws[i][k + 1:]
            first = next(j for j, c in enumerate(ws[i + 1]) if TE.match(c))
            ws[i + 1] = ws[i + 1][:first] + ws[i + 1][first + 1:]    # the next word loses its first (independent) vowel
    return ws


def align(s, h):
    """Edit-distance alignment (not difflib's greedy blocks): where[i] = index in h that s[i] matched, or None."""
    n, m = len(s), len(h)
    D = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1): D[i][0] = i
    for j in range(m + 1): D[0][j] = j
    for i in range(1, n + 1):
        si, row, prev = s[i - 1], D[i], D[i - 1]
        for j in range(1, m + 1):
            row[j] = min(prev[j - 1] + (0 if si == h[j - 1] else 1), prev[j] + 1, row[j - 1] + 1)
    where, i, j = [None] * n, n, m
    while i and j:
        if s[i - 1] == h[j - 1] and D[i][j] == D[i - 1][j - 1]: where[i - 1] = j - 1; i -= 1; j -= 1
        elif D[i][j] == D[i - 1][j - 1] + 1: i -= 1; j -= 1
        elif D[i][j] == D[i - 1][j] + 1: i -= 1
        else: j -= 1
    return where


def check(script, heard):
    """Both spoken forms are fine (with and without vowel elision between words): per word, the better score counts."""
    a, b = _check(script, heard, False), _check(script, heard, True)
    return [y if (y["score"] or 0) > (x["score"] or 0) else x for x, y in zip(a, b)]


def _check(script, heard, elision):
    """Per script word: score = share of its Telugu characters found in order in what Scribe heard. Latin words -> None (not scored)."""
    ws = words_of(script); said_as = sandhi(elide(ws) if elision else ws)
    spans, s_all = [], ""
    for w in said_as:
        t = tel(w); spans.append((len(s_all), len(s_all) + len(t))); s_all += t
    if isinstance(heard, str): heard = [{"text": heard}]
    h_all, owner = "", []                       # owner[j] = which Scribe word letter j of the transcript belongs to
    for k, hw in enumerate(heard):
        t = tel(hw["text"]); h_all += t; owner += [k] * len(t)
    where = align(s_all, h_all); hit = [w is not None for w in where]
    res = []
    for w, (a, b) in zip(ws, spans):
        if b == a:
            res.append({"word": w, "score": None if not tel(w) else 1.0, "heard": ""}); continue
        m = sum(hit[a:b]); n = b - a
        own = [where[i] for i in range(a, b) if hit[i]]
        if own:     # what she said for this word: from its first to its last matched letter (extra syllables inside count against it)
            said = h_all[own[0]:own[-1] + 1]
        else:       # nothing matched: whatever was heard between the neighbouring words
            prev = next((where[i] for i in range(a - 1, -1, -1) if hit[i]), -1)
            nxt = next((where[i] for i in range(b, len(s_all)) if hit[i]), len(h_all))
            said = h_all[prev + 1:nxt]
        score = m / max(n, len(said))
        if n <= 2 and m < n: score = min(score, 0.5)     # 1-2 letter words: any miss counts
        r = {"word": w, "score": round(score, 2), "heard": said}
        lo = own[0] if own else prev + 1; hi = own[-1] if own else nxt - 1
        if owner and 0 <= lo <= hi < len(owner) and "start" in heard[owner[lo]]:
            r["t"] = [heard[owner[lo]]["start"], heard[owner[hi]]["end"]]
        r["_own"] = own
        res.append(r)
    # extra sounds she made that are not in the script (coffee_v2: "ఈ లోహీ" before ఆయన). English words in the script may come back
    # transliterated (office -> ఆఫీస్), so a gap right after an English word is allowed.
    last_h, latin_between = -1, False
    for i, r in enumerate(res):
        own = r.pop("_own", None)
        if r["score"] is None: latin_between = True; continue
        if not own: continue
        gap = h_all[last_h + 1:own[0]]
        if _re_letter.search(gap) and not latin_between:   # even one extra syllable (నా పపని) counts; a leftover vowel sign does not   # (a sandhi letter left over is not extra)
            r.update(extra=gap, word_ok=r["score"] >= PASS, score=0.0, heard=gap + "|" + r["heard"])
            if "start" in heard[owner[last_h + 1]]: r["t"] = [heard[owner[last_h + 1]]["start"], r.get("t", [0, heard[owner[own[0]]]["end"]])[1]]
        last_h, latin_between = own[-1], False
    if res and last_h < len(h_all) - 3 and not latin_between:        # trailing extra after the last word
        r = next(x for x in reversed(res) if x["score"] is not None)
        r.update(extra=h_all[last_h + 1:], word_ok=r["score"] >= PASS, score=0.0)
    return res


def flagged(res):
    return [r for r in res if r["score"] is not None and r["score"] < PASS]


AKSHARA = re.compile(r"(?:[క-హౘ-ౚ]్)*[క-హౘ-ౚ][ా-ౌౕౖ]?[ఁ-ః]?"
                     r"|[అ-ఔౠౡ][ఁ-ః]?|.", re.S)


def respellings(word):
    """Ways to write a word that ElevenLabs may say right, in the order to try (ఈరోజు -> ఈ రోజు was the fix that worked)."""
    core = re.sub(r"[^ఀ-౿]", "", word); tail = word[len(word.rstrip("?!.,।")):]
    ak = AKSHARA.findall(core)
    out = []
    if len(ak) >= 3: out.append("".join(ak[:1]) + " " + "".join(ak[1:]))          # split after the first syllable
    if len(ak) >= 4: out.append("".join(ak[:len(ak) // 2]) + " " + "".join(ak[len(ak) // 2:]))
    if len(ak) >= 2: out.append("-".join(ak))                                        # syllable by syllable
    out.append(core)                                                                 # plain retake (takes vary)
    seen, res = set(), []
    for o in out:
        if o not in seen: seen.add(o); res.append(o + tail)
    return res


def report(res):
    return " ".join(r["word"] if r["score"] is None or r["score"] >= PASS else f"[{r['word']}→{r['heard']} {r['score']}]" for r in res)


if __name__ == "__main__":
    audio, script = sys.argv[1], pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")
    r = scribe(audio); res = check(script, [w for w in r["words"] if w.get("type") == "word"])
    print("heard:", r["text"]); print("check:", report(res))
    bad = flagged(res); print("FLAGGED:" if bad else "OK", [(b["word"], b["heard"], b["score"], b.get("t")) for b in bad])
    sys.exit(1 if bad else 0)
