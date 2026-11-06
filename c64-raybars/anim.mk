# make -f anim.mk          rebuild both programs after editing anim_params.py
# make -f anim.mk sim      ... and run the simulators (they check against the Python reference)
all: anim0.prg animsplit.prg

anim.inc anim_rec.bin anim_prof.bin: anim_params.py anim_scene.py anim_gen.py
	python3 anim_gen.py
wave.inc wave_off.bin wave_rec.bin wave_still.bin: anim_params.py anim_gen.py wave_gen.py anim_prof.bin
	python3 wave_gen.py
anim0.prg: anim0.s anim.cfg anim.inc anim_rec.bin anim_prof.bin
	cl65 -g -t none -C anim.cfg -Ln anim0.lbl -o $@ anim0.s
animsplit.prg: animsplit.s anim2.cfg wave.inc wave_off.bin wave_rec.bin wave_still.bin anim_prof.bin
	cl65 -g -t none -C anim2.cfg -Ln animsplit.lbl -o $@ animsplit.s
sim: all
	python3 sim_anim0.py
	python3 sim_animsplit.py
.PHONY: all sim
