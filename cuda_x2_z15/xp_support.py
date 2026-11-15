"""CUDA support for the exact horizontal-pair search prototype."""
import ctypes as c
import numpy as np

from .cuda_compile import module_image
from .x_phase import Driver, packed_row_bytes

HEADER=".version 8.0\n.target sm_86\n.address_size 64\n"
DX=(2,4,5,6,7,7,8,8,8,8,8,7,7,6,5,4,2)
CIRCLE=[((1<<(2*d+1))-1)<<(8-d) for d in DX]

TERMS = """
.func (.param .b64 value) coordinate_x(.param .b32 input)
{
.reg .b32 x,a,b;
.reg .b64 pa,pb,sum;
ld.param.u32 x,[input];
mul.lo.u32 a,x,x;
mul.lo.u32 a,a,0x4c1906;
mul.lo.u32 b,x,0x5ac0db;
cvt.s64.s32 pa,a; cvt.s64.s32 pb,b;
add.u64 sum,pa,pb; and.b64 sum,sum,0xffffffffffff;
st.param.b64 [value],sum;
ret;
}
.visible .entry terms_x(.param .u64 o,.param .u32 org,.param .u32 n)
{
.reg .b32 idx,g,t,left,lim,x;
.reg .b64 out,off,val;
.reg .pred exit;
ld.param.u64 out,[o]; ld.param.u32 left,[org]; ld.param.u32 lim,[n];
mov.u32 g,%ctaid.x; mov.u32 t,%tid.x; mad.lo.u32 idx,g,256,t;
setp.ge.u32 exit,idx,lim; @exit ret;
add.u32 x,left,idx;
call.uni (val),coordinate_x,(x);
mul.wide.u32 off,idx,8; add.u64 out,out,off; st.global.u64 [out],val;
ret;
}
.visible .entry terms_z(.param .u64 o,.param .u32 org,.param .u32 n,.param .u64 seed_arg)
{
.reg .b32 idx,g,t,left,lim,x,a,b;
.reg .b64 out,off,val,w,temp,seed;
.reg .pred exit;
ld.param.u64 out,[o]; ld.param.u32 left,[org]; ld.param.u32 lim,[n];
ld.param.u64 seed,[seed_arg];
mov.u32 g,%ctaid.x; mov.u32 t,%tid.x; mad.lo.u32 idx,g,256,t;
setp.ge.u32 exit,idx,lim; @exit ret;
add.u32 x,left,idx;
mul.lo.u32 a,x,x; mul.lo.u32 b,x,0x5f24f;
mul.wide.s32 w,a,0x4307a7; cvt.s64.s32 temp,b;
add.u64 val,w,temp; add.u64 val,val,seed; and.b64 val,val,0xffffffffffff;
mul.wide.u32 off,idx,8; add.u64 out,out,off; st.global.u64 [out],val;
ret;
}
"""

def make_pack(bands=6):
    row_bytes=packed_row_bytes(bands)
    out=[
        ".visible .entry pack_z(.param .u64 z,.param .u64 p,.param .u32 start,.param .u32 n,.param .u32 bands)",
        "{",".reg .b64 in,out,off,val,high;",f".reg .b32 idx,g,t,base,limit,b,raw,h<{max(8, ((bands + 3) // 4) * 4)}>,lo,zero;",
        ".reg .pred exit,use;",
        "ld.param.u64 in,[z]; ld.param.u64 out,[p]; ld.param.u32 base,[start];",
        "ld.param.u32 limit,[n]; ld.param.u32 b,[bands];",
        "mov.u32 g,%ctaid.x; mov.u32 t,%tid.x; mad.lo.u32 idx,g,256,t;",
        "setp.ge.u32 exit,idx,limit; @exit ret;",
        f"mul.wide.u32 off,idx,{row_bytes}; add.u64 out,out,off;",
        "add.u32 idx,idx,base; mul.wide.u32 off,idx,8; add.u64 in,in,off;",
        "ld.global.u64 val,[in]; shr.u64 high,val,16; cvt.u32.u64 h0,high; cvt.u32.u64 lo,val;",
        "shl.b32 lo,lo,16; mov.u32 zero,0;",
    ]
    for i in range(1,bands):
        out += [f"setp.gt.u32 use,b,{i}; mov.u32 h{i},0;",
                f"@use ld.global.u64 val,[in+{i*131072*8}];",
                f"@use shr.u64 high,val,16; @use cvt.u32.u64 h{i},high;"]
    out+=["st.global.v4.u32 [out],{h0,h1,h2,h3};"]
    if bands>=8:
        out+=["st.global.v4.u32 [out+16],{h4,h5,h6,h7};"]
        if bands>12:
            out+=["st.global.v4.u32 [out+32],{h8,h9,h10,h11};"]
            if bands==16:
                out+=["st.global.v4.u32 [out+48],{h12,h13,h14,h15};",
                      "st.global.u32 [out+64],lo;"]
            elif bands==15:
                out+=["st.global.v4.u32 [out+48],{h12,h13,h14,lo};"]
            elif bands==14:
                out+=["st.global.v4.u32 [out+48],{h12,h13,lo,zero};"]
            else:
                out+=["st.global.v4.u32 [out+48],{h12,lo,zero,zero};"]
        else:
            if bands>8:
                for i in range(bands,12):
                    out += [f"mov.u32 h{i},0;"]
                out+=["st.global.v4.u32 [out+32],{h8,h9,h10,h11};"]
            out+=[f"st.global.u32 [out+{4*bands}],lo;"]
    else:
        out+=["st.global.v4.u32 [out+16],{h4,h5,lo,zero};"]
    return "\n".join(out+["ret;","}",""])

REFINE = """
.visible .entry refine_groups(
.param .u64 xp,.param .u64 zp,.param .u64 calls,.param .u64 len,
.param .u64 result,.param .u64 written,.param .u32 cap,
.param .u32 xmin,.param .u32 zmin,.param .u32 threshold)
{
.reg .b64 xbase,zbase,q,groups,out,out_count,index64,addr,xpart,zpart,d,rr;
.reg .b32 t,b,g,warp,lane,x,z,vx,vz,dx,dz,row,k,step,tx,tz,origin,acc,bits,rv,pop,max_out,minimum;
.reg .pred stop,again,legal,hit;
ld.param.u64 xbase,[xp]; ld.param.u64 zbase,[zp]; ld.param.u64 q,[calls];
ld.param.u64 groups,[len]; ld.param.u64 out,[result]; ld.param.u64 out_count,[written];
ld.param.u32 max_out,[cap]; ld.param.u32 minimum,[threshold];
mov.u32 t,%tid.x; mov.u32 b,%ctaid.x; and.b32 lane,t,31; shr.u32 warp,t,5;
mad.lo.u32 g,b,4,warp; cvt.u64.u32 index64,g;
setp.ge.u64 stop,index64,groups; @stop ret;
mul.wide.u32 addr,g,16; add.u64 q,q,addr;
ld.global.v4.u32 {x,z,vx,vz},[q];
and.b32 dx,lane,3; shr.u32 dz,lane,2;
ld.param.u32 origin,[xmin]; sub.s32 tx,x,origin;
add.u32 tx,tx,lane; mul.wide.u32 addr,tx,8; add.u64 addr,xbase,addr;
ld.global.u64 xpart,[addr];
ld.param.u32 origin,[zmin]; sub.s32 tz,z,origin; mul.wide.u32 addr,tz,8; add.u64 zbase,zbase,addr;
mov.u32 row,0; mov.u32 acc,0;
ScoreRow:
ld.global.nc.u64 zpart,[zbase];
add.u64 d,xpart,zpart; xor.b64 d,d,0x5e434e432;
Redraw:
mul.lo.u64 d,d,0x5deece66d; add.u64 d,d,11; and.b64 d,d,0xffffffffffff;
shr.u64 rr,d,17; cvt.u32.u64 bits,rr;
setp.ge.u32 again,bits,2147483640; @again bra Redraw;
rem.u32 rv,bits,10; setp.eq.u32 hit,rv,0;
vote.sync.ballot.b32 bits,hit,0xffffffff;
sub.s32 k,row,dz; setp.le.u32 legal,k,16;
mov.u32 step,0;
@legal mul.wide.u32 addr,k,4; @legal mov.u64 rr,footprint; @legal add.u64 addr,addr,rr;
@legal ld.const.u32 step,[addr];
shl.b32 step,step,dx; and.b32 bits,bits,step; popc.b32 pop,bits; add.u32 acc,acc,pop;
add.u32 row,row,1; add.u64 zbase,zbase,8;
setp.lt.u32 again,row,20; @again bra.uni ScoreRow;
setp.ge.u32 stop,dx,vx; @stop ret;
setp.ge.u32 stop,dz,vz; @stop ret;
setp.lt.u32 stop,acc,minimum; @stop ret;
atom.global.add.u64 index64,[out_count],1;
cvt.u64.u32 addr,max_out; setp.ge.u64 stop,index64,addr; @stop ret;
shl.b64 addr,index64,4; add.u64 out,out,addr;
add.s32 x,x,dx; add.s32 z,z,dz;
st.global.v4.u32 [out],{acc,x,z,0};
ret;
}
"""
# The vector store needs a register for its fourth operand.
REFINE=REFINE.replace("st.global.v4.u32 [out],{acc,x,z,0};","mov.u32 rv,0;\nst.global.v4.u32 [out],{acc,x,z,rv};")

RARE = """
.visible .entry rare_groups(
.param .u64 zp,.param .u64 target,.param .u64 offsets,.param .u64 inverse,
.param .u64 queue,.param .u64 written,.param .u32 cap,
.param .u32 xlow,.param .u32 xhigh,.param .u32 zlow,.param .u32 zhigh)
{
.reg .b64 Z,T,O,I,Q,W,data,addr,zz,desired,check,qi,qp,c64;
.reg .b32 t,g,id,n,xmin,xmax,zmin,zmax,x,z,term,xroot,invert,tmp,deriv,cor;
.reg .b32 j,stop_index,bk,cap_n,xx,zz0,xend,zend,gx,gz,vx,vz,ix,iz;
.reg .pred stop,ok;
ld.param.u64 Z,[zp]; ld.param.u64 T,[target]; ld.param.u64 O,[offsets];
ld.param.u64 I,[inverse]; ld.param.u64 Q,[queue]; ld.param.u64 W,[written];
ld.param.u32 cap_n,[cap]; cvt.u64.u32 c64,cap_n;
ld.param.u32 xmin,[xlow]; ld.param.u32 xmax,[xhigh];
ld.param.u32 zmin,[zlow]; ld.param.u32 zmax,[zhigh];
mov.u32 t,%tid.x; mov.u32 g,%ctaid.x; mad.lo.u32 id,g,256,t;
sub.s32 n,zmax,zmin; add.u32 n,n,17; setp.ge.u32 stop,id,n; @stop ret;
add.s32 z,zmin,id; add.s32 z,z,-8;
mul.wide.u32 addr,id,8; add.u64 addr,Z,addr; ld.global.u64 zz,[addr];
shr.u64 data,zz,32; cvt.u32.u64 bk,data;
mul.wide.u32 addr,bk,4; add.u64 addr,O,addr;
ld.global.u32 j,[addr]; ld.global.u32 stop_index,[addr+12];
RareNext:
setp.ge.u32 stop,j,stop_index; @stop ret;
mul.wide.u32 addr,j,8; add.u64 addr,T,addr; ld.global.u64 data,[addr];
add.u32 j,j,1;
sub.u64 desired,data,zz; and.b64 desired,desired,0xffffffffffff;
cvt.u32.u64 term,desired; and.b32 tmp,term,255;
mul.wide.u32 addr,tmp,4; add.u64 addr,I,addr; ld.global.u32 tmp,[addr];
and.b32 xroot,tmp,255; shr.u32 invert,tmp,8;
mad.lo.u32 deriv,xroot,0x98320c,0x5ac0db;
mul.lo.u32 tmp,invert,deriv; sub.u32 tmp,2,tmp; mul.lo.u32 invert,invert,tmp;
mad.lo.u32 tmp,xroot,0x4c1906,0x5ac0db; mul.lo.u32 tmp,tmp,xroot;
sub.u32 cor,term,tmp; mul.lo.u32 cor,cor,invert; and.b32 cor,cor,0xff00; add.u32 xroot,xroot,cor;
mad.lo.u32 deriv,xroot,0x98320c,0x5ac0db;
mul.lo.u32 tmp,invert,deriv; sub.u32 tmp,2,tmp; mul.lo.u32 invert,invert,tmp;
mad.lo.u32 tmp,xroot,0x4c1906,0x5ac0db; mul.lo.u32 tmp,tmp,xroot;
sub.u32 cor,term,tmp; mul.lo.u32 cor,cor,invert; and.b32 cor,cor,0xffff0000; add.u32 x,xroot,cor;
add.s32 xx,x,-8; add.s32 xend,x,8; add.s32 zz0,z,-8; add.s32 zend,z,8;
setp.lt.s32 stop,xend,xmin; @stop bra RareNext;
setp.gt.s32 stop,xx,xmax; @stop bra RareNext;
call (check),coordinate_x,(x);
setp.ne.u64 stop,check,desired; @stop bra RareNext;
max.s32 xx,xx,xmin; min.s32 xend,xend,xmax;
max.s32 zz0,zz0,zmin; min.s32 zend,zend,zmax;
mov.s32 gz,zz0;
RareZ:
setp.gt.s32 stop,gz,zend; @stop bra RareNext;
sub.s32 vz,zend,gz; add.u32 vz,vz,1; min.u32 vz,vz,4;
mov.s32 gx,xx;
RareX:
setp.gt.s32 stop,gx,xend; @stop bra RareAdvanceZ;
sub.s32 vx,xend,gx; add.u32 vx,vx,1; min.u32 vx,vx,4;
atom.global.add.u64 qi,[W],1; setp.ge.u64 stop,qi,c64; @stop bra RareAdvanceX;
shl.b64 qp,qi,4; add.u64 qp,Q,qp;
st.global.v4.u32 [qp],{gx,gz,vx,vz};
RareAdvanceX:
add.s32 gx,gx,4; bra RareX;
RareAdvanceZ:
add.s32 gz,gz,4; bra RareZ;
}
"""

def support_program(bands=6):
    return HEADER+".const .align 4 .u32 footprint[17]={"+",".join(map(str,CIRCLE))+"};\n"+TERMS+make_pack(bands)+REFINE+RARE

SUPPORT=support_program()


class ScanDriver(Driver):
    def module(self,program,names):
        code=module_image(program, self.arch)
        data=c.create_string_buffer(code)
        mod=c.c_void_p()
        self.call("cuModuleLoadData",c.byref(mod),c.cast(data,c.c_void_p))
        self.modules.append(mod)
        return {name:self.function(mod,name) for name in names}

    def function(self,mod,name):
        fn=c.c_void_p()
        self.call("cuModuleGetFunction",c.byref(fn),mod,name.encode())
        return fn

    def start(self,fn,blocks,threads,*args):
        if blocks<=0:
            return
        params=(c.c_void_p*len(args))(*(c.cast(c.byref(x),c.c_void_p) for x in args))
        self.call("cuLaunchKernel",fn,c.c_uint(blocks),c.c_uint(1),c.c_uint(1),
                  c.c_uint(threads),c.c_uint(1),c.c_uint(1),c.c_uint(0),
                  c.c_void_p(),params,c.c_void_p())

    def zero(self,ptr,size=8):
        self.call("cuMemsetD8_v2",ptr,c.c_ubyte(0),c.c_size_t(size))

    def u64(self,ptr):
        out=c.c_uint64()
        self.call("cuMemcpyDtoH_v2",c.byref(out),ptr,c.c_size_t(8))
        return out.value

    def empty(self,nbytes):
        p=c.c_uint64()
        self.call("cuMemAlloc_v2",c.byref(p),c.c_size_t(nbytes))
        self.buffers.append(p)
        return p

    def release(self,p):
        self.call("cuMemFree_v2",p)
        self.buffers.remove(p)

