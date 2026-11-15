"""Precheck the four largest clipped rows for all lanes together."""


def instructions(bands, index, rows, stride):
    plane=(1+index//2)*rows*stride
    plane_b=plane+((bands+1)//2)*rows*stride
    return [
        "{",
        ".reg .b32 start,age,col,k,addr,par,raw,other,cut,mask0,mask1;",
        ".reg .b32 c0,c1,c2,c3,remove;",
        ".reg .pred top,wide_edges,wrap,heavy;",
        # y == 0, 1, 18, 19 of the original 20-row union.
        "setp.lt.u32 top,rowfrag,2; selp.u32 start,19,3,top; sub.s32 age,start,rowfrag;",
        "sub.s32 age,r,age; setp.lt.s32 wrap,age,0;",
        f"@wrap add.s32 age,age,{rows};",
        f"mad.lo.s32 addr,age,{stride},mem; mad.lo.u32 addr,wordfrag,4,addr;",
        "ld.shared.u32 par,[addr]; ld.shared.u32 other,[addr+4];",
        "@shifted shf.r.wrap.b32 par,par,other,16;",
        f"ld.shared.u32 raw,[addr+{plane}]; ld.shared.u32 other,[addr+{plane+4}];",
        "@shifted shf.r.wrap.b32 raw,raw,other,16;",
        "and.b32 c0,raw,par; xor.b32 c2,raw,c0;",
        f"ld.shared.u32 raw,[addr+{plane_b}]; ld.shared.u32 other,[addr+{plane_b+4}];",
        "@shifted shf.r.wrap.b32 raw,raw,other,16;",
        "and.b32 c3,raw,par; xor.b32 c1,raw,c3;",
        "setp.eq.u32 wide_edges,rowfrag,0; setp.eq.or.u32 wide_edges,rowfrag,3,wide_edges;",
        "selp.b32 cut,0xfc03f,0xf000f,wide_edges;",
        "shr.u32 col,lane,3; shl.b32 col,col,2; shl.b32 cut,cut,col;",
        "selp.b32 mask0,zero,cut,shifted; selp.b32 mask1,cut,zero,shifted;",
        "mma.sync.aligned.m16n8k256.row.col.s32.b1.b1.s32.and.popc "
        "{c0,c2,c1,c3},{c0,c1,c2,c3},{mask0,mask1},{zero,zero,zero,zero};",
        "mad.lo.u32 c0,c1,256,c0; mad.lo.u32 c2,c3,256,c2;",
        "mad.lo.u32 remove,c2,65536,c0;",
        # A large slice can have a clipped low-five-bit total. Those
        # lanes retain the ordinary exact scalar clipping path.
        "and.b32 k,quad_marks,0x60606060; setp.ne.u32 heavy,k,0;",
        "@!heavy sub.u32 cut,quad_upper,remove;",
        "@!heavy and.b32 quad_flags,cut,0x80808080;",
        "}",
    ]
