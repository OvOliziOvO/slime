"""Experimental exact, pure CUDA search with adjacent X phases."""
import argparse
from collections import defaultdict
import ctypes as c
from pathlib import Path
import sys
from time import perf_counter

import numpy as np

from .x_phase import generator, Variant, PERIOD, INPUT, OUTPUT, STRIDE, packed_row_bytes
from .xp_support import ScanDriver, support_program, DX
from .bitmap_layout import VECTOR_THREADS, vectorize

TILE_Z=8192
CAPACITY=65536
SUPPORT_FUNCTIONS=("terms_x","terms_z","pack_z","refine_groups","rare_groups")
UINT=c.c_uint32
INT=c.c_int32
U64=c.c_uint64


def exclusions():
    for row in range(10):
        radius=max(DX[row-dz] for dz in range(4) if 0<=row-dz<17)
        width=8-radius
        if width:
            word=(1<<width)-1
            yield row, word|(word<<(20-width))


def refine_bound(index,bands,group_cut,rows,trim,stride,half=None,swap=False,merge_orphan=False):
    phase,band=divmod(index,bands)
    pair=(bands+1)//2
    zone=band%2 if swap and (2*(band//2)+1<bands or merge_orphan) else phase
    plane=(1+zone*pair+band//2)*rows*stride
    stop=f"Skip_{index}"
    p="and.b32 a,a,b;" if (phase+band)%2==0 else "lop3.b32 a,a,b,0,0x30;"
    if half is None:
        bound_init=f"shr.u32 bound,histhi{index},8;"
    else:
        bound_init="and.b32 bound,upper_pair,65535;" if half==0 else "shr.u32 bound,upper_pair,16;"
    code=[
        "{", ".reg .b32 bound,slot0,addr0,a,an,b,bn,off,k,zz,vz,gx,gz;",
        ".reg .b64 ticket,dest;",
        ".reg .pred skip,wrap;",
        bound_init,
        "setp.lt.or.u32 skip,bound,minimum,invalid;",
        f"@skip bra {stop};",
    ]
    if not trim:
        code += [
        f"add.u32 zz,z_local,{band*PERIOD}; add.u32 zz,zz,z_group;",
        "sub.s32 vz,slab,zz; min.s32 vz,vz,vz_tile;",
        "setp.le.s32 skip,vz,0;",f"@skip bra {stop};",
        ]
    for pair_id,(row,mask) in enumerate(exclusions()):
        if pair_id>=group_cut:
            break
        for age in (19-row,row):
            code += [
                f"add.s32 slot0,r,{-age}; setp.lt.s32 wrap,slot0,0;",
                f"@wrap add.s32 slot0,slot0,{rows};",
                f"mad.lo.s32 addr0,slot0,{stride},cold_word;",
                f"ld.shared.u32 a,[addr0+{plane}]; ld.shared.u32 an,[addr0+{plane+4}];",
                "ld.shared.u32 b,[addr0]; ld.shared.u32 bn,[addr0+4];",
                "shf.r.wrap.b32 a,a,an,cold_shift; shf.r.wrap.b32 b,b,bn,cold_shift;",
                p, f"and.b32 k,a,{mask}; popc.b32 k,k; sub.s32 bound,bound,k;",
            ]
        code += ["setp.lt.s32 skip,bound,minimum;", f"@skip bra {stop};"]
    code += [
        "atom.global.add.u64 ticket,[written],1;",
        "setp.ge.u64 skip,ticket,max_queue;",f"@skip bra {stop};",
        "shl.b64 dest,ticket,4; add.u64 dest,queue,dest;",
        f"add.s32 gx,gx_tile,{phase*PERIOD};",
    ]
    if trim:
        code += [
            "add.s32 gz,z_origin,z_local; add.s32 gz,gz,z_group;",
            f"add.s32 gz,gz,{band*PERIOD};",
            "st.global.v4.u32 [dest],{gx,gz,vx_tile,vz_tile};",
        ]
    else:
        code += ["add.s32 gz,z_origin,zz;", "st.global.v4.u32 [dest],{gx,gz,vx_tile,vz};"]
    code += [f"{stop}:", "}", ""]
    return "\n".join(code)


def fused_x_counts(program,bands,rows,stride,swap=False,merge_orphan=False):
    """Evaluate both X phases with one four-output binary Tensor operation."""
    shape="mma.sync.aligned.m16n8k256.row.col.s32.b1.b1.s32.and.popc"
    orphan="mma.sync.aligned.m8n8k128.row.col.s32.b1.b1.s32.and.popc"
    pairs=(bands+1)//2
    pitch=rows*stride
    head="@shifted shf.r.wrap.b32 parity,parity,next,16;\n"
    start=program.index(head)+len(head)
    end=program.index("}\nadd.u32 iter,iter,1;",start)
    old=program[start:end]
    assert old.count("mma.sync")==pairs*2
    code=[
        "{ .reg .b32 ma,mb,fa,fb,other0,other1;",
        "selp.b32 ma,zero,mask,shifted; selp.b32 mb,mask,zero,shifted;",
    ]

    def fragment(slot):
        off=slot*pitch
        return [
            f"ld.shared.u32 fragment,[mptr+{off}]; ld.shared.u32 next,[mptr+{off+4}];",
            "@shifted shf.r.wrap.b32 fragment,fragment,next,16;",
        ]

    def history(index,side):
        fresh=f"d{side}"
        return [
            f"and.b32 old,histhi{index},255; shr.u32 score,histhi{index},8;",
            f"sub.s32 delta,{fresh},old; add.s32 score,score,delta;",
            f"shr.u32 old,histlo{index},24; shl.b32 score,score,8;",
            f"or.b32 histhi{index},score,old;",
            f"prmt.b32 histlo{index},histlo{index},{fresh},0x2104;",
        ]

    for k in range(pairs):
        i=2*k
        other=bands+i
        code+=fragment(1+k)+["and.b32 a,fragment,parity;"]
        if i+1==bands and merge_orphan:
            two="mma.sync.aligned.m16n8k128.row.col.s32.b1.b1.s32.and.popc"
            code+=["xor.b32 b,fragment,a;",
                   f"{two} {{d0,junk0,d1,junk1}},{{a,b}},{{mask}},{{zero,zero,zero,zero}};"]
            code+=history(i,0)+["mov.b32 d0,d1;"]+history(other,0)
            continue
        if i+1==bands:
            code+=[f"{orphan} {{d0,junk0}},{{a}},{{mask}},{{zero,zero}};"]
            code+=history(i,0)+fragment(1+pairs+k)
            code+=["lop3.b32 a,fragment,parity,0,0x30;",
                   f"{orphan} {{d0,junk0}},{{a}},{{mask}},{{zero,zero}};"]
            code+=history(other,0)
            continue
        if swap:
            code+=["xor.b32 fa,fragment,a;"]+fragment(1+pairs+k)
            code+=["and.b32 fb,fragment,parity; xor.b32 b,fragment,fb;"]
        else:
            code+=["xor.b32 b,fragment,a;"]+fragment(1+pairs+k)
            code+=["and.b32 fb,fragment,parity; xor.b32 fa,fragment,fb;"]
        code+=[f"{shape} {{d0,other0,d1,other1}},{{a,b,fa,fb}},{{ma,mb}},{{zero,zero,zero,zero}};"]
        code+=history(i,0)+history(i+1,1)
        code+=["mov.b32 d0,other0; mov.b32 d1,other1;"]
        code+=history(other,0)+history(other+1,1)
    return program[:start]+"\n".join(code+["}",""])+program[end:]


def paired_history(program,phases,bands,cut,rows,trim,stride,swap=False,gate=False,split=False):
    """Update two independent rolling totals in the halves of one word."""
    names=[]
    cold=[]
    marker=".reg .b32 cold_shift,cold_word,hop;"
    assert program.count(marker)==1
    program=program.replace(marker,marker+"\n.reg .b32 upper_pair;")
    if gate:
        # A halfword has its top bit set precisely when the bound reaches
        # the threshold. The bias leaves room for the entire 20 by 20 tile.
        program=program.replace(marker,marker+"\n.reg .b32 gate_bias,gate_flags; .reg .pred skip_pair;")
        marker2="ld.param.u32 minimum,[lo_arg];"
        init="sub.u32 gate_bias,32768,minimum; mul.lo.u32 gate_bias,gate_bias,65537;"
        program=program.replace(marker2,marker2+init)

    def old_block(index,side):
        fresh=f"d{side}"
        return (
            f"and.b32 old,histhi{index},255; shr.u32 score,histhi{index},8;\n"
            f"sub.s32 delta,{fresh},old; add.s32 score,score,delta;\n"
            f"shr.u32 old,histlo{index},24; shl.b32 score,score,8;\n"
            f"or.b32 histhi{index},score,old;\n"
            f"prmt.b32 histlo{index},histlo{index},{fresh},0x2104;\n"
        )

    for phase in range(phases):
        for b in range(0,bands-1,2):
            i=phase*bands+b
            prior=old_block(i,0)+old_block(i+1,1)
            assert program.count(prior)==1,i
            # Each total is at most 400 and the retiring slice is
            # part of the prior sum. No carry crosses the halfwords.
            new=(
                "mad.lo.u32 score,d1,65536,d0;\n"
                f"add.u32 upper_pair,total{i},score;\n"
                f"prmt.b32 old,histhi{i},zero,0x4342;\n"
                f"sub.u32 total{i},upper_pair,old;\n"
                f"prmt.b32 histhi{i},histlo{i},histhi{i},0x5432;\n"
                "mad.lo.u32 score,d1,256,d0;\n"
                f"mad.lo.u32 histlo{i},histlo{i},65536,score;\n"
            )
            refine=refine_bound(i,bands,cut,rows,trim,stride,0,swap)
            refine+=refine_bound(i+1,bands,cut,rows,trim,stride,1,swap)
            if gate:
                seed=f"mov.b32 total{i}, 0;"
                assert program.count(seed)==1, i
                program=program.replace(seed,f"mov.b32 total{i}, gate_bias;")
                new+="and.b32 gate_flags,upper_pair,0x80008000;\n"
                decode="sub.u32 upper_pair,upper_pair,gate_bias;\n"
                resume=f"ResumePair_{i}"
                if split:
                    new+=f"setp.ne.and.u32 skip_pair,gate_flags,0,!invalid; @skip_pair bra ColdPair_{i};\n{resume}:\n"
                    cold.append(f"ColdPair_{i}:\n"+decode+refine+f"bra {resume};\n")
                else:
                    new+=f"setp.eq.or.u32 skip_pair,gate_flags,0,invalid; @skip_pair bra {resume};\n"
                    new+=decode+refine+f"{resume}:\n"
            else:
                new+=refine
            program=program.replace(prior,new)
            names.extend((i,i+1))
    if cold:
        program=program[:program.index("mul.wide.u32 ptr64,ct,6144;")]+"ret;\n"+"".join(cold)+"}\n"
    return program,frozenset(names)


def scan_program(phases,bands,group_cut,resident,trim=False,batch=False,z_bands=6,packed_counts=False,fuse=False,swap=False,rowloop=False,gate=False,split=False,quad=False,reduce_cold=False,merge_orphan=False,ring_rows=24,vector_bitmaps=False):
    swap=swap and phases==2 and fuse and not batch
    merge_orphan=merge_orphan and swap
    v=Variant(f"scan-{phases}-{bands}",phases,packed=True,resident=resident,swap=swap,rowloop=rowloop,merge_orphan=merge_orphan)
    rows=32 if batch else ring_rows
    stride=VECTOR_THREADS//2 if vector_bitmaps else STRIDE
    row_bytes=packed_row_bytes(z_bands)
    p=generator(v,False,bands=bands,ring_rows=rows,packed_bands=z_bands,stride=stride).decode()
    a=p.index(".visible .entry")
    b=p.index(".maxntid",a)
    p=p[:a]+""".visible .entry search_phase(
    .param .u64 x_arg,.param .u64 z_arg,.param .u32 xt_arg,
    .param .u64 starts_x,.param .u64 starts_z,
    .param .u64 q_arg,.param .u64 written_arg,.param .u32 cap_arg,
    .param .u32 xmin_arg,.param .u32 zmin_arg,.param .u32 slab_arg,.param .u32 lo_arg
)
"""+p[b:]
    a=p.index("ld.param.u64 X,")
    b=p.index("div.u32 zt,",a)
    p=p[:a]+""".reg .b64 XTiles,ZTiles,queue,written,max_queue;
.reg .b32 x_start,x_width,z_local,z_height,slab,minimum,cap;
.reg .b32 x_origin,z_origin,gx_tile,z_group,vx_tile,vz_tile;
.reg .b32 cold_shift,cold_word,hop;
.reg .pred invalid,tmp_invalid;
ld.param.u64 X,[x_arg]; ld.param.u64 Z,[z_arg];
ld.param.u64 XTiles,[starts_x]; ld.param.u64 ZTiles,[starts_z];
ld.param.u64 queue,[q_arg]; ld.param.u64 written,[written_arg];
ld.param.u32 cap,[cap_arg]; cvt.u64.u32 max_queue,cap;
ld.param.u32 slab,[slab_arg]; ld.param.u32 minimum,[lo_arg];
ld.param.u32 nbx,[xt_arg];
ld.param.u32 x_origin,[xmin_arg]; ld.param.u32 z_origin,[zmin_arg];
mov.u32 tid,%tid.x; mov.u32 ct,%ctaid.x; mov.u32 bid,ct;
and.b32 lane,tid,31; shr.u32 warp,tid,5;
"""+p[b:]
    a=p.index("shl.b32 lx, warp, 7;")
    b=p.index("setp.eq.u32 leader,",a)
    p=p[:a]+"""mul.wide.u32 ptr64,xt,8; add.u64 ptr64,XTiles,ptr64;
ld.global.v2.u32 {x_start,x_width},[ptr64];
mul.wide.u32 ptr64,zt,8; add.u64 ptr64,ZTiles,ptr64;
ld.global.v2.u32 {z_local,z_height},[ptr64];
add.u32 groups,z_height,3; shr.u32 groups,groups,2; add.u32 groups,groups,4;
shl.b32 lx,warp,7; add.u32 lx,lx,lane; add.u32 lx,lx,x_start;
mul.wide.u32 xa,lx,8; add.u64 xa,X,xa;
mul.wide.u32 za,z_local,ROW_BYTES; add.u64 za,Z,za;
shl.b32 hop,tid,2; add.s32 gx_tile,x_start,x_origin; add.s32 gx_tile,gx_tile,hop;
sub.s32 vx_tile,x_width,hop; min.s32 vx_tile,vx_tile,4;
and.b32 cold_shift,hop,31; shr.u32 cold_word,hop,5; shl.b32 cold_word,cold_word,2;
"""+p[b:]
    p=p.replace("ROW_BYTES",str(row_bytes))
    old="mov.u32 mem, ring;"
    assert p.count(old)==1
    p=p.replace(old,old+" add.u32 cold_word,cold_word,mem;")
    a=p.index("Main:")+len("Main:\n")
    b=p.index("bar.sync 0;",a)+len("bar.sync 0;\n")
    if batch:
        draw=p[a:b-len("bar.sync 0;\n")]
        prepare=(
            "{ .reg .pred last; .reg .u32 next; add.u32 next,iter,1;\n"
            "setp.ge.u32 last,next,groups; @last bra.uni Barrier; }\n"
            f"add.u32 iter,iter,1; add.u64 za,za,{4*row_bytes}; add.u32 r,r,4; and.b32 r,r,31;\n"
        )
        rewind=(
            f"add.u32 iter,iter,-1; add.u64 za,za,{-4*row_bytes}; add.u32 r,r,-4; and.b32 r,r,31;\n"
            "Barrier:\nbar.sync 0;\nCount:\n"
        )
        p=p[:a]+draw+prepare+draw+rewind+p[b:]
        b=a+len(draw+prepare+draw+rewind)
        loop="setp.lt.u32 continuation,iter,groups; @continuation bra.uni Main;"
        assert p.count(loop)==1
        p=p.replace(loop,
            "setp.ge.u32 continuation,iter,groups; @continuation bra.uni Done;\n"
            "{ .reg .pred next; .reg .u32 parity; and.b32 parity,iter,1;\n"
            "setp.ne.u32 next,parity,0; @next bra.uni Count; }\n"
            "bra.uni Main;\nDone:")

    p=p[:b]+"""shl.b32 z_group,iter,2; add.s32 z_group,z_group,-16;
sub.s32 vz_tile,z_height,z_group; min.s32 vz_tile,vz_tile,4;
setp.le.s32 invalid,vx_tile,0;
setp.lt.or.s32 invalid,z_group,0,invalid;
"""+p[b:]
    if fuse and phases==2 and rows!=32:
        p=fused_x_counts(p,bands,rows,stride,swap,merge_orphan)
        if split:
            p=p.replace("{\n.reg .b32 parity, fragment", ".reg .b32 parity, fragment")
            p=p.replace("{ .reg .b32 ma,mb,fa,fb,other0,other1;", ".reg .b32 ma,mb,fa,fb,other0,other1;")
            p=p.replace("}\n}\nadd.u32 iter,iter,1;", "add.u32 iter,iter,1;")
    else:
        split=False
    paired_states=frozenset()
    if quad and swap and gate and split:
        from .quad_history import code_for
        p,paired_states=code_for(p,bands,group_cut,rows,trim,stride,swap,reduce_cold)
    elif packed_counts:
        p,paired_states=paired_history(p,phases,bands,group_cut,rows,trim,stride,swap,gate,split)
    for b in range(bands*phases):
        if b in paired_states:
            continue
        end=f"prmt.b32 histlo{b},histlo{b},d{b%bands%2},0x2104;\n"
        # The odd-width band's last single uses d0, and the next phase
        # starts again at even local band zero.
        assert p.count(end)==1,(b,end)
        p=p.replace(end,end+refine_bound(b,bands,group_cut,rows,trim,stride,swap=swap,merge_orphan=merge_orphan))
    if "mul.wide.u32 ptr64,ct,6144;" in p:
        p=p[:p.index("mul.wide.u32 ptr64,ct,6144;")]+"ret;\n}\n"
    return vectorize(p,phases,bands,rows) if vector_bitmaps else p


def x_layout(width,pair,output=OUTPUT):
    both,one=[],[]
    if pair:
        groups=width//(2*PERIOD)
        for i in range(groups):
            start=2*PERIOD*i
            for off in range(0,PERIOD,output):
                both.append((start+off,min(output,PERIOD-off)))
        tail=2*PERIOD*groups
    else:
        tail=0
    for left in range(tail,width,output):
        one.append((left,min(output,width-left)))
    assert 2*sum(h for _,h in both)+sum(h for _,h in one)==width
    return np.asarray(both,np.uint32),np.asarray(one,np.uint32)


def z_layout(height):
    rows=defaultdict(list)
    full,rem=divmod(height,PERIOD)
    for low,high,bands in ((0,rem,full+1),(rem,PERIOD,full)):
        if bands==0:
            continue
        for first in range(low,high,TILE_Z):
            rows[bands].append((first,min(TILE_Z,high-first)))
    assert sum(h*b for b,r in rows.items() for _,h in r)==height
    return {b:np.asarray(r,np.uint32) for b,r in rows.items()}


def ceil(a,b):
    return (a+b-1)//b


def rare_inputs():
    # Reuse the incumbent's exhaustive list of Java rejected states
    # whose accepted continuation yields a hit.
    from .generate_slime_rare_tables import rejection_targets,inverse_table
    from bisect import bisect_left
    values=rejection_targets()
    offsets=np.array([bisect_left(values,i*(1<<32)) for i in range(-1,65538)],np.uint32)
    targets=np.array([v&((1<<48)-1) for v in values],np.uint64)
    return targets,offsets,np.array(inverse_table(),np.uint32)


class ExactScan:
    def __init__(self,cut,resident,trim=False,batch=False,z_bands=15,packed_counts=True,fuse=True,ring_rows=None,first_slab=None,rowloop=False,*,driver=None,verbose=True):
        self.d = driver if driver is not None else ScanDriver()
        self.verbose = verbose
        self.k=self.d.module(support_program(z_bands),SUPPORT_FUNCTIONS)
        self.z_bands=z_bands
        self.first_slab=first_slab
        self.rowloop=rowloop
        self.packed_counts=packed_counts
        self.fuse=fuse
        self.fast_path=packed_counts and fuse and not batch
        if ring_rows is None:
            ring_rows=24 if self.fast_path and not rowloop else 20
        self.ring_rows=ring_rows
        self.vector_bitmaps=self.fast_path and ring_rows==24 and not rowloop
        self.threads=VECTOR_THREADS if self.vector_bitmaps else 256
        self.output_width=4*self.threads-16
        self.rare=tuple(self.d.alloc(a) for a in rare_inputs())
        self.hot={}
        self.cut=cut
        self.resident=resident
        self.trim=trim
        self.batch=batch

    def slab_ranges(self,width):
        first_bands=self.first_slab
        if first_bands is None and self.vector_bitmaps and self.z_bands==15:
            if 28*PERIOD<=width<=29*PERIOD:
                # Two fourteen-band slabs avoid two orphan bands in
                # the full part while leaving room for the partial band.
                first_bands=14
        if first_bands is not None and width>first_bands*PERIOD:
            first_h=first_bands*PERIOD
            yield 0,first_h
            offset=first_h
        else:
            offset=0
        step=self.z_bands*PERIOD
        while offset<width:
            h=min(step,width-offset)
            yield offset,h
            offset+=h

    def prepare(self,width,pair,*,checkpoint=None):
        for _,h in self.slab_ranges(width):
            for b in z_layout(h):
                for p,tiles in zip((2,1),x_layout(width,pair,self.output_width)):
                    if len(tiles)==0 or (p,b) in self.hot:
                        continue
                    if checkpoint is not None:
                        checkpoint()
                    resident=self.resident if p==2 else (2 if b>8 else 3)
                    if self.packed_counts and b<=8:
                        resident=3
                    rows=self.ring_rows
                    if self.vector_bitmaps:
                        resident=4
                        if p==2 and b>15:
                            rows=20
                    prog=scan_program(
                        p,b,self.cut,resident,self.trim,self.batch,self.z_bands,self.packed_counts,self.fuse,
                        swap=self.fast_path,rowloop=self.rowloop,gate=self.fast_path,split=self.fast_path,
                        quad=self.fast_path,reduce_cold=self.fast_path,merge_orphan=self.fast_path,
                        ring_rows=rows,vector_bitmaps=self.vector_bitmaps
                    )
                    kernel=self.d.module(prog,("search_phase",))["search_phase"]
                    self.hot[p,b]=kernel
                    if self.verbose:
                        metrics=[]
                        for attr in (4,1,3):
                            item=INT()
                            self.d.call("cuFuncGetAttribute",c.byref(item),INT(attr),kernel)
                            metrics.append(item.value)
                        occupancy=INT()
                        self.d.call("cuOccupancyMaxActiveBlocksPerMultiprocessor",c.byref(occupancy),kernel,INT(self.threads),c.c_size_t(0))
                        print(f"compiled X{p} Z{b} regs={metrics[0]} shared={metrics[1]} local={metrics[2]} blocks/SM={occupancy.value}",flush=True)

    def scan(self,seed,radius,threshold,center_x,center_z,pair,initial_cap=None,*,checkpoint=None,progress=None):
        d=self.d
        fresh=len(d.buffers)
        t0=perf_counter()
        n=2*radius+1
        xlow,xhigh=center_x-radius,center_x+radius
        zlow,zhigh=center_z-radius,center_z+radius
        assert max(abs(xlow),abs(xhigh),abs(zlow),abs(zhigh))<=100_000_000
        xsize=n+INPUT+32
        zsize=ceil(n,PERIOD)*PERIOD+32
        cap=initial_cap if initial_cap is not None else (1<<23 if threshold>=59 else 1<<25)
        stages=[]
        completed_centers = 0
        bounded_batches = checkpoint is not None or progress is not None
        try:
            x=d.empty(xsize*8); z=d.empty(zsize*8)
            packed=d.empty((PERIOD+20)*packed_row_bytes(self.z_bands))
            q=d.empty(cap*16)
            qcount=d.empty(8)
            out=d.empty(CAPACITY*16)
            out_count=d.empty(8)
            d.start(self.k["terms_x"],ceil(xsize,256),256,x,INT(xlow-8),UINT(xsize))
            d.start(self.k["terms_z"],ceil(zsize,256),256,z,INT(zlow-8),UINT(zsize),U64(seed))
            d.zero(out_count)
            xsets = [(p, tiles, d.alloc(tiles)) for p, tiles in
                     zip((2, 1), x_layout(n, pair, self.output_width)) if len(tiles)]
            for offset,h in self.slab_ranges(n):
                bands=ceil(h,PERIOD)
                d.start(self.k["pack_z"],ceil(PERIOD+20,256),256,z,packed,UINT(offset),UINT(PERIOD+20),UINT(bands))
                zsets = [(b, len(tiles), b * int(tiles[:, 1].sum()), d.alloc(tiles))
                         for b, tiles in z_layout(h).items()]
                tk=perf_counter()
                reported_centers = 0
                while True:
                    d.zero(qcount)
                    attempt_centers = 0
                    for p, tiles, xt in xsets:
                        nx = len(tiles)
                        for b, nz, height, zt in zsets:
                            # Short launches allow UI pause/cancel checkpoints and keep
                            # display-driver jobs bounded on Windows.
                            batch_width = max(1, 4096 // nz) if bounded_batches else nx
                            for first in range(0, nx, batch_width):
                                count_x = min(batch_width, nx - first)
                                tile_x = U64(xt.value + first * 8)
                                if checkpoint is not None:
                                    checkpoint()
                                d.start(self.hot[p,b],count_x*nz,self.threads,x,packed,UINT(count_x),
                                        tile_x,zt,q,qcount,UINT(cap),INT(xlow),INT(zlow+offset),
                                        UINT(h),UINT(threshold))
                                if bounded_batches:
                                    d.call("cuCtxSynchronize")
                                if progress is not None:
                                    width = p * int(tiles[first:first + count_x, 1].sum())
                                    attempt_centers += width * height
                                    # A queue retry covers the same centers again.
                                    # Its time counts, and its centers count once.
                                    reported_centers = max(reported_centers, attempt_centers)
                                    progress(completed_centers + reported_centers, False)
                    count=d.u64(qcount)
                    if count<=cap:
                        break
                    d.release(q)
                    cap=ceil(count,1<<20)*(1<<20)
                    q=d.empty(cap*16)
                for _, _, _, zt in zsets:
                    d.release(zt)
                if checkpoint is not None:
                    checkpoint()
                completed_centers += n * h
                td=perf_counter()
                self.refine(x,z,q,count,out,out_count,xlow,zlow,threshold)
                stages.append((count,td-tk,perf_counter()-td))
            final_start=perf_counter()
            while True:
                if checkpoint is not None:
                    checkpoint()
                d.zero(qcount)
                d.start(self.k["rare_groups"],ceil(n+16,256),256,z,*self.rare,q,qcount,UINT(cap),
                        INT(xlow),INT(xhigh),INT(zlow),INT(zhigh))
                rare=d.u64(qcount)
                if rare<=cap:
                    break
                d.release(q)
                cap=ceil(rare,1<<20)*(1<<20)
                q=d.empty(cap*16)
            self.refine(x,z,q,rare,out,out_count,xlow,zlow,threshold)
            hits=d.u64(out_count)
            if hits>CAPACITY:
                raise RuntimeError(f"Exact matches exceeded output capacity ({hits})")
            if checkpoint is not None:
                checkpoint()
            a=d.download(out,(hits,4)).view(np.int32)
            result=sorted({tuple(map(int,line[:3])) for line in a})
            elapsed=perf_counter()-t0
            if progress is not None:
                progress(completed_centers, True)
            if self.verbose:
                print("stages",[(n,round(s,5),round(t,5)) for n,s,t in stages],
                      "rare candidate groups",rare,"rare+read",round(perf_counter()-final_start,5),flush=True)
            return result,elapsed
        finally:
            for ptr in d.buffers[fresh:].copy():
                d.release(ptr)

    def refine(self,x,z,q,count,out,out_count,xmin,zmin,threshold):
        self.d.start(self.k["refine_groups"],ceil(count,4),128,x,z,q,U64(count),out,out_count,
                     UINT(CAPACITY),INT(xmin),INT(zmin),UINT(threshold))
        self.d.call("cuCtxSynchronize")


class RefRow(c.Structure):
    _fields_=[(n,INT) for n in ("size","center_x","center_z","obs_count","afk_x","afk_z")]


def reference(path,seed,radius,lo,x,z):
    lib=c.CDLL(str(path.resolve()))
    fn=lib.search_slime_clusters_gpu_v1_centered
    fn.argtypes=[c.c_int64,c.c_int64,INT,INT,c.c_int64,INT,INT,c.POINTER(RefRow),INT,INT]
    fn.restype=c.c_int64
    rows=(RefRow*CAPACITY)()
    lib.reset_cancel()
    start=perf_counter()
    count=fn(seed,radius,lo,999,0,x,z,rows,len(rows),1)
    elapsed=perf_counter()-start
    assert 0<=count<=len(rows),count
    lib.get_processed_centers.restype=c.c_int64
    assert lib.get_processed_centers()==(2*radius+1)**2
    result=sorted((v.size,(v.center_x-8)//16,(v.center_z-8)//16) for v in rows[:count])
    return result,elapsed


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--radius",type=int,default=393216)
    parser.add_argument("--x",type=int,default=912696)
    parser.add_argument("--z",type=int,default=-592827)
    parser.add_argument("--seed",type=int,default=123456789)
    parser.add_argument("--lo",type=int,choices=range(55,61),default=60)
    parser.add_argument("--cuts",type=int,choices=range(1,7),default=6)
    parser.add_argument("--resident",type=int,choices=(2,3))
    parser.add_argument("--ref",type=Path)
    parser.add_argument("--single",action="store_true")
    parser.add_argument("--trim",action="store_true")
    parser.add_argument("--batch",action="store_true")
    parser.add_argument("--z-bands",type=int,choices=(6,8,10,12,13,14,15,16),default=15)
    parser.add_argument("--ring-rows",type=int,choices=(20,24))
    parser.add_argument("--first-slab",type=int,default=None)
    parser.add_argument("--rowloop",action="store_true")
    parser.add_argument("--repeat",type=int,default=1)
    args=parser.parse_args()
    cfg=(args.seed,args.radius,args.lo,args.x,args.z)
    count=(2*args.radius+1)**2
    before=None
    if args.ref:
        reference(args.ref,args.seed,196608,60,args.x,args.z)
        before=reference(args.ref,*cfg)
        print(f"reference {before[1]:.5f}s {count/before[1]/1e9:.2f} B/s {len(before[0])} hits",flush=True)
    wide=args.z_bands>=8
    resident=args.resident if args.resident is not None else (2 if args.z_bands>8 else 3)
    rows=args.ring_rows
    if rows is None and args.resident is not None:
        rows=20
    experiment=ExactScan(args.cuts,resident,args.trim,args.batch,args.z_bands,wide,wide,
                         ring_rows=rows,first_slab=args.first_slab,rowloop=args.rowloop)
    try:
        experiment.prepare(2*args.radius+1,not args.single)
        for _ in range(args.repeat):
            hits,sec=experiment.scan(*cfg,not args.single)
            print(f"search {sec:.5f}s {count/sec/1e9:.2f} B/s {len(hits)} hits",flush=True)
            if before:
                expected=set(before[0])
                diff=set(hits)
                assert expected==diff,("missing",sorted(expected-diff)[:16],"extra",sorted(diff-expected)[:16])
                print("EXACT same results",flush=True)
    finally:
        experiment.d.close()


if __name__=="__main__":
    main()

