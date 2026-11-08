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
