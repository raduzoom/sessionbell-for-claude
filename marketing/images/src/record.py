"""Record the Sessionbell demo from the made-up snapshot page as PNG frames plus a concat list with durations.

Story: All -> Pocket Shop tab -> dismiss the stuck session -> pin the dark-mode question -> open a question.
Run from the project root, after `python3 -I tools/snapshot.py`, with a scratch folder for the frames:
  uv run --with playwright==1.63.0 python marketing/images/src/record.py "$PWD" <scratch>/frames
Then, inside <scratch>/frames:
  ffmpeg -y -f concat -i list.txt -vf "scale=1600:1000:flags=lanczos,fps=24,format=yuv420p" -c:v libx264 -crf 20 -preset slow -movflags +faststart <project>/marketing/images/sessionbell-demo.mp4
  ffmpeg -y -f concat -i list.txt -vf "fps=12,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle" <project>/marketing/images/sessionbell-demo.gif
The frames folder's old PNGs are replaced on each run, so never point it at a folder you keep.
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

root, frames = Path(sys.argv[1]), Path(sys.argv[2])
frames.mkdir(parents=True, exist_ok=True)
for f in frames.glob("*.png"):
    f.unlink()  # scratch frames only, inside the scratchpad
W, H = 1280, 800
MOTION = 1 / 24
CURSOR = """
(() => {
  const d = document.createElement('div'); d.id = 'fake-cursor';
  d.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 2 L4 19 L8.5 15 L11.5 22 L14.5 20.7 L11.6 14 L17.5 14 Z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  Object.assign(d.style, {position: 'fixed', left: '0', top: '0', zIndex: 99999, pointerEvents: 'none', transform: 'translate(640px, 500px)'});
  document.body.appendChild(d);
  // Never follow claude:// links while recording; the page's own handler still shows "Opening…".
  document.addEventListener('click', e => { const a = e.target.closest('a[href^="claude:"]'); if (a) e.preventDefault(); }, true);
})();
"""
END_CARD = """
(() => {
  const o = document.createElement('div');
  Object.assign(o.style, {position: 'fixed', inset: '0', zIndex: 100000, display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center', gap: '18px', background: 'rgba(244,246,250,0.94)',
    backdropFilter: 'blur(6px)', fontFamily: getComputedStyle(document.querySelector('h1')).fontFamily, color: '#14171c'});
  o.innerHTML = '<div style="font-size:64px;font-weight:650;letter-spacing:-0.5px">Sessionbell</div>' +
    '<div style="font-size:28px;color:#3b4250">See which Claude Code sessions are waiting on you</div>' +
    '<div style="font-size:20px;color:#5b6472;margin-top:8px">Free · runs on your Mac · open source</div>';
  document.body.appendChild(o);
})();
"""

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    ctx = b.new_context(viewport={"width": W, "height": H}, color_scheme="light", device_scale_factor=2)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto((root / "design/page-check/build/snapshot-demo-light.html").as_uri())
    pg.wait_for_selector("#app:not([aria-busy])")
    pg.wait_for_timeout(400)
    pg.evaluate(CURSOR)
    pos = [640.0, 500.0]
    items = []

    def shot(dur):
        n = len(items)
        path = frames / f"f{n:04d}.png"
        pg.screenshot(path=str(path))
        items.append((path.name, dur))

    def move(x, y, secs=0.7):
        steps = max(2, round(secs / MOTION))
        x0, y0 = pos
        for i in range(1, steps + 1):
            t = i / steps
            e = t * t * (3 - 2 * t)  # ease in-out
            cx, cy = x0 + (x - x0) * e, y0 + (y - y0) * e
            pg.evaluate(f"document.getElementById('fake-cursor').style.transform='translate({cx}px,{cy}px)'")
            pg.mouse.move(cx, cy)
            shot(MOTION)
        pos[:] = [x, y]

    def center(sel):
        bb = pg.locator(sel).first.bounding_box()
        return bb["x"] + bb["width"] * 0.35, bb["y"] + bb["height"] / 2

    def click():
        pg.mouse.click(*pos)
        for _ in range(4):
            shot(MOTION)

    def box(sel):
        bb = pg.locator(sel).first.bounding_box()
        return bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2

    def menu(sid, item, hold=1.4):
        move(*center(f'[data-key="row:{sid}"]')); click(); shot(0.8)
        move(*box('[data-key="more:detail"]'), 0.5); click(); shot(0.5)
        x, y = box(f'[data-key="menu:{item}"]')
        bb = pg.locator(f'[data-key="menu:{item}"]').first.bounding_box()
        move(bb["x"] + 60, y, 0.45); click(); shot(hold)

    shot(1.4)                                   # All projects, first question selected
    move(*center('[data-key="pill:shop"]')); click(); shot(1.2)   # second tab: Pocket Shop
    menu("local_demo-05", "dismiss", 1.6)       # dismiss the stuck one: toast with Undo
    menu("local_demo-02", "pin", 1.4)           # pin the dark-mode question
    move(*center('[data-key="row:local_demo-01"]')); click(); shot(1.4)
    ox, oy = center('[data-key="open"]')
    move(ox + 20, oy); pg.mouse.click(*pos)
    for _ in range(8):                          # "Opening…" with its spinner, in real time
        pg.wait_for_timeout(90)
        shot(0.12)
    pg.wait_for_timeout(1300)
    shot(0.5)
    pg.evaluate(END_CARD)
    pg.wait_for_timeout(200)
    shot(2.6)
    b.close()

with open(frames / "list.txt", "w") as f:
    for name, dur in items:
        f.write(f"file '{name}'\nduration {dur:.4f}\n")
    f.write(f"file '{items[-1][0]}'\n")
print("frames:", len(items), "seconds:", round(sum(d for _, d in items), 1), "errors:", errors)
