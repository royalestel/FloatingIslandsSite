# Handoff: the C64 build of the routine (parts 1-4), as of the end of the "Colour ramp + raster splits" chat

Branch `claude/c64-raytraced-rasterbars-1iigat` (push only there; `git pull` before every push; no PR unless asked).
Working folder `c64-raybars/`.  The user is a visual tester who iterates fast and likes SHORT explanations.  Send
videos/files with SendUserFile (videos `display: "attach"`, stills `"render"`); long renders in the background; the stop
hook wants everything committed and pushed (keep files that are still being rendered uncommitted until they decode).
Cloud container tools: cc65 (cl65/ca65/ld65), py65 (`c64cpu.py`), ffmpeg, PIL, **VICE 3.7.1 (x64sc) via xvfb-run** (needs the
dummy ROMs in /usr/share/vice/C64 -- recreate them if the container is new, see below), `mk_d64.py`.

## The film (video) -- DONE and approved
`part1.mp4` (1830 frames, from `part1_proc.py`'s model), `part2.mp4`, `part3.mp4`, `part4.mp4`, `routine_full.mp4`: 60 fps,
CRT look.  Parts 2-4 in the video are the 7-column version and use the OLD shading (no in-bar parity) -- they have not been
re-rendered after part 1 was finalised; the C64 versions use 6 columns (decided with the user).

## Part 1 on the C64 -- DONE, VICE-verified
`part1p.s` + `part1p_gen.py` (+ `part1_proc.py` = bit-exact spec, `sim_part1p.py`, `vice_check_p.py`, `mk_cart_p.py`,
`routine_p.crt`, `part1p.prg`).  Procedural beginning (sine/smoothstep tables, 8-bit maths, quarter-square multiply) for frames
0..1269, then a stream (bar arrays + records) from 1270.  Swatch tables have two blocks (second = line parities swapped; bars with
an odd first line add 32) so a bar's look follows the row's parity INSIDE its bar.  Simulator: all 1830 frames equal the spec,
update worst 93 % of the blank; VICE: pixel exact.  (Its stable raster WAITX is still the old value; parts 2c/3c use WAITX 8 + odd `bit`.)

## Parts 2-4 on the C64 (6 columns: 32|64x4|32 px) -- IN PROGRESS
Engine (VICE-verified): ONE loop of 200 (part 3: 185) lines, 63 cycles a line, X = line:
`lda P0,x / sta $d021` x6 (8 cycles apart) then `lda G+1,x / sta $3fff` (next line's idle byte, written in the right border),
`inx / cpx / bne`.  Each column and the idle byte is a byte pattern of a page (page-aligned, read at offsets 0..255, no page
crossings).  Settings found in VICE: WAITX = 8 with the odd `bit $00` (compare falls on the line change), HTUNE = 0, column 1 starts at
x = 33; check with `-VICIImodel 6569` (the 8565 shows a 1-px grey dot per mid-line write).  DEN must be high before line 51, so the
stable IRQ stays at line 49 (the loop may END early, never START late).

* `part2c.*` (DONE): part 2's earthquake (frames 0..1063): each column reads the still floor's pattern at `pattern + C0 - d`, 7 patched bytes
  a frame from `part2.shake_offsets` (6 columns); ghost swatches + idle pattern while all columns share a shift, flat swatches + zero idle
  otherwise.  `part2c_gen.py`, `vice_check_2c.py` (`FREEZE=n python3 mk_cart_p.py part2c part2c.crt` = test build that stays on frame n).
* `part3c.*` (DONE): part 3's waves (484 frames): 7 pages per frame parity, the stream in ROML banks = runs `[page][line][len] bytes`;
  schedule by simulating the pages (blank j prepares frame j with priority and may start on j+1); 70 KB; worst blank 7,240 cycles of
  ~7,686; 13 peak frames (317-327, 0-1) show up to 40 lines one frame late.  `part3_dump.py` (frames -> /tmp/part3_frames.pkl),
  `part3c_gen.py`, `vice_check_3c.py`.  Build: `SPLITS=6 python3 part3_dump.py && SPLITS=6 python3 part3c_gen.py && python3 mk_cart_p.py part3c part3c.crt`.
* **TODO part 2's waves** (frames 1064..1895: W-waves with palettes blue/red/multicolour, white flashes): same engine as part3c: dump the frames
  like `part3_dump.py` (from `part2.py`'s sequence: `make_seq()` + `wave_tokens`/`gp2.segments`, SPLITS=6), generate the change stream, build a
  cart; then JOIN parts 2c + 2-waves + 3c into one program/cart (one loop, the earthquake's shifted-pattern mode and the stream mode; the stream part
  needs the stream-mode pages to start in the state the earthquake ends in -- the still floor, frame 1063).
* **TODO part 4** (1304 frames): the user said the RANDOM part need not match the video: build it PROCEDURALLY with a small pseudo-random generator moving a
  limited number of (bar, column) pieces (the video has ~500 changed cells a frame: too many for the blank); the rest (circling, flashes, lining up, the
  nearest bar's sweep) as in `part4.py`.  Use the same page engine; pieces are composed into the pages (restore from a pristine floor page, draw).
* **TODO** the whole routine as one cartridge (EasyFlash, 1 MB): part 1 (procedural) + parts 2-4; the cart boot `cartboot.s` copies the program image
  from ROML banks to RAM and the stream stays in banks (`$01 = $37` while reading, `$de00` = bank).  Also re-render parts 2-4 of the video with the
  in-bar parity and the new floor if the user wants the video to match the C64.
* The user's other ideas: a disk (.d64) with a fast loader from the Karateka work (D:\c64\karateka2, `NOTES.md` "Fast loader": drive.s/fl.s;
  folder not reachable from the cloud), probably only after the cart is done.

## Costs measured (for planning)
Blank = about 7.7 k cycles with the loop on lines 0-184 (6.5 k with 200 lines).  Delta copy ~14 cycles a byte + ~80 a run + ~600 fixed.  Moving all
6 columns of the floor each frame with the 6-store trick would cost ~6 k.  The quarter-square 8x8 multiply is ~50 cycles.

## Recreating the VICE test setup in a new container
`apt-get install -y vice` (then `xvfb-run` exists); VICE needs ROMs: create dummy 8 KB `kernal-901227-03.bin` (reset vector irrelevant), 8 KB
`basic-901226-01.bin`, 4 KB `chargen-901225-01.bin` in /usr/share/vice/C64 (the cart boots from the EasyFlash's own ROMH).  Run
`x64sc +sound -warp -VICIIfilter 0 -VICIIextpal -VICIIpalette colodore -VICIImodel 6569 -remotemonitor -remotemonitoraddress ip4://127.0.0.1:6510
-cartcrt X.crt` and talk to the monitor on port 6510 (see `vice_check_2c.py`: `screenshot "file" 2`, `m addr addr`); kill stray `x64sc`/`Xvfb`
after each run (`pkill -x`, never `pkill -f`).

## Gotchas learned
* `cl65 -D` does not reach ca65: pass `-Wa -DNAME=v`.  ca65 needs `-g` for `-Ln` labels.  Cheap `@` labels break across macros.
* `ldy #n / bpl` loops only work for n <= 127.  `bpl` after `ldy #0` tests Y, not the loaded value (sign extension bug).
* A stale "done" monitor event can come from an old log: check the file before trusting it.
* Do not start a second render writing the same mp4; `pkill -f` kills your own shell.

## Update: everything joined (end of the "go" chat)
* `python3 mk_cart_all.py` -> `routine_all.crt` (parts part1p, part2c, part2w, part3c, part4c chained; 16K mode, ROML+ROMH banks).  Each part ends with `jmp $0200`: the
  resident loader (cartboot_all.s, copied to $0200, part number in $02ff) loads the next part to $0801; after the last it wraps to part 1.  Streams: `partNc_gen.py` read
  /tmp/*_frames.pkl from `part2_dump.py` (2w), `part3_dump.py` (3c), `part4_dump.py` (4c; uses part4m.py = part4.py with columns taking turns + few trips).  Each stream part starts
  on its own first frames (a cut at the joins).  VICE: chain checked visually through all parts; parts 2w pixel-exact (vice_check_2w.py); part 4c NOT pixel-checked.
* Part 4 is the thinned model: 245 of 1296 frames have lines one frame late (mean 96 lines).  Part-2 waves 26 late frames, part 3 11.
* Video: `c64_routine_all.mp4` (part1.mp4 + models of 2c/2w/3c/4c via render_c64_model.py 2|3|4).

## NTSC branch `claude/c64-raybars-ntsc` (PAL stays on `claude/c64-raytraced-rasterbars-1iigat`)
* 6567R8: 65 cycles a line, 263 lines.  Every film frame is shown for 2 frames (30 Hz motion, the film runs ~1.67x longer).
* Part 1: rows padded to 65 cycles (dly 15 nops), two line buffers (LB0 $0400 / LB1 $0600, one per frame parity), the work split over
  the two blanks (even: bars + clear 0-109, odd: clear 110-199 + draw).  `sim_part1n.py`: all frames equal the spec, worst blank 3.6 k of ~3.8 k.
  WAITX 5, HTUNE 1, `bit $00`.  VICE pixel-exact.
* Column engine (2c / 2w / 3c / 4c): loop + `nop` = 65 cycles; the stable raster needs WAITX 8 + PRE 1 + `bit $00` (the single compare window that
  absorbs the 1-cycle jitter), HTUNE 0; the row loop must stay inside one page (`c64build.py` pads with SLEDPAD nops: a page-crossing `bne` = 66
  cycles = drifting columns); the idle loop is 100 nops + jmp (2-cycle jitter only).  2c: update every second blank (`sub`).  Streams: one record per
  blank, `NF2` = 2 x frames, budget 4,000 cycles (stale frames: 2w 9, 3c 0, 4c 218).
* VICE checks: screenshots crop at y = 23 (CROPY); `-VICIImodel 6567`; `/tmp`-style multi-screenshot sampling (one VICE session, `x` to resume) was what
  exposed the per-frame jitter.  2c, 2w, 3c pixel-exact; 4c exact except stale frames and rows 185-199 (the loop ends at 184, as on PAL).
* `python3 mk_cart_all.py routine_ntsc.crt` = the whole routine (chains and loops in VICE).  Video: `c64_routine_ntsc.mp4`.

## Part 1 final motion + music (NTSC branch)
* Motion (decided with mock-ups, see mock_full1d.py / mock_*.py): the 3 aligned bars 6 lines higher (all stack bars shifted together, eased in 1270 -> 1400, out with the
  rotation), the 3 bottom bars rise from film time 1345 (was 1400), the scene rotates with the stack's own spacing (flatter easing, no spreading), and from 25 % of the
  rotation every bar moves in a STRAIGHT LINE (centre line + thickness) to its place on the final floor (1 blank line between bars; nearest bar 159..184).
  All of it is in `part1r_gen.py` (my_stack / my_bars_all / _bars_at).  The mock rose the bottom bars unshifted until 1400 and then jumped 6 lines; the code shifts them with the rest.
* Music: Alpha by LukHash (2021), used with his permission (the owner has it).  `music/Alpha.sid` -> `music/Alpha.dat` (PSID data, load $1000, init $1000, play $1003, ZP $fe/$ff only,
  play = 1.1 k cycles mean, 1.6 k max).  Layout: tune $1000-$2A33, rows0 $2B00, tables $3D00, rows1 $4000.  `musicplay` runs in the blank before `update`; NTSC calls it 5 frames in 6
  (the tune is 50 Hz); the generator reserves each frame's real play cost in the delta budget (stale frames: 2 in 1d).  The SID is silenced at the end of part 1.  NTSC plays the tune
  ~3.8 % high (the PAL freq table on the NTSC clock).  Sim: update + tune worst 3,667 cycles of a ~3,770-cycle blank (+ ~130 before line 48).
* The music files and the built files that contain the tune (part1r.prg/.crt, routine_ntsc.crt) are in .gitignore on purpose: ask the owner before pushing them.
* Checks: sim_part1r.py (all 2,194 frames equal the model), vice_check_1r.py (12/12 exact on the 6567), x64sc audio capture vs the sidplayfp render (envelope corr 0.73, +3.7 % pitch).

## Part 2 earthquake: packed shake table (NTSC branch)
* `part2c_gen.py` packs the shifts: a frame = 3 bytes (6 nibbles, shift + 8), `$ff, n` = keep the shifts for n more frames (pauses cost 2 bytes).  1,758 bytes (was 8,939) for 1,277 frames.
  NTSC samples `shake_offsets` at film time n * 5/6 and updates EVERY blank (60 Hz; the old every-second-blank doubling is gone); PAL (PLATFORM=PAL) samples 1:1.
* `part2c.s` decodes in `update` (nibble -> operand low byte through `optab`, mode = all six equal, ~100 cycles); `hold` counts the frames of a `$ff, n` run.  The `START` test option is gone (no random access); `FREEZE` still works.
* VICE 6567: 7/7 captures pixel-exact.  Part 2's waves (part2w) still use the old 2-blanks-a-frame doubling.

## Part 2 waves (part2w): frame doubling removed (NTSC branch)
* One blank per frame again: `part2_dump.py` samples the film at frame round(n * 5/6) (NTSC, 1000 frames) and colours it with the DISPLAYED frame's parity; `part2w_gen.py` has the single-blank
  scheduler (record x = the blank before frame x: prepares frame x, may start x+1; NTSC budget 3000 cycles of runs, PAL 6700); `part2w.s` takes the page parity from fcl & 1 again, wrap at NF.
* Cost: at 60 Hz every frame changes (mean 111 changed bytes, p90 236, max 454 against ~200 bytes of budget), so 600 of 1,000 frames show some stale lines (median 20, 90 % 84, 179 frames over 64
  lines, max 128).  A whole-lines-from-the-top scheduler was tried and was worse (677 frames).  The doubled version had 9 stale frames of 832 with 2 blanks per film frame.
* Test carts of the stream parts must be built with `mk_cart_all.py` (16 KB banks): `mk_cart_p.py` cuts 8 KB banks and shows garbage.  VICE 6567: exact on the frames that are not stale by design.
* Parts 3 and 4 (part3c, part4c) still use the doubled scheme.

## Parts 2-4 on the NEW floor + option 1 (NTSC branch)
* New floor (the one part 1 ends on, 1 blank line between bars, lines 58..185): `ghost_preview.NEWFLOOR` (OLDFLOOR=1 keeps the old one).  Regenerate with `part2c_gen.py`, `part2_dump.py`, `part3_dump.py`, `part4_dump.py`, then the wave gens.
* Option 1 = the update also works through the empty top lines.  `blockend` writes DEN low and calls `update`; the stream record is `[F][nA][runs][nB][runs]` (`wavesched.py`):
  group A runs before line 49, then `update` polls `$d012` and writes DEN high itself (lines 49-50, no IRQ: the stream window needs $01 = $37, where an IRQ would read its vector
  from the KERNAL ROM), group B runs until the stable IRQ, which `update` arms at the end for line 49 + F (F = the first active line of the frame about to be shown; F < 3 -> 0 = the old
  way: rows from 0, the stable IRQ writes DEN at line 49).  The rows loop starts at row F (`rows+1` patched), the first idle byte too.  `irq0` is no longer used.
* Budgets (runs only, est. cycles): A = 4,000; B = 65 F - 450 (F = 0: none).  VICE 6567: part 3 (part2w/part3c) exact on every capture, part 4 exact apart from the known bottom cut + stale frames.
* Stale frames (new floor), without / with option 1: part2w 296 / 9 of 1000, part3c 11 / 0 of 484, part4c 187 / 104 of 1296 (258 frames have F = 0: pieces at the top use the old budget).

## NTSC: part 4 = new motion (mock_part4_seq), busy stretch held, crash fixed
* Motion: `mock_part4_seq.py` (one random bar per column starts every 10 frames, random speed/swing, a random subset speeds up as more move,
  original matching/slowdown; nothing above visible line 50 or below row 184; nearest bars rise 76 lines).  Frames: `part4h_dump.py` ->
  /tmp/part4h_frames.pkl; `HOLD2=1 FRAMES=/tmp/part4h_frames.pkl python3 part4c_gen.py`.
* Busy stretch (frames 270..729) is HELD in pairs: picture AND flicker phase the same for frames 2k, 2k+1 and both shown from the same page set
  (record F bit 7 = hold: the engine's set variable `pset` does not toggle).  Stale frames 681 -> 212 of 1116 (median 0 lines).
  Holding only the picture (flicker at 60 Hz) saves nothing: the flicker makes the two sets differ every frame.
* Stream record x is applied in the blank BEFORE frame x + 1 (the generator now writes blanks[x + 1] at position x; F is that frame's).
* Crash fixed (all three parts): when arming the stable IRQ, write the new compare BEFORE acking $d019 -- a match of the old compare (last
  frame's stage-2 line) while the update ran stayed latched and fired stage 1 at once -> stage 2 broken, irq2 txs with junk X.  Also stage 1
  writes nt1 instead of inc $d012, and DEN is lowered if the target was missed.
* VICE 6567: part2w, part3c pixel exact; part4c pixel exact against the generator's shown frames (stale lines modelled:
  /tmp/part4c_shown.pkl, `SHOWN=... vice_check_4c.py`, strict); no stack drift over ~21,500 frames.
* Cartridge (part1r + part2c + part2w + part3c + part4c): 58 of 64 16K banks (~928 KB of 1 MB).

## NTSC SID pitch (branch claude/c64-raybars-ntsc-sid)
* Alpha.sid is a PAL tune (header flags: PAL clock; note table tuned for 985248 Hz: A-4 = 439.97 Hz).  On NTSC (1022727 Hz) it played 3.8 % (65 cents) sharp.
  Calling the player less often would only slow the tempo (pitch comes from the frequency values), so the fix is in the data: `music_ntsc_patch.py`
  rescales the 95-note 16-bit table (hi bytes $1714.., lo bytes $177c.., read as lda $1713,y / lda $177b,y) by 985248/1022727 ->
  `music/Alpha_ntsc.dat` (A-4 = 439.94 Hz on NTSC).  Zero run-time cost.  `part1r_music.s` includes the NTSC file; c64build.py runs the patch when
  needed (the music files stay out of the repository).  VICE 6567 check: strong spectral peaks drop by 0.957-0.966 (expected 0.963).
* The tune is still called 5 times in 6 frames (50 Hz tempo).  Only part 1 plays music.

## SID playback in parts 2 and 3 (branch claude/c64-raybars-ntsc-sid)
* Alpha.sid stays resident at $1000-$2A33 from part 1.  Parts 2c/2w/3c run their tables above it ($2B00+: cfg `load` at $1000 in the image, `run` at $2B00);
  the loader (cartboot_all.s) starts at $0800 (mk_cart_all.py prefixes the image with one byte so the 256-byte chunks line up with $1000) and parts flagged
  in bit 15 of their start address skip $1000-$2AFF (dst jumps to $2B00).  Part 4 is not flagged (its pages overwrite the tune) and silences the SID at its start.
* `musicplay` (5 calls in 6 frames, NTSC) in each part's blank: 2w/3c in `blockend` before the update, 2c after `update` (tail call).  A call costs 280-1540 cycles
  (mean 1000; py65 over 1500 calls): wavesched.A_BUDGET = 3600 - MUSIC_COST (run the generators with MUSIC_COST=1700).  Stale frames: 2w 24 -> 134 of 1000, 3c 42 -> 130 of 582.
* Part 1 no longer silences the SID at its end.  Test carts: `python3 mk_cart_all.py /tmp/t2w.crt tunepart part2w` (tunepart.s loads + inits the tune, then chains);
  `CRT=/tmp/t2w.crt python3 vice_check_2w.py ...`.  The loader gap between parts (~5 frames) pauses the tune.
* VICE 6567: 2c, 2w, 3c pixel exact; chained audio: music plays from part 1 through part 3 (~86 s), silent in part 4, restarts with the loop.

## NTSC cartridge at the mock-up's timing (60 film frames a second)
* The owner timed the animation to the music in the python mock-ups (one film frame per 1/60 s).  The NTSC parts now show ONE FILM FRAME PER FRAME
  (`RATE = 1.0` in `part1r_gen.py`, `part2c_gen.py`, `part2_dump.py`, `part3_dump.py`; part 4 already did).  The tune still plays 5 frames in 6.
* The SID branch (`claude/c64-raybars-ntsc-sid`) is merged in: this branch had its python side but not its 6502 sources (the loader expected the
  tune-resident layout the part sources did not have).
* Part 1 (`part1r_gen.py`, rewritten) draws what `mock_part1_flicker.py` draws: the three circling bars, three more between them from frame 960 (blinking in),
  the red bars from the beat at 1218 (flicker in, depth swatches 4..1, back to blue as each lines up in the stack), the red-over-blue transparency (the
  blue bar's swatch from the red ramp), solid red where two red bars overlap, the stack, the 1 s pause, the straight 1.5 s move to part 2's floor and the
  2 s hold (ends at `part1.T_JOIN` = 1910).  Frames < 960: routines (3 bars, as before).  Frames >= 960: a STREAM of runs of changed buffer rows
  copied from interned shape arrays (blue / red-tinted bar arrays, constant arrays), composed by `compose()` exactly like the mock (it imports the mock for
  the extra bars and `red_state` / `red_swatch_for`).  Gaps of up to 4 unchanged rows are bridged; BUDGET 3700 (worst update + tune 3,682 cycles in the sim).
* Buffer code (8 bits): level 1..24 | centre<<5 | blk<<6 | red<<7 (red with level 25..29 = a flat red swatch, never dimmed).  blk = the swatch table block =
  the bar-relative row parity (min(i, T-1-i), the mock's) XOR the screen row's parity (the finished floor: screen parity, as part 2).  The dim MAP is 256
  bytes x 16 dim levels ($C000-$CFFF), code -> swatch index 64*red + 32*blk + level (7 bits); the swatch tables (`part1r.inc` COLT / GHT) have 128 entries
  per (frame parity, row parity) = blue ramp blocks 0/1 + red ramp blocks 0/1 ($5200-$55FF); the shape arrays use $0D40.., $3D00-$3EFF, $3F00 and
  $5600-$7FFF.  Stream records of the stream part: [dim level][number of runs][runs]; the engine reads the dim map pointers with $01 = $35 (they are under the ROM window).
* Part 1 shapes now come from `gp.PROF` (the mock's profiles) + the centre bit, not `q.FULL`.  Differences from the mock-up in the dimmed stretch: the
  centre rows are per bar (the mock merges overlapping bars), 16 dim levels instead of 31.  Stale lines: 360 of 950 stream frames, mean 7 lines (frames
  with more than 20: 25), mostly in the first frames after 960 and in the 1700-1790 move.  Rebuild order: `part1r_gen.py`, build, `part1r_gen.py`
  again (the array pool follows the build's `codeend`), build.  `sim_part1r.py 1908`: 1,909 frames equal the model; `vice_check_1r.py`: the model is
  rendered from the buffer, the dim map and the swatch tables.
* Part 2 earthquake (`part2c`): 860 frames (the last tremor is gone, the waves start 1 s after the quake); the floor patterns are part2.py's still
  floor by SCREEN-row parity; a column's page = frame parity EOR its shift's parity (part2c.s).  Whole-floor quakes are pixel exact; while the
  columns differ the engine uses flat swatches on every line (the model keeps ghost swatches where a line's columns agree): ~93-97 % of pixels.
* Part 2 waves: no pauses between the waves (732 frames); part 3: 484; part 4: 1116 (its stream was regenerated: the committed one did not match
  `mock_part4_seq.py` any more).  Wave streams built with `MUSIC_COST=1700`.
* `python3 mk_cart_all.py routine_ntsc.crt`: whole routine, 3 stream banks for part 1.  VICE 6567, whole chain, 51 screenshots against the models: part 1 19/19 exact (six bars, red, floor),
  earthquake 5/9 exact (see above), part 2 waves 6/7, part 3 4/5 (stale lines by design), part 4 10/11 (one shot matched no frame: probably
  taken mid-frame).  Total 5,102 frames = 85 s.

## Part 4 keeps the tune playing (NTSC)
* `part4c.s` now has part 3's music hooks (`mc`, `musicplay` before `update` in the blank, no SID silencing); `part4c.cfg` = part 3's (the pages are stored at $1000 in the image and
  run at $2B00, above the tune); `mk_cart_all.py` lists part4c in SKIP_TUNE (the loader leaves $1000-$2AFF alone).  The wrap to part 1 re-inits the tune.
* `part4c_gen.py` budgets each blank with the tune's real play cost (`tunecost.py`: the tune on the 6502 simulator through the calls of the whole routine, the dearest call within +-3
  calls of the blank; `wavesched.budgets(F, music)`); `NOTUNE=1` = no tune (the old numbers).  `HOLDRANGE=a,b` (part4h_dump.py, part4c_gen.py) sets the held stretch (default 270,730).
* Cost of the music in part 4: stale frames 224 -> 674 of 1116 (lines of a frame that show the previous frame; mean 87 lines in those frames, frames 100-900); holding a
  wider stretch (down to 100-900) does not help (506 frames), the picture simply changes more than 1 blank per pair can carry.  VICE: 11 of 12 part 4 shots exact (the 12th has
  stale lines by design), the SID registers change throughout part 4.  Real fixes: the delayed-copy design (`mock_part4_wave.py`) or a cheaper copy engine.

## Part 4 copy loop unrolled twice (NTSC)
* `doruns` in `part4c.s`: a run is now [first line][page address HIGH byte][length] bytes (`part4c_gen.py` `record4`; PAGE0_HI = $2B; parts 2w / 3c keep `ws.record`), the next-run pointer is one add, and the
  copy loop is unrolled twice (odd lengths enter at the second half).  Fitted on the 6502 simulator with 400 real runs: the plain loop cost 14 x bytes + 113 per run (the generator had
  assumed 81 per run), the new one 12.5 x bytes + 123 per run (per-run overhead went UP by 10: the second copy's operands are patched too).  Unrolling 4x would not pay (more patching).
* The generator's cost model is now fitted (`C_BYTE`, `C_RUN` env override).  With the TRUE costs of both engines and the tune in the budget: plain loop 761 stale frames of 1116, unrolled 591
  (median stale lines 55 -> 11).  Without the tune: 224.  VICE: 11 of 12 part 4 shots exact, the 12th one stale line; the SID changes throughout.

## Part 4 as DELAYED COPIES with the SPLIT SHIFT (`part4d`, NTSC) -- the default part 4 of `mk_cart_all.py`
* `part4d_gen.py` (the design of `mock_part4_wave.py`: two movement sources A / B, the six columns show them delayed by 16 k frames), `part4d.s` / `part4d.cfg` (part4c's raster loop and `doruns`),
  `sim_part4d.py`, `part4d_video.py` (the C64's own frames), `mock_part4_shift.py` (the shift's schedule: `shift(k, t)`, also the python mock-up).  `python3 mk_cart_all.py out.crt part1r part2c part2w part3c part4c`
  builds the old change-stream part 4 instead.
* A source frame is ONE page of colour bytes (rows 54..184, at page offsets C0 + row, C0 = 16); the engine copies the newest page of each source into a ring slot (two rings of 66 slots, RAM $2B00-$B3FF;
  identical pages share a slot) and each record patches the loop's 7 page operands: [F][hi x 7][lo x 6][nA][runs][nB][runs].  The idle byte pages (zero page, Ge, Go) must lie BELOW $8000 (`update` reads row F's
  idle byte with the ROM window mapped).  `start` clears the zero page and the margins of every page (RAM is not cleared; 200,000 cycles = 12 frames).
* THE SHIFT: every split moves up and down as a whole, 16 lines, its own period (72..134 frames; splits 1 and 4, not adjacent, run twice as fast at full amplitude: `FAST`, `FAST_X` in mock_part4_shift.py, periods 43 and 36 at the peak), eased in from frame 270 (+ its delay), eased out to rest by the last matchup (frame 731 + its delay): the LOW byte of
  the column's page operand (C0 - d: page offset C0 + line - d never crosses a page; costs 6 record bytes and ~40 cycles).  Rows below 184 are cut.  Going UP shrinks F (the update must end before line 49 + F): all busy
  frames still fit at 16 lines up (the generator checks every frame with its shifted F); at 24 only 19% would.  An odd shift keeps the flicker pair attached to the picture (the page was baked for the unshifted row
  parity; the other phase would need a second copy of the page): 35,154 rows of the shifted frames differ from the mock by that phase only.  Uniform frames (the hold and the wipe) are not shifted (the idle byte page is global).
* Busy frames: ghost swatches off (every token flat): 5,154 rows differ from the mock (4.2 a frame, at most 25) where it keeps ghost swatches because all six columns agree.  Uniform frames (from 926: the rest, the hold and the
  wipe): ghost swatches as the mock draws them, colour page C and idle page G per frame parity, changed rows copied (the first ones preloaded in the 30 blanks before 926).
* Result: 1,226 frames, 0 frames over budget with the tune (worst runs 4,181 cycles, worst update 4,612 cycles in the sim), NO stale lines; the stream is 245 KB (part 4c: 327 KB).  The sim equals the generator on all
  1,225 frames; VICE 6567: 13 of 13 part 4 shots exact (frames 7..1196, including the shifted stretch), the SID changes throughout.  Part 4 is 1,226 frames (part 4c: 1,116).
