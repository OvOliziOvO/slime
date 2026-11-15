"""Compare one and two X phases of the six-band CUDA hot path."""
import argparse
import ctypes as c
from dataclasses import dataclass
from pathlib import Path
import statistics
import sys

import numpy as np
from .cuda_compile import cached_cubin

PERIOD = 1 << 17
MASK48 = (1 << 48) - 1
LCG = 0x5DEECE66D
SEED_XOR = LCG ^ 0x3AD8025F
TPB = 256
INPUT = 1024
OUTPUT = 1008
STRIDE = 144
RING = 24
PITCH = RING * STRIDE
WARP_MASK = 0xFFFFFFFF


@dataclass(frozen=True)
class Variant:
    name: str
    phases: int
    packed: bool = False
    complement_sum: bool = False
    resident: int = 3
    swap: bool = False
    rowloop: bool = False
    merge_orphan: bool = False


VARIANTS=(
    Variant("single",1),
    Variant("single-packed",1,packed=True),
    Variant("paired",2),
    Variant("paired-packed",2,packed=True),
    Variant("paired-sum",2,complement_sum=True),
    Variant("paired-sum2",2,complement_sum=True,resident=2),
)


def x_inputs(x):
    def signed32(v):
        return v.astype(np.uint32).view(np.int32).astype(np.int64)
    return ((signed32(x*x*0x4C1906)+signed32(x*0x5AC0DB)).astype(np.uint64)
            & np.uint64(MASK48))


def z_inputs(z,seed):
    def signed32(v):
        return v.astype(np.uint32).view(np.int32).astype(np.int64)
    z=(signed32(z*z)*0x4307A7+signed32(z*0x5F24F)).astype(np.uint64)
    return (z+np.uint64(seed&MASK48))&np.uint64(MASK48)


def make_inputs(x_tiles,z_tiles,groups,seed,x0,z0):
    x=x_inputs(np.arange(x0,x0+(x_tiles-1)*OUTPUT+INPUT+PERIOD,dtype=np.int64))
    z_grid=(np.arange(z0,z0+z_tiles*groups*4,dtype=np.int64)[None,:]
            + np.arange(6,dtype=np.int64)[:,None]*PERIOD)
    z=z_inputs(z_grid,seed)
    p=np.zeros((z.shape[1],8),dtype=np.uint32)
    p[:,:6]=(z>>16).T.astype(np.uint32)
    p[:,6]=(z[0]<<16).astype(np.uint32)
    return x,p,z


def packed_row_bytes(bands):
    return ((bands+4)//4)*16


def generator(v,snapshot,bands=6,ring_rows=24,packed_bands=6,stride=STRIDE):
    assert not snapshot or (bands==6 and ring_rows==24)
    pitch=ring_rows*stride
    row_bytes=packed_row_bytes(packed_bands)
    n=bands*v.phases
    pairs=(bands+1)//2
    planes=1+pairs*v.phases
    pt=[
        ".version 8.0",".target sm_86",".address_size 64",
        ".visible .entry compare_hot(",
        ".param .u64 x_arg, .param .u64 z_arg, .param .u32 xt_arg, .param .u32 groups_arg,",
        ".param .u64 scores_arg, .param .u64 sample_arg)",
        ".maxntid 256, 1, 1",
        f".minnctapersm {v.resident}",
        "{",
        f".shared .align 16 .b8 ring[{planes*pitch+(16 if stride==128 else 0)}];",
        ".reg .b64 X, Z, scores, sample, xa, za, ptr64, value64;",
        ".reg .b32 tid, lane, warp, ct, bid, phase, xt, zt, nbx, groups, lx, zword, r, iter;",
        ".reg .b32 mem, memrow, xaddr, src, slot, zero, mask, rowfrag, wordfrag, bit, mptr;",
        ".reg .b32 xlo<4>, xhi<8>;",
        f".reg .b32 histlo<{n}>, histhi<{n}>, total<{n}>;",
        ".reg .pred leader, continuation, pad, shifted;",
        "ld.param.u64 X, [x_arg]; ld.param.u64 Z, [z_arg]; ld.param.u64 scores, [scores_arg];",
        "ld.param.u64 sample, [sample_arg]; ld.param.u32 nbx, [xt_arg];",
        "ld.param.u32 groups, [groups_arg];",
        "mov.u32 tid, %tid.x; mov.u32 ct, %ctaid.x;",
        "and.b32 lane, tid, 31; shr.u32 warp, tid, 5;",
    ]
    if v.phases==1:
        pt += ["and.b32 phase, ct, 1; shr.u32 bid, ct, 1;"]
    else:
        pt += ["mov.u32 bid, ct; mov.u32 phase, 0; shl.b32 ct, ct, 1;"]
    pt += [
        "div.u32 zt, bid, nbx; mul.lo.u32 xt, zt, nbx; sub.u32 xt, bid, xt;",
        "shl.b32 lx, warp, 7; add.s32 lx, lx, lane;",
        "mad.lo.u32 lx, xt, 1008, lx;",
        "mad.lo.u32 lx, phase, 131072, lx;",
        "mul.wide.u32 xa, lx, 8; add.u64 xa, X, xa;",
        "mul.lo.u32 zword, zt, groups; shl.b32 zword, zword, 7;",
        "cvt.u64.u32 za, zword; add.u64 za, Z, za;",
        f"setp.eq.u32 leader, lane, 0; setp.lt.u32 pad, tid, {ring_rows};",
        f"mov.u32 mem, ring; mad.lo.u32 memrow, tid, {stride}, mem; mov.u32 zero, 0;",
    ]
    for i in range(planes if stride==144 else 0):
        pad=pitch*i+128
        pt += [f"@pad st.shared.v4.u32 [memrow+{pad}], {{zero, zero, zero, zero}};"]
    for k in range(4):
        pt += [
            f"ld.global.u64 value64, [xa+{k*256}];",
            f"cvt.u32.u64 xlo{k}, value64; shl.b32 xlo{k}, xlo{k}, 16;",
            f"shr.u64 ptr64, value64, 16; cvt.u32.u64 xhi{k}, ptr64;",
        ]
        if v.phases==2:
            pt += [f"ld.global.u64 value64, [xa+{PERIOD*8+k*256}];",
                   f"shr.u64 ptr64, value64, 16; cvt.u32.u64 xhi{k+4}, ptr64;"]
    for b in range(n):
        pt += [f"mov.b32 histlo{b}, 0; mov.b32 histhi{b}, 0; mov.b32 total{b}, 0;"]
    pt += [
        "shr.u32 wordfrag, lane, 3; shl.b32 rowfrag, warp, 2; add.u32 wordfrag, wordfrag, rowfrag;",
        "and.b32 rowfrag, lane, 3; and.b32 bit, lane, 4; setp.ne.u32 shifted, bit, 0;",
        "shr.u32 bit, lane, 3; shl.b32 bit, bit, 2; mov.u32 mask, 1048575; shl.b32 mask, mask, bit;",
        "mov.u32 r, 3; mov.u32 iter, 0; bar.sync 0;",
        "Main:",
        *(["bar.sync 0;"] if ring_rows==20 else []),
    ]
    if v.rowloop:
        pt += [
            "{ .reg .b32 row_ptr,row_iter; .reg .pred next_row;",
            "add.s32 row_ptr,r,-3;",
            f"mad.lo.s32 row_ptr,row_ptr,{stride},mem;",
            "mad.lo.u32 row_ptr,warp,16,row_ptr; mov.u32 row_iter,0;",
            "DrawRow:",
        ]
    for row in range(1 if v.rowloop else 4):
        pt += [
            "{",
            f".reg .b32 zlo, z<{max(8, ((packed_bands + 3) // 4) * 4)}>, zs<{max(4,pairs)}>, trash, lo, u, w, phase_a, phase_b, s, k, za_sel, a, b, res;",
            ".reg .b32 pa<4>, pb<4>, bias<4>, b<4>, c<4>;",
            ".reg .b64 product;",
            ".reg .pred ev<4>, hit;",
            f"ld.global.nc.v4.u32 {{z0,z1,z2,z3}},[za+{row_bytes*row}];",
        ]
        if packed_bands>=8:
            pt += [f"ld.global.nc.v4.u32 {{z4,z5,z6,z7}},[za+{row_bytes*row+16}];"]
            if packed_bands>8:
                pt += [f"ld.global.nc.v4.u32 {{z8,z9,z10,z11}},[za+{row_bytes*row+32}];"]
            if packed_bands==16:
                pt += [f"ld.global.nc.v4.u32 {{z12,z13,z14,z15}},[za+{row_bytes*row+48}];",
                       f"ld.global.nc.u32 zlo,[za+{row_bytes*row+64}];"]
            elif packed_bands==15:
                pt += [f"ld.global.nc.v4.u32 {{z12,z13,z14,zlo}},[za+{row_bytes*row+48}];"]
            elif packed_bands==14:
                pt += [f"ld.global.nc.v4.u32 {{z12,z13,zlo,trash}},[za+{row_bytes*row+48}];"]
            elif packed_bands==13:
                pt += [f"ld.global.nc.v4.u32 {{z12,zlo,trash,trash}},[za+{row_bytes*row+48}];"]
            else:
                pt += [f"ld.global.nc.u32 zlo,[za+{row_bytes*row+4*packed_bands}];"]
        else:
            pt += [f"ld.global.nc.v4.u32 {{z4,z5,zlo,trash}},[za+{row_bytes*row+16}];"]
        if v.complement_sum:
            for k in range(pairs):
                pt += [f"add.u32 zs{k}, z{2*k}, z{2*k+1};"]
        if v.rowloop:
            pt += ["mov.u32 xaddr,row_ptr;"]
        else:
            pt += [
                f"add.s32 slot, r, {row-3}; mad.lo.u32 memrow, slot, {stride}, mem;",
                "mad.lo.u32 xaddr, warp, 16, memrow;",
            ]
        for col in range(4):
            pt += [
                f"add.cc.u32 lo, xlo{col}, zlo;",
                f"addc.u32 phase_a, xhi{col}, 0;",
            ]
            if v.phases==2:
                pt += [f"addc.u32 phase_b, xhi{col+4}, 0;"]
            pt += [
                "xor.b32 u, lo, 0xe4320000;",
                "mul.wide.u32 product,u,0xdeece66d; add.u64 product,product,720896;",
                "shr.u64 product,product,32; cvt.u32.u64 w,product;",
                "add.s32 s,phase_a,z0; add.s32 s,s,w;",
                f"and.b32 k,s,2; setp.eq.u32 ev{col},k,0;",
                f"vote.sync.ballot.b32 b{col},ev{col},0xffffffff;",
                f"and.b32 k,s,1; sub.s32 bias{col},w,k; mad.lo.s32 bias{col},bias{col},0xcccccccd,u;",
            ]
            if v.swap:
                # A stride of 2**17 changes high-word bit 1 and leaves
                # the low word and bit 0 shared. Choose the X phase once.
                pt += [f"selp.b32 pa{col},phase_a,phase_b,ev{col};",
                       f"selp.b32 pb{col},phase_b,phase_a,ev{col};"]
            else:
                pt += [f"mov.b32 pa{col},phase_a;"]
                if v.phases==2:
                    pt += [f"mov.b32 pb{col},phase_b;"]
        pt += ["@leader st.shared.v4.u32 [xaddr],{b0,b1,b2,b3};"]
        for k in range(pairs):
            if v.swap and (2*k+1<bands or v.merge_orphan):
                # At an unpaired final Z band, only the parity-selected
                # X phase can match. Both phases share this one ballot.
                chosen=("a",) if 2*k+1==bands else ("a","b")
                for j,phase in enumerate(chosen):
                    pvar="pa" if phase=="a" else "pb"
                    dst="b" if j==0 else "c"
                    for col in range(4):
                        pt += [
                            f"add.s32 za_sel,{pvar}{col},z{2*k+j};",
                            "xor.b32 za_sel,za_sel,0x5e434;",
                            f"mad.lo.s32 res,za_sel,-969973431,bias{col}; setp.le.u32 hit,res,858993456;",
                            f"vote.sync.ballot.b32 {dst}{col},hit,0xffffffff;",
                        ]
                    pt += [f"@leader st.shared.v4.u32 [xaddr+{(1+k+j*pairs)*pitch}],{{{dst}0,{dst}1,{dst}2,{dst}3}};"]
                continue
            last_single=2*k+1==bands
            for col in range(4):
                pick=(f"mov.b32 za_sel,z{2*k};" if last_single else
                      f"selp.b32 za_sel,z{2*k},z{2*k+1},ev{col};")
                pt += [
                    pick,
                    f"add.s32 a,pa{col},za_sel; xor.b32 a,a,0x5e434;",
                    f"mad.lo.s32 res,a,-969973431,bias{col}; setp.le.u32 hit,res,858993456;",
                    f"vote.sync.ballot.b32 b{col},hit,0xffffffff;",
                ]
                if v.phases==2:
                    if last_single:
                        pt += [f"mov.b32 b,z{2*k};"]
                    elif v.complement_sum:
                        pt += [f"sub.s32 b,zs{k},za_sel;"]
                    else:
                        pt += [f"selp.b32 b,z{2*k+1},z{2*k},ev{col};"]
                    pt += [
                        f"add.s32 b,b,pb{col}; xor.b32 b,b,0x5e434;",
                        f"mad.lo.s32 res,b,-969973431,bias{col}; setp.le.u32 hit,res,858993456;",
                        f"vote.sync.ballot.b32 c{col},hit,0xffffffff;",
                    ]
            pt += [f"@leader st.shared.v4.u32 [xaddr+{(1+k)*pitch}],{{b0,b1,b2,b3}};"]
            if v.phases==2 and not (v.merge_orphan and last_single):
                pt += [f"@leader st.shared.v4.u32 [xaddr+{(1+pairs+k)*pitch}],{{c0,c1,c2,c3}};"]
        pt += ["}"]
    if v.rowloop:
        pt += [
            f"add.u64 za,za,{row_bytes}; add.u32 row_ptr,row_ptr,{stride};",
            "add.u32 row_iter,row_iter,1; setp.lt.u32 next_row,row_iter,4; @next_row bra.uni DrawRow;",
            "}",
        ]
    pt += [
        "bar.sync 0;",
        "{",
        ".reg .b32 parity, fragment, next, a, b, d0, d1, junk0, junk1, old, score, delta;",
        f"sub.s32 slot, r, rowfrag; mad.lo.u32 memrow, slot, {stride}, mem;",
        "mad.lo.u32 mptr, wordfrag, 4, memrow;",
        "ld.shared.u32 parity,[mptr]; ld.shared.u32 next,[mptr+4];",
        "@shifted shf.r.wrap.b32 parity,parity,next,16;",
    ]
    for phase_i in range(v.phases):
        for k in range(pairs):
            off=pitch*(1+phase_i*pairs+k)
            lhs,rhs=("a","b") if phase_i==0 else ("b","a")
            pt += [
                f"ld.shared.u32 fragment,[mptr+{off}]; ld.shared.u32 next,[mptr+{off+4}];",
                "@shifted shf.r.wrap.b32 fragment,fragment,next,16;",
                f"and.b32 {lhs},fragment,parity; xor.b32 {rhs},fragment,{lhs};",
            ]
            last_single=2*k+1==bands
            if last_single:
                pt += ["mma.sync.aligned.m8n8k128.row.col.s32.b1.b1.s32.and.popc "
                       "{d0,junk0},{a},{mask},{zero,zero};"]
            else:
                pt += ["mma.sync.aligned.m16n8k128.row.col.s32.b1.b1.s32.and.popc "
                       "{d0,junk0,d1,junk1},{a,b},{mask},{zero,zero,zero,zero};"]
            for side in range(1 if last_single else 2):
                b=bands*phase_i+2*k+side
                fresh=f"d{side}"
                if v.packed:
                    pt += [
                        f"and.b32 old,histhi{b},255; shr.u32 score,histhi{b},8;",
                        f"sub.s32 delta,{fresh},old; add.s32 score,score,delta;",
                        f"shr.u32 old,histlo{b},24; shl.b32 score,score,8;",
                        f"or.b32 histhi{b},score,old;",
                    ]
                else:
                    pt += [
                        f"sub.s32 delta,{fresh},histhi{b}; add.s32 total{b},total{b},delta;",
                        f"shr.u32 histhi{b},histlo{b},24;",
                    ]
                pt += [f"prmt.b32 histlo{b},histlo{b},{fresh},0x2104;"]
    pt += [
        "}",
        f"add.u32 iter,iter,1; add.u64 za,za,{4*row_bytes};" if not v.rowloop else "add.u32 iter,iter,1;",
        "add.u32 r,r,4; and.b32 r,r,31;" if ring_rows==32 else
        f"{{ .reg .pred rollover; setp.eq.u32 rollover,r,{ring_rows-1}; add.u32 r,r,4; @rollover mov.u32 r,3; }}",
        "setp.lt.u32 continuation,iter,groups; @continuation bra.uni Main;",
        "mul.wide.u32 ptr64,ct,6144; add.u64 scores,scores,ptr64;",
        "mul.wide.u32 ptr64,tid,4; add.u64 scores,scores,ptr64;",
    ]
    for b in range(n):
        if v.packed:
            pt += [f"shr.u32 total{b},histhi{b},8;"]
        pt += [f"st.global.u32 [scores+{1024*b}],total{b};"]
    if snapshot:
        pt += ["{", ".reg .b32 raw, parity, m, inv, idx, rr, ww;",
               ".reg .b64 so, vv;", 
               "mul.wide.u32 so,ct,18432; add.u64 sample,sample,so;"]
        for step in range(3):
            pt += [
                f"add.u32 idx,tid,{step*TPB}; shr.u32 rr,idx,5; and.b32 ww,idx,31;",
                "mad.lo.u32 mptr,rr,144,mem; mad.lo.u32 mptr,ww,4,mptr;",
                "ld.shared.u32 parity,[mptr]; not.b32 inv,parity;",
                "mul.wide.u32 vv,idx,4; add.u64 so,sample,vv;",
            ]
            for ph in range(v.phases):
                for k in range(pairs):
                    pt += [f"ld.shared.u32 raw,[mptr+{pitch*(1+ph*3+k)}];"]
                    for side in (0,1):
                        b=6*ph+2*k+side
                        pm="parity" if ph==side else "inv"
                        pt += [f"and.b32 m,raw,{pm}; st.global.u32 [so+{3072*b}],m;"]
        pt += ["}"]
    pt += ["ret;","}",""]
    return "\n".join(pt).encode()


class UnsupportedDevice(RuntimeError):
    """The selected CUDA device does not match the packaged kernels."""


class Driver:
    def __init__(self, required_capability=None):
        if sys.platform == "win32":
            self.lib = c.WinDLL("nvcuda.dll", winmode=0x800)
        else:
            self.lib = c.CDLL("libcuda.so.1")
        self.call("cuInit",c.c_uint(0))
        dev=c.c_int()
        self.call("cuDeviceGet",c.byref(dev),c.c_int(0))
        if required_capability is not None:
            major, minor = c.c_int(), c.c_int()
            self.call("cuDeviceGetAttribute", c.byref(major), c.c_int(75), dev)
            self.call("cuDeviceGetAttribute", c.byref(minor), c.c_int(76), dev)
            if (major.value, minor.value) != required_capability:
                raise UnsupportedDevice(f"CUDA device has SM {major.value}.{minor.value}")
        self.context=c.c_void_p()
        self.call("cuCtxCreate_v2",c.byref(self.context),c.c_uint(0),dev)
        self.modules=[]
        self.buffers=[]

    def call(self,name,*args):
        result=getattr(self.lib,name)(*args)
        if result:
            raise RuntimeError(f"{name} CUDA error {result}")

    def create(self,program):
        cubin=c.create_string_buffer(cached_cubin(program))
        mod=c.c_void_p()
        fn=c.c_void_p()
        self.call("cuModuleLoadData",c.byref(mod),c.cast(cubin,c.c_void_p))
        self.modules.append(mod)
        self.call("cuModuleGetFunction",c.byref(fn),mod,c.c_char_p(b"compare_hot"))
        props={}
        for label,idx in (("shared",1),("local",3),("regs",4)):
            value=c.c_int()
            self.call("cuFuncGetAttribute",c.byref(value),c.c_int(idx),fn)
            props[label]=value.value
        return fn,props

    def alloc(self,arr,upload=True):
        p=c.c_uint64()
        self.call("cuMemAlloc_v2",c.byref(p),c.c_size_t(arr.nbytes))
        self.buffers.append(p)
        if upload:
            self.call("cuMemcpyHtoD_v2",p,c.c_void_p(arr.ctypes.data),c.c_size_t(arr.nbytes))
        return p

    def download(self,p,shape):
        arr=np.empty(shape,dtype=np.uint32)
        self.call("cuMemcpyDtoH_v2",c.c_void_p(arr.ctypes.data),p,c.c_size_t(arr.nbytes))
        return arr

    def launch(self,fn,blocks,args,repeat):
        a,b=c.c_void_p(),c.c_void_p()
        for e in (a,b):
            self.call("cuEventCreate",c.byref(e),c.c_uint(0))
        params=(c.c_void_p*len(args))(*(c.cast(c.byref(x),c.c_void_p) for x in args))
        self.call("cuEventRecord",a,c.c_void_p())
        for _ in range(repeat):
            self.call("cuLaunchKernel",fn,c.c_uint(blocks),c.c_uint(1),c.c_uint(1),
                      c.c_uint(TPB),c.c_uint(1),c.c_uint(1),c.c_uint(0),c.c_void_p(),
                      params,c.c_void_p())
        self.call("cuEventRecord",b,c.c_void_p())
        self.call("cuEventSynchronize",b)
        ms=c.c_float()
        self.call("cuEventElapsedTime",c.byref(ms),a,b)
        for e in (a,b):
            self.call("cuEventDestroy_v2",e)
        return ms.value/(1000*repeat)

    def free(self):
        for p in self.buffers:
            self.call("cuMemFree_v2",p)
        self.buffers.clear()

    def close(self):
        self.free()
        for mod in self.modules:
            self.call("cuModuleUnload",mod)
        self.call("cuCtxDestroy_v2",self.context)


def independent(x,z,xt,zt,groups):
    assert groups%6==0 and groups>=6
    masks=np.empty((xt*zt*2,6,RING,32),dtype=np.uint32)
    scores=np.empty((xt*zt*2,6,TPB),dtype=np.uint32)
    rejection_count=0
    for tz in range(zt):
        for tx in range(xt):
            for phase in (0,1):
                tile=(tz*xt+tx)*2+phase
                left=tx*OUTPUT+phase*PERIOD
                recent=z[:,(tz+1)*groups*4-RING:(tz+1)*groups*4]
                state=((recent[:,:,None]+x[None,None,left:left+INPUT])^np.uint64(SEED_XOR))
                state=(state*np.uint64(LCG)+np.uint64(11))&np.uint64(MASK48)
                bits=state>>17
                rejection_count+=np.count_nonzero(bits>=2147483640)
                hit=bits%10==0
                masks[tile]=np.packbits(hit,axis=-1,bitorder="little").view("<u4")
                horiz=hit[:,-20:,:].sum(axis=1)
                cum=np.pad(horiz,((0,0),(1,16))).cumsum(axis=1)
                start=np.arange(TPB)*4
                scores[tile]=cum[:,start+20]-cum[:,start]
    return scores,masks,rejection_count


def execute(driver, variants, verify, xt,zt,groups,repeat,rounds):
    runs={}
    for v in variants:
        ptx=generator(v,verify)
        Path(f"xp-{v.name}{'-check' if verify else ''}.ptx").write_bytes(ptx)
        runs[v.name]=driver.create(ptx)
        r=runs[v.name][1]
        print(f"{v.name} regs={r['regs']} shared={r['shared']} local={r['local']}",flush=True)
    seeds=((123456789,-1875013,910011),(-4551278310048043,2147391234,-2147029941)) if verify else ((123456789,-1875013,910011),)
    for seed,x0,z0 in seeds:
        x,p,z=make_inputs(xt,zt,groups,seed,x0,z0)
        n=2*xt*zt
        da,db=driver.alloc(x),driver.alloc(p)
        sc_shape=(n,6,TPB)
        sa_shape=(n,6,RING,32)
        sc=driver.alloc(np.empty(sc_shape,np.uint32),False)
        raw=driver.alloc(np.empty(sa_shape if verify else (1,),np.uint32),False)
        args=(da,db,c.c_uint(xt),c.c_uint(groups),sc,raw)
        oracle=independent(x,z,xt,zt,groups) if verify else None
        collected={v.name:[] for v in variants}
        if not verify:
            for v in variants:
                driver.launch(runs[v.name][0],n//v.phases,args,1)
        for i in range(rounds):
            order=variants if i%2==0 else variants[::-1]
            for v in order:
                sec=driver.launch(runs[v.name][0],n//v.phases,args,repeat)
                if verify:
                    truth,want,reject=oracle
                    actual=driver.download(sc,sc_shape)
                    sample=driver.download(raw,sa_shape)
                    if not np.array_equal(sample,want):
                        where=np.argwhere(sample!=want)[0]
                        pos=tuple(where)
                        raise AssertionError((v.name,"mask",pos,hex(int(sample[pos])),hex(int(want[pos]))))
                    if not np.array_equal(actual,truth):
                        where=tuple(np.argwhere(actual!=truth)[0])
                        raise AssertionError((v.name,"score",where,int(actual[where]),int(truth[where])))
                    print(f"exact {v.name} {seed}: {sample.size*32} bitmap bits, {actual.size} counts, first rejections {reject}",flush=True)
                else:
                    collected[v.name].append(sec)
                    units=n*6*groups*4*INPUT/1e9
                    print(f"{i+1} {v.name} {sec:.6f}s {units/sec:.2f} B/s hot",flush=True)
        if not verify:
            base=statistics.median(collected["single"])
            units=n*6*groups*4*INPUT/1e9
            for v in variants:
                t=statistics.median(collected[v.name])
                print(f"median {v.name} {t:.6f}s {units/t:.2f} B/s hot {100*(base/t-1):+.2f}%",flush=True)
        driver.free()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verify",action="store_true")
    p.add_argument("--variants",nargs="*",default=[v.name for v in VARIANTS])
    p.add_argument("--x-tiles",type=int,default=256)
    p.add_argument("--z-tiles",type=int,default=4)
    p.add_argument("--groups",type=int,default=1024)
    p.add_argument("--repeat",type=int,default=4)
    p.add_argument("--rounds",type=int,default=4)
    a=p.parse_args()
    choices=tuple(v for v in VARIANTS if v.name in a.variants)
    assert choices and (a.verify or choices[0].name=="single")
    driver=Driver()
    try:
        if a.verify:
            execute(driver,choices,True,2,2,12,1,1)
        else:
            execute(driver,choices,False,a.x_tiles,a.z_tiles,a.groups,a.repeat,a.rounds)
    finally:
        driver.close()


if __name__=="__main__":
    main()

