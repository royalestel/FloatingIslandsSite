# autopilot check: runs the cartridge build of cosmicstrings (/tmp/gold_ntsc, mk_gold_ntsc.py) on py65 for N builds from a random start and prints the smallest gap at the rows passed
# python3 ap_sim.py [builds] [seed]
import sys, os, math, re
sys.path.insert(0,"/home/user/FloatingIslandsSite/c64-raybars")
from c64cpu import MPU
L={}
for ln in open("/tmp/gold_ntsc/cosmicstrings.lbl"):
    _,a,n=ln.split(); L[n.lstrip(".")]=int(a,16)
mpu=MPU(); mem=mpu.memory
for f in sorted(os.listdir("/tmp/gold_ntsc")):
    m=re.match(r"cosmicstrings_(C\w)\.bin",f)
    if not m: continue
cfg=open("/tmp/gold_ntsc/cosmicstrings.cfg").read()
for m in re.finditer(r"(\w+): start = \$([0-9A-F]+), size = \$([0-9A-F]+), file = \"([^\"]+)\"",cfg):
    a=int(m.group(2),16); d=open(m.group(4),"rb").read(); mem[a:a+len(d)]=list(d)
mem[0x1003]=0x60
TR=0x0400
def run_until(stop,limit=20_000_000):
    c=mpu.processorCycles
    while mpu.pc!=stop:
        mpu.step()
        if mpu.processorCycles-c>limit: raise RuntimeError("runaway %04x"%mpu.pc)
    return mpu.processorCycles-c
def call(addr):
    mpu.sp=0xF0
    for v in ((TR-1)>>8,(TR-1)&255): mem[0x100+mpu.sp]=v; mpu.sp=(mpu.sp-1)&255
    mpu.pc=addr
    return run_until(TR)
mpu.pc,mpu.sp=L["start"],0xFF; mem[0xDC00]=0xFF
run_until(L["main"],60_000_000)
HY=[mem[L["hy"]+i] for i in range(256)]
def wd(a): return ((a+128)%256)-128
steps=int(sys.argv[1]) if len(sys.argv)>1 else 450
import random
random.seed(int(sys.argv[2]) if len(sys.argv)>2 else 0)
mem[L["intro"]]=0
mem[L["kc"]]=random.randrange(256); mem[L["cyi"]]=random.randrange(256); mem[L["czi"]]=random.randrange(22)
cyc=[]; prev=None; worst=999; cl=[]
for b in range(steps):
    mem[L["fcount"]]=(mem[L["fcount"]]+4)&255
    c=call(L["build"]); cyc.append(c)
    kc=mem[L["kc"]]; cyi=mem[L["cyi"]]; cyf=mem[L["cyf"]]
    if prev is not None and kc!=prev[0]:
        # rows crossed since the last build: kc rows at height HY[kc]; ship height ~ cyi
        d=abs(wd(HY[kc]-cyi)); cl.append(d); worst=min(worst,d)
    prev=(kc,cyi)
    if False: print(b,"kc",kc,"cyi",cyi,"angh",mem[L["angh"]],"rate",mem[L["rate"]],"tgt",mem[L["aptgh"]],"cycles",c,flush=True)
print("rows passed",len(cl),"worst clearance",worst,"min5",sorted(cl)[:5],"max build cycles",max(cyc),"mean",sum(cyc)//len(cyc))
