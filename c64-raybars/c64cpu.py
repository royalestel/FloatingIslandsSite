"""py65's 6502 with the stable illegal (undocumented) opcodes the C64's
6510 runs reliably: LAX, SAX, DCP, ISC, SLO, RLA, SRE, RRA, SBX (AXS), ANC,
ALR (ASR), and the illegal NOPs.  Not the unstable ones (ANE/XAA, LXA,
SHA/AHX, SHX, SHY, TAS, LAS), which depend on the chip and temperature.

    from c64cpu import MPU
"""
from py65.devices.mpu6502 import MPU as _MPU

class MPU(_MPU):
    instruct = list(_MPU.instruct)
    cycletime = list(_MPU.cycletime)
    extracycles = list(_MPU.extracycles)
    disassemble = list(_MPU.disassemble)

def _op(code, name, mode, cycles, extra=0):
    def deco(f):
        MPU.instruct[code] = f
        MPU.cycletime[code] = cycles
        MPU.extracycles[code] = extra
        MPU.disassemble[code] = (name, mode)
        return f
    return deco

MODES = {  # mode -> (address function name, operand bytes)
    "zpg": ("ZeroPageAddr", 1), "zpx": ("ZeroPageXAddr", 1), "zpy": ("ZeroPageYAddr", 1),
    "abs": ("AbsoluteAddr", 2), "abx": ("AbsoluteXAddr", 2), "aby": ("AbsoluteYAddr", 2),
    "inx": ("IndirectXAddr", 1), "iny": ("IndirectYAddr", 1),
}

def _mk(code, name, mode, cycles, body, extra=0):
    fn, n = MODES[mode]
    def inst(self):
        body(self, getattr(self, fn))
        self.pc += n
    _op(code, name, mode, cycles, extra)(inst)

def _lax(self, addr):
    v = self.ByteAt(addr())
    self.a = self.x = v
    self.FlagsNZ(v)

def _sax(self, addr):
    self.memory[addr()] = self.a & self.x

def _rmw(f):
    def body(self, addr):
        a = addr()
        self.memory[a] = f(self, a, self.memory[a]) & 255
    return body

def _dcp(self, a, v):
    v = (v - 1) & 255
    self.p &= ~(self.CARRY | self.ZERO | self.NEGATIVE)
    if self.a == v:
        self.p |= self.CARRY | self.ZERO
    elif self.a > v:
        self.p |= self.CARRY
    self.p |= (self.a - v) & self.NEGATIVE
    return v

def _isc(self, a, v):
    v = (v + 1) & 255
    self.memory[a] = v
    self.opSBC(lambda: a)
    return v

def _slo(self, a, v):
    self.p = (self.p & ~self.CARRY) | (v >> 7)
    v = (v << 1) & 255
    self.a |= v
    self.FlagsNZ(self.a)
    return v

def _rla(self, a, v):
    c = self.p & self.CARRY
    self.p = (self.p & ~self.CARRY) | (v >> 7)
    v = ((v << 1) | c) & 255
    self.a &= v
    self.FlagsNZ(self.a)
    return v

def _sre(self, a, v):
    self.p = (self.p & ~self.CARRY) | (v & 1)
    v >>= 1
    self.a ^= v
    self.FlagsNZ(self.a)
    return v

def _rra(self, a, v):
    c = self.p & self.CARRY
    self.p = (self.p & ~self.CARRY) | (v & 1)
    v = (v >> 1) | (c << 7)
    self.memory[a] = v
    self.opADC(lambda: a)
    return v

for code, mode, cyc, ex in [(0xA7, "zpg", 3, 0), (0xB7, "zpy", 4, 0), (0xAF, "abs", 4, 0),
                            (0xBF, "aby", 4, 1), (0xA3, "inx", 6, 0), (0xB3, "iny", 5, 1)]:
    _mk(code, "LAX", mode, cyc, _lax, ex)
for code, mode, cyc in [(0x87, "zpg", 3), (0x97, "zpy", 4), (0x8F, "abs", 4), (0x83, "inx", 6)]:
    _mk(code, "SAX", mode, cyc, _sax)
RMW = [("zpg", 5, 0x07), ("zpx", 6, 0x17), ("abs", 6, 0x0F), ("abx", 7, 0x1F),
       ("aby", 7, 0x1B), ("inx", 8, 0x03), ("iny", 8, 0x13)]
for base, name, f in [(0x00, "SLO", _slo), (0x20, "RLA", _rla), (0x40, "SRE", _sre),
                      (0x60, "RRA", _rra), (0xC0, "DCP", _dcp), (0xE0, "ISC", _isc)]:
    for mode, cyc, off in RMW:
        _mk(base + off, name, mode, cyc, _rmw(f))

@_op(0xCB, "SBX", "imm", 2)
def _sbx(self):
    v = self.ByteAt(self.pc)
    t = (self.a & self.x) - v
    self.p &= ~(self.CARRY | self.ZERO | self.NEGATIVE)
    if t >= 0:
        self.p |= self.CARRY
    self.x = t & 255
    self.FlagsNZ(self.x)
    self.pc += 1

def _anc(self):
    self.a &= self.ByteAt(self.pc)
    self.FlagsNZ(self.a)
    self.p = (self.p & ~self.CARRY) | (self.a >> 7)
    self.pc += 1
_op(0x0B, "ANC", "imm", 2)(_anc)
_op(0x2B, "ANC", "imm", 2)(_anc)

@_op(0x4B, "ALR", "imm", 2)
def _alr(self):
    v = self.a & self.ByteAt(self.pc)
    self.p = (self.p & ~self.CARRY) | (v & 1)
    self.a = v >> 1
    self.FlagsNZ(self.a)
    self.pc += 1

def _nop(n, cyc, extra=0):
    def f(self):
        if n == 2 and extra:
            self.AbsoluteXAddr()
        self.pc += n
    return f
for c in (0x1A, 0x3A, 0x5A, 0x7A, 0xDA, 0xFA):
    _op(c, "NOP", "imp", 2)(_nop(0, 2))
for c in (0x80, 0x82, 0x89, 0xC2, 0xE2):
    _op(c, "NOP", "imm", 2)(_nop(1, 2))
for c in (0x04, 0x44, 0x64):
    _op(c, "NOP", "zpg", 3)(_nop(1, 3))
for c in (0x14, 0x34, 0x54, 0x74, 0xD4, 0xF4):
    _op(c, "NOP", "zpx", 4)(_nop(1, 4))
_op(0x0C, "NOP", "abs", 4)(_nop(2, 4))
for c in (0x1C, 0x3C, 0x5C, 0x7C, 0xDC, 0xFC):
    _op(c, "NOP", "abx", 4, 1)(_nop(2, 4, 1))
