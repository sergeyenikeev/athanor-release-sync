import sys, wave
sys.path.insert(0, r'D:\d\ouroboros\out\video')
from pathlib import Path
import make_video as M
AUDIO = Path(r'D:\d\ouroboros\out\video\build\audio')
t = 0.0
def ts(x):
    m = int(x // 60); s = x % 60
    return f'00:{m:02d}:{s:05.2f}'
print('FRAG | start    | end      | dur   | tag')
for i, fr in enumerate(M.FRAGMENTS, 1):
    wp = AUDIO / (f'frag{i:02d}.wav')
    with wave.open(str(wp), 'rb') as f:
        dur = f.getnframes() / float(f.getframerate())
    start = t; t += dur
    ws = [s[0] for s in fr['scenes']]; wsum = sum(ws)
    sc = '; '.join(f'{s[0]}/{wsum}={dur*s[0]/wsum:.1f}s' + (f' ×{s[2]}anim' if len(s) > 2 else '') for s in fr['scenes'])
    tag = fr['tag']
    print(f'{i:2d}   | {ts(start)} | {ts(t)} | {dur:5.2f} | {tag:24s} | {sc}')
print(f'TOTAL audio: {t:.2f}s = {ts(t)}')
