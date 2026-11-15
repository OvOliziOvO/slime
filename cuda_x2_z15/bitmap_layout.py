"""Packed shared-memory layout for the fused X-phase search kernels."""
import re

def tiled_ring(program, phases, bands, rows, threads):
    """Interleave four successive rows by warp, without row padding."""
    stride=threads//2
    program = program.replace(".reg .b32 cold_shift,cold_word,hop;",
        ".reg .b32 cold_shift,cold_word,hop,word_local,word_base,word_delta,hot_offset,clip_offset,mnext,clip_next,next_cold;\n"
        ".reg .pred last_word,last_warp;")
    program = re.sub(r'(ring\[)(\d+)(\];)',
        lambda m: m[1]+str((1+bands if phases==2 else 1+(bands+1)//2)*rows*stride)+m[3], program, count=1)
    program = program.replace(" add.u32 cold_word,cold_word,mem;", "")
    marker = "and.b32 rowfrag, lane, 3; and.b32 bit, lane, 4; setp.ne.u32 shifted, bit, 0;\n"
    assert program.count(marker) == 1
    # Within a warp, the last word takes the next warp's first word.
    # The last warp's wrapped outputs are outside the valid tile.
    program = program.replace(marker, marker + f"""and.b32 word_local,lane,24; shr.u32 word_local,word_local,1;
mad.lo.u32 word_base,warp,64,word_local;
setp.eq.u32 last_word,word_local,12; selp.u32 word_delta,52,4,last_word;
setp.eq.u32 last_warp,warp,{threads//32-1};
@last_warp selp.u32 word_delta,-12,4,last_word;
add.u32 cold_word,mem,word_base;
mad.lo.u32 clip_offset,rowfrag,16,word_base;
sub.u32 hot_offset,3,rowfrag; mad.lo.u32 hot_offset,hot_offset,16,word_base;
""")
    # Each group of four rows uses one aligned 512-byte slab. The four
    # rows of a warp occupy different banks with no gaps between them.
    for row in range(4):
        prev = f"add.s32 slot, r, {row-3}; mad.lo.u32 memrow, slot, {stride}, mem;\nmad.lo.u32 xaddr, warp, 16, memrow;"
        new = (f"add.s32 slot, r, -3; mad.lo.u32 memrow, slot, {stride}, mem;\n"
               "mad.lo.u32 xaddr, warp, 64, memrow;")
        if row:
            new += f" add.u32 xaddr,xaddr,{16*row};"
        assert program.count(prev) == 1, row
        program = program.replace(prev, new)
    prev = f"sub.s32 slot, r, rowfrag; mad.lo.u32 memrow, slot, {stride}, mem;\nmad.lo.u32 mptr, wordfrag, 4, memrow;"
    new = (f"add.s32 slot, r, -3; mad.lo.u32 memrow, slot, {stride}, mem;\n"
           "add.u32 mptr,memrow,hot_offset; add.u32 mnext,mptr,word_delta;")
    assert program.count(prev) == 1
    program = program.replace(prev, new)
    program = re.sub(r'(ld\.shared\.u32 next,)\[mptr\+(\d+)\]',
        lambda m: m[1]+"[mnext"+(f"+{int(m[2])-4}" if int(m[2])>4 else "")+"]", program)

    # The two Tensor cold subtiles use the same four-row bank layout.
    program = program.replace(f"mad.lo.s32 addr,age,{stride},mem; mad.lo.u32 addr,wordfrag,4,addr;",
        f"and.b32 addr,age,0xfffffffc; mad.lo.u32 addr,addr,{stride},mem;\n"
        "add.u32 addr,addr,clip_offset; add.u32 clip_next,addr,word_delta;")
    program = re.sub(r'(ld\.shared\.u32 other,)\[addr(?:\+(\d+))\]',
        lambda m: m[1]+"[clip_next"+(f"+{int(m[2])-4}" if int(m[2])>4 else "")+"]", program)

    # The scalar cold subtiles have a fixed position within each quartet.
    pattern = re.compile(r'add\.s32 slot0,r,(-?\d+); setp\.lt\.s32 wrap,slot0,0;\n'
        rf'@wrap add\.s32 slot0,slot0,(\d+);\nmad\.lo\.s32 addr0,slot0,{stride},cold_word;\n'
        r'ld\.shared\.u32 a,\[addr0\+(\d+)\]; ld\.shared\.u32 an,\[addr0\+\d+\];\n'
        r'ld\.shared\.u32 b,\[addr0\]; ld\.shared\.u32 bn,\[addr0\+4\];')
    def fix_cold(m):
        age=-int(m[1])
        row=3-(age&3)
        po=int(m[3])
        return (f"add.s32 slot0,r,{-3-(age&~3)}; setp.lt.s32 wrap,slot0,0;\n"
            f"@wrap add.s32 slot0,slot0,{rows};\n"
            f"mad.lo.s32 addr0,slot0,{stride},cold_word;\n"
            f"add.u32 addr0,addr0,{16*row}; add.u32 next_cold,addr0,word_delta;\n"
            f"ld.shared.u32 a,[addr0+{po}]; ld.shared.u32 an,[next_cold+{po}];\n"
            "ld.shared.u32 b,[addr0]; ld.shared.u32 bn,[next_cold];")
    program=pattern.sub(fix_cold,program)
    assert "ld.shared.u32 an,[addr0" not in program
    return program


def paired_planes(program,bands,rows,threads):
    """Store two live bitmaps together so each Tensor load fetches both."""
    if bands<2:
        return program
    pitch=rows*threads//2
    pairs=(bands+1)//2
    regs=("pair_draw,pair_hot,pair_hot_next,pair_word,pair_word_next,"
          "pair_clip,pair_clip_next,pair_raw,pair_raw_next,pair_scalar,pair_scalar_next")
    marker=".reg .b32 cold_shift,cold_word,hop,"
    program=program.replace(marker,f".reg .b32 {regs};\n"+marker)
    marker="@leader st.shared.v4.u32 [xaddr],{b0,b1,b2,b3};"
    program=program.replace(marker,marker+"\n"
        "sub.u32 pair_draw,xaddr,mem; mad.lo.u32 pair_draw,pair_draw,2,mem;")
    marker="add.u32 mptr,memrow,hot_offset; add.u32 mnext,mptr,word_delta;"
    program=program.replace(marker,marker+"\n"
        "sub.u32 pair_hot,mptr,mem; mad.lo.u32 pair_hot,pair_hot,2,mem;\n"
        "mad.lo.u32 pair_hot_next,word_delta,2,pair_hot;")
    marker="add.u32 addr,addr,clip_offset; add.u32 clip_next,addr,word_delta;"
    program=program.replace(marker,marker+"\n"
        "sub.u32 pair_clip,addr,mem; mad.lo.u32 pair_clip,pair_clip,2,mem;\n"
        "mad.lo.u32 pair_clip_next,word_delta,2,pair_clip;")
    for k in range(bands//2):
        off_a=(1+k)*pitch
        off_b=(1+pairs+k)*pitch
        mapped=(1+2*k)*pitch
        first=f"@leader st.shared.v4.u32 [xaddr+{off_a}],{{b0,b1,b2,b3}};\n"
        second=f"@leader st.shared.v4.u32 [xaddr+{off_b}],{{c0,c1,c2,c3}};"
        merged=(f"@leader st.shared.v4.u32 [pair_draw+{mapped}],{{b0,c0,b1,c1}};\n"
                f"@leader st.shared.v4.u32 [pair_draw+{mapped+16}],{{b2,c2,b3,c3}};")
        assert program.count(first)==4 and program.count(second)==4
        program=program.replace(first,"").replace(second,merged)
        old=(f"ld.shared.u32 fragment,[mptr+{off_a}]; ld.shared.u32 next,[mnext+{off_a}];\n"
             "@shifted shf.r.wrap.b32 fragment,fragment,next,16;\n"
             "and.b32 a,fragment,parity;\nxor.b32 fa,fragment,a;\n"
             f"ld.shared.u32 fragment,[mptr+{off_b}]; ld.shared.u32 next,[mnext+{off_b}];\n"
             "@shifted shf.r.wrap.b32 fragment,fragment,next,16;\n"
             "and.b32 fb,fragment,parity; xor.b32 b,fragment,fb;")
        new=(f"ld.shared.v2.u32 {{fragment,pair_word}},[pair_hot+{mapped}];\n"
             f"ld.shared.v2.u32 {{next,pair_word_next}},[pair_hot_next+{mapped}];\n"
             "@shifted shf.r.wrap.b32 fragment,fragment,next,16;\n"
             "@shifted shf.r.wrap.b32 pair_word,pair_word,pair_word_next,16;\n"
             "and.b32 a,fragment,parity; xor.b32 fa,fragment,a;\n"
             "and.b32 fb,pair_word,parity; xor.b32 b,pair_word,fb;")
        assert program.count(old)==1
        program=program.replace(old,new)
        old_clip=(f"ld.shared.u32 raw,[addr+{off_a}]; ld.shared.u32 other,[clip_next+{off_a}];\n"
                  "@shifted shf.r.wrap.b32 raw,raw,other,16;\n"
                  "and.b32 c0,raw,par; xor.b32 c2,raw,c0;\n"
                  f"ld.shared.u32 raw,[addr+{off_b}]; ld.shared.u32 other,[clip_next+{off_b}];\n"
                  "@shifted shf.r.wrap.b32 raw,raw,other,16;\n"
                  "and.b32 c3,raw,par; xor.b32 c1,raw,c3;")
        new_clip=(f"ld.shared.v2.u32 {{raw,pair_raw}},[pair_clip+{mapped}];\n"
                  f"ld.shared.v2.u32 {{other,pair_raw_next}},[pair_clip_next+{mapped}];\n"
                  "@shifted shf.r.wrap.b32 raw,raw,other,16;\n"
                  "@shifted shf.r.wrap.b32 pair_raw,pair_raw,pair_raw_next,16;\n"
                  "and.b32 c0,raw,par; xor.b32 c2,raw,c0;\n"
                  "and.b32 c3,pair_raw,par; xor.b32 c1,pair_raw,c3;")
        assert program.count(old_clip) <= 2
        program=program.replace(old_clip,new_clip)

    if bands%2:
        last=(1+bands//2)*pitch
        last_v2=bands*pitch
        store=f"@leader st.shared.v4.u32 [xaddr+{last}],{{b0,b1,b2,b3}};"
        assert program.count(store)==4
        program=program.replace(store,store.replace(f"+{last}]",f"+{last_v2}]"))
        # Avoid changing a paired offset when the orphan's old index
        # coincides with another pair's new address.
        old=f"ld.shared.u32 fragment,[mptr+{last}]; ld.shared.u32 next,[mnext+{last}];"
        assert program.count(old)==1
        program=program.replace(old,old.replace(f"+{last}]",f"+{last_v2}]"))
    else:
        last=-1
        last_v2=-1

    def scalar(m):
        old=int(m[1])
        if old==last:
            return (f"ld.shared.u32 a,[addr0+{last_v2}]; "
                    f"ld.shared.u32 an,[next_cold+{last_v2}];")
        slot=old//pitch-1
        k=slot%pairs
        off=(1+2*k)*pitch+4*(slot>=pairs)
        return ("sub.u32 pair_scalar,addr0,mem; mad.lo.u32 pair_scalar,pair_scalar,2,mem;\n"
            "mad.lo.u32 pair_scalar_next,word_delta,2,pair_scalar;\n"
            f"ld.shared.u32 a,[pair_scalar+{off}]; ld.shared.u32 an,[pair_scalar_next+{off}];")
    return re.sub(r"ld\.shared\.u32 a,\[addr0\+(\d+)\]; ld\.shared\.u32 an,\[next_cold\+\1\];",
                  scalar,program)


def order_draw(program,bands,rows,threads):
    """Write each two-column vector as soon as both masks are ready."""
    pitch=rows*threads//2
    for pair in range(bands//2):
        z=2*pair
        a,b=[],[]
        for side,col_code in enumerate((a,b)):
            src="pa" if side==0 else "pb"
            dst="b" if side==0 else "c"
            for col in range(4):
                col_code.append(
                    f"add.s32 za_sel,{src}{col},z{z+side};\n"
                    "xor.b32 za_sel,za_sel,0x5e434;\n"
                    f"mad.lo.s32 res,za_sel,-969973431,bias{col}; setp.le.u32 hit,res,858993456;\n"
                    f"vote.sync.ballot.b32 {dst}{col},hit,0xffffffff;\n")
        offset=(1+2*pair)*pitch
        first=f"@leader st.shared.v4.u32 [pair_draw+{offset}],{{b0,c0,b1,c1}};\n"
        last=f"@leader st.shared.v4.u32 [pair_draw+{offset+16}],{{b2,c2,b3,c3}};\n"
        old="".join([*a,*b,first,last])
        chain=[*a[:2],*b[:2],first,*a[2:],*b[2:],last]
        assert program.count(old)==4,pair
        program=program.replace(old,"".join(chain))
    return program



VECTOR_THREADS = 128


def vectorize(program, phases, bands, rows):
    """Give a block a compact row ring and use one vector load per bitmap pair."""
    program=program.replace(".maxntid 256, 1, 1",f".maxntid {VECTOR_THREADS}, 1, 1")
    program=tiled_ring(program,phases,bands,rows,VECTOR_THREADS)
    if phases==2:
        program=paired_planes(program,bands,rows,VECTOR_THREADS)
        program=order_draw(program,bands,rows,VECTOR_THREADS)
    return program
