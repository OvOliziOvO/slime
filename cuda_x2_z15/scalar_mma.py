"""Lower binary matrix products to warp shuffles and popcounts on older GPUs."""
import re

BINARY_MMA = re.compile(
    r"mma\.sync\.aligned\.m(8|16)n8k(128|256)\.row\.col\.s32\.b1\.b1\.s32\.and\.popc\s+"
    r"\{([^}]+)\},\{([^}]+)\},\{([^}]+)\},\{([^}]+)\};"
)


def lower_binary_mma(program):
    """Preserve the row/column fragment layout of each binary MMA."""
    lowered = BINARY_MMA.sub(_scalar_product, program)
    if "mma.sync" in lowered:
        raise ValueError("Unsupported binary matrix instruction")
    return lowered


def _scalar_product(match):
    rows, width = map(int, match.group(1, 2))
    outputs, lhs, rhs, accumulators = (
        [register.strip() for register in fragment.split(",")]
        for fragment in match.group(3, 4, 5, 6)
    )
    row_fragments = rows // 8
    k_fragments = width // 128
    # Each lane owns two adjacent columns in group laneId >> 2. The
    # four lanes in each input group hold consecutive 32-bit K slices.
    active = [i for i, register in enumerate(outputs) if not register.startswith("junk")]
    code = [
        "{",
        ".reg .b32 a_base,b_base,a_lane,b_lane,lhs_word,rhs_word,bits,count;",
        ".reg .b32 total<4>;",
        "mov.u32 a_base,%laneid;",
        "and.b32 b_base,a_base,3;",
        "and.b32 a_base,a_base,28;",
        "shl.b32 b_base,b_base,3;",
    ]
    for i in active:
        code.append(f"mov.b32 total{i},{accumulators[i]};")
    for k in range(k_fragments):
        for slice_id in range(4):
            code.append(f"add.u32 a_lane,a_base,{slice_id};")
            for row in range(row_fragments):
                source = lhs[k * row_fragments + row]
                code.append(f"shfl.sync.idx.b32 lhs_word,{source},a_lane,31,0xffffffff;")
                for column in range(2):
                    i = 2 * row + column
                    if i not in active:
                        continue
                    code.extend([
                        f"add.u32 b_lane,b_base,{4 * column + slice_id};",
                        f"shfl.sync.idx.b32 rhs_word,{rhs[k]},b_lane,31,0xffffffff;",
                        "and.b32 bits,lhs_word,rhs_word;",
                        "popc.b32 count,bits;",
                        f"add.s32 total{i},total{i},count;",
                    ])
    # Some instructions use the same registers for input and output.
    code.extend(f"mov.b32 {outputs[i]},total{i};" for i in active)
    return "\n".join([*code, "}"])
