import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from litemapy import BlockState, Entity, Region, Schematic, TileEntity
from nbtlib import Compound
import SlimeFinder as app


def assert_distance_field_matches_bruteforce(afk_x, afk_z, width, length, slime_test):
    _, _, start_x, start_z, field = app.build_floor_distance_field(
        afk_x, afk_z, width, length, slime_test)
    spawnable = []
    for x in range(width):
        wx = start_x + x
        for z in range(length):
            wz = start_z + z
            if app.is_spawnable_floor_block(afk_x, afk_z, wx, wz, slime_test):
                spawnable.append((x, z))
    for x in range(width):
        for z in range(length):
            expected = min(
                [4] + [max(abs(x - sx), abs(z - sz)) for sx, sz in spawnable])
            assert field[x * length + z] == expected, (x, z, expected, field[x * length + z])


def roundtrip_case(afk_x, afk_z, width, length, enabled):
    # A stable mixed pattern exercises negative chunk floor division and leaves
    # both spawnable and non-spawnable areas in typical test dimensions.
    slime_test = lambda cx, cz: ((cx * 31 + cz * 17) % 5) in (0, 1)
    schem = app.create_slime_floor_schematic(
        123456789, afk_x, afk_z, width, length, "minecraft:tinted_glass",
        use_magma=enabled,
        use_wither=enabled,
        use_rod=enabled,
        use_portal_array=enabled,
        portal_axis_x=False,
        wither_base_soul=enabled,
        slime_chunk_at=slime_test)

    floor = schem.regions["floor"]
    portal = schem.regions["portal"]
    assert (floor.x, floor.z, floor.width, floor.length) == (
        -(width // 2), -(length // 2), width, length)
    center_x, center_z = width // 2, length // 2
    assert floor[center_x, 0, center_z].id == "minecraft:composter"
    if enabled:
        assert portal[center_x, 2, center_z].id == "minecraft:lightning_rod"

    with tempfile.TemporaryDirectory() as temp_dir:
        path = os.path.join(temp_dir, "projection.litematic")
        schem.save(path)
        loaded = Schematic.load(path)
        loaded_floor = loaded.regions["floor"]
        loaded_portal = loaded.regions["portal"]
        assert (loaded_floor.x, loaded_floor.z, loaded_floor.width, loaded_floor.length) == (
            floor.x, floor.z, width, length)
        assert loaded_floor[center_x, 0, center_z].id == "minecraft:composter"
        if enabled:
            assert loaded_portal[center_x, 2, center_z].id == "minecraft:lightning_rod"


def main():
    calls = []
    assert app.is_spawnable_floor_block(0, 0, -1, 25, lambda cx, cz: calls.append((cx, cz)) or True)
    assert calls[-1] == (-1, 1)
    assert not app.is_spawnable_floor_block(0, 0, 24, 0, lambda *_: True)
    assert app.is_spawnable_floor_block(0, 0, 128, 0, lambda *_: True)
    assert not app.is_spawnable_floor_block(0, 0, 129, 0, lambda *_: True)

    assert app.ensure_litematic_extension("demo") == "demo.litematic"
    assert app.ensure_litematic_extension("DEMO.LITEMATIC") == "DEMO.LITEMATIC"

    assert_distance_field_matches_bruteforce(-17, -33, 37, 51, lambda cx, cz: (cx + cz) % 3 == 0)
    for case in (
        (-17, -33, 32, 48, False),
        (-17, -33, 33, 49, True),
        (123, -456, 64, 35, True),
    ):
        roundtrip_case(*case)

    source = Region(20, 3, -10, -3, 2, -4)
    source[-2, 1, -3] = BlockState("minecraft:chest")
    tile = TileEntity(Compound())
    tile.position = (2, 1, 3)
    source.tile_entities.append(tile)
    entity = Entity("minecraft:pig")
    entity.position = (1.5, 1.0, 2.5)
    source.entities.append(entity)
    source.block_ticks.append(Compound())
    source.fluid_ticks.append(Compound())
    cloned = app.clone_litematic_region(source, 100, 5, -7)
    assert (cloned.x, cloned.y, cloned.z) == (120, 8, -17)
    assert (cloned.width, cloned.height, cloned.length) == (-3, 2, -4)
    assert cloned[-2, 1, -3].id == "minecraft:chest"
    assert cloned.tile_entities[0].position == (2, 1, 3)
    assert cloned.entities[0].position == (1.5, 1.0, 2.5)
    assert len(cloned.block_ticks) == len(cloned.fluid_ticks) == 1
    with tempfile.TemporaryDirectory() as temp_dir:
        path = os.path.join(temp_dir, "negative-region.litematic")
        Schematic(regions={"negative": cloned}).save(path)
        loaded = Schematic.load(path).regions["negative"]
        assert (loaded.width, loaded.height, loaded.length) == (-3, 2, -4)
        assert loaded[-2, 1, -3].id == "minecraft:chest"
        assert loaded.tile_entities[0].position == (2, 1, 3)
        assert loaded.entities[0].position == (1.5, 1.0, 2.5)
    print("projection tests: OK")


if __name__ == "__main__":
    main()
