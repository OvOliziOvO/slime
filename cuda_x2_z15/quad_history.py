"""Four exact rolling bounds sharing a carry-free packed gate."""


def code_for(program, bands, cut, rows, trim, stride, swap, reduce_cold=False):
    from .xp_scan import refine_bound

    marker=".reg .b32 cold_shift,cold_word,hop;"
    code="""
.reg .b32 quad_bias,quad_shift,quad_fresh,quad_low,quad_upper,quad_marks,quad_flags;
.reg .pred quad_pass,quad_warp;
"""
    program=program.replace(marker,marker+code)
    marker="ld.param.u32 minimum,[lo_arg];"
    program=program.replace(marker,marker+"sub.u32 quad_shift,128,minimum; mul.lo.u32 quad_bias,quad_shift,0x01010101;")
    covered=[]
    cold=[]

    def old_block(index,side):
        fresh=f"d{side}"
        return (
            f"and.b32 old,histhi{index},255; shr.u32 score,histhi{index},8;\n"
            f"sub.s32 delta,{fresh},old; add.s32 score,score,delta;\n"
            f"shr.u32 old,histlo{index},24; shl.b32 score,score,8;\n"
            f"or.b32 histhi{index},score,old;\n"
            f"prmt.b32 histlo{index},histlo{index},{fresh},0x2104;\n"
        )

    for i in range(0,bands-1,2):
        j=bands+i
        words=[f"histlo{i}",f"histhi{i}",f"histlo{i+1}",f"histhi{i+1}"]
        h0,h1,h2,h3=words
        prior=old_block(i,0)+old_block(i+1,1)
        prior+="mov.b32 d0,other0; mov.b32 d1,other1;\n"
        prior+=old_block(j,0)+old_block(j+1,1)
        assert program.count(prior)==1,i
        seed=f"mov.b32 total{i}, 0;"
        program=program.replace(seed,f"mov.b32 total{i}, quad_bias;")
        new=[
            "mad.lo.u32 score,d1,256,d0;",
            "mad.lo.u32 old,other1,256,other0;",
            "mad.lo.u32 quad_fresh,old,65536,score;",
            "and.b32 quad_low,quad_fresh,0x1f1f1f1f;",
            f"add.u32 quad_upper,total{i},quad_low;",
            f"and.b32 old,{h3},0x1f1f1f1f;",
            f"sub.u32 total{i},quad_upper,old;",
            f"lop3.b32 quad_marks,{h0},{h1},{h2},0xfe;",
            f"lop3.b32 quad_marks,quad_marks,{h3},quad_fresh,0xfe;",
            "and.b32 quad_flags,quad_upper,0x80808080;",
            "lop3.b32 quad_flags,quad_marks,0x60606060,quad_flags,0xea;",
            "setp.ne.and.u32 quad_pass,quad_flags,0,!invalid;",
        ]
        # For the Tensor correction, every lane participates.
        if reduce_cold and cut>=2:
            new += ["vote.sync.any.pred quad_warp,quad_pass,0xffffffff;",
                    f"@quad_warp bra.uni ColdQuad_{i};"]
        else:
            new.append(f"@quad_pass bra ColdQuad_{i};")
        new += [
            f"ResumeQuad_{i}:",
            f"mov.b32 {h3},{h2}; mov.b32 {h2},{h1};",
            f"mov.b32 {h1},{h0}; mov.b32 {h0},quad_fresh;",
        ]
        # Any five low-five-bit counts fit beside the threshold bias.
        # A high slice triggers an exact sum of all five original byte counts.
        slow=[f"ColdQuad_{i}:"]
        if reduce_cold and cut>=2:
            from .tensor_cold import instructions
            slow+=instructions(bands,i,rows,stride)
            slow += [
                "setp.eq.or.u32 quad_pass,quad_flags,0,invalid;",
                f"@quad_pass bra ResumeQuad_{i};",
            ]
        for field,band in enumerate((i,i+1,j,j+1)):
            b=refine_bound(band,bands,cut,rows,trim,stride,0,swap)
            assert "and.b32 bound,upper_pair,65535;" in b
            mask=0xff<<(field*8)
            select=0x0040+0x11*field
            restore=f"""{{
.reg .b32 flags,lo_bytes,hi_bytes,counts,slice;
and.b32 flags,quad_flags,{mask}; setp.eq.u32 skip,flags,0; @skip bra Skip_{band};
prmt.b32 lo_bytes,{h0},{h1},{select};
prmt.b32 hi_bytes,{h2},{h3},{select};
prmt.b32 counts,lo_bytes,hi_bytes,0x5410;
bfe.u32 slice,quad_fresh,{field*8},8;
dp4a.u32.u32 bound,counts,0x01010101,slice;
}}"""
            slow.append(b.replace("and.b32 bound,upper_pair,65535;",restore))
            covered.append(band)
        slow.append(f"bra ResumeQuad_{i};")
        cold+=slow
        program=program.replace(prior,"\n".join(new)+"\n")
    if bands % 2 == 1 and bands >= 3:
        i = bands - 1
        other = 2 * bands - 1
        prior = old_block(i, 0) + "mov.b32 d0,d1;\n" + old_block(other, 0)
        assert program.count(prior) == 1, i
        program = program.replace(
            "sub.u32 quad_shift,128,minimum; mul.lo.u32 quad_bias,quad_shift,0x01010101;",
            "sub.u32 quad_shift,128,minimum; mul.lo.u32 quad_bias,quad_shift,0x01010101;\n"
            "sub.u32 gate_bias,32768,minimum; mul.lo.u32 gate_bias,gate_bias,65537;"
        )
        program = program.replace(
            ".reg .b32 quad_bias,quad_shift,quad_fresh,quad_low,quad_upper,quad_marks,quad_flags;",
            ".reg .b32 quad_bias,quad_shift,quad_fresh,quad_low,quad_upper,quad_marks,quad_flags,gate_bias,gate_flags,upper_pair;\n"
            ".reg .pred skip_pair;"
        )
        seed = f"mov.b32 total{i}, 0;"
        assert program.count(seed) == 1, i
        program = program.replace(seed, f"mov.b32 total{i}, gate_bias;")
        new = (
            "mad.lo.u32 score,d1,65536,d0;\n"
            f"add.u32 upper_pair,total{i},score;\n"
            f"prmt.b32 old,histhi{i},zero,0x4342;\n"
            f"sub.u32 total{i},upper_pair,old;\n"
            f"prmt.b32 histhi{i},histlo{i},histhi{i},0x5432;\n"
            "mad.lo.u32 score,d1,256,d0;\n"
            f"mad.lo.u32 histlo{i},histlo{i},65536,score;\n"
            "and.b32 gate_flags,upper_pair,0x80008000;\n"
            f"setp.ne.and.u32 skip_pair,gate_flags,0,!invalid; @skip_pair bra ColdPair_{i};\n"
            f"ResumePair_{i}:\n"
        )
        refine = refine_bound(i, bands, cut, rows, trim, stride, 0, swap, merge_orphan=True)
        refine += refine_bound(other, bands, cut, rows, trim, stride, 1, swap, merge_orphan=True)
        cold.append(f"ColdPair_{i}:\nsub.u32 upper_pair,upper_pair,gate_bias;\n{refine}bra ResumePair_{i};\n")
        program = program.replace(prior, new)
        covered.extend((i, other))
    if cold:
        program=program[:program.index("mul.wide.u32 ptr64,ct,6144;")]+"ret;\n"+"\n".join(cold)+"\n}\n"
    return program,frozenset(covered)
