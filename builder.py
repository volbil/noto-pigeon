from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from pathlib import Path


ROOT = Path("./src")
DEMO_IMAGE = ROOT / "demo.png"

SOURCE_FONT = ROOT / "NotoSansMono-Regular.ttf"
VARIABLE_FONT = ROOT / "NotoSansMono[wdth,wght].ttf"
DIGIT_FONT = ROOT / "NunitoSans-Regular.ttf"
MODIFIED_FONT = Path(".") / "NotoSansMono-PG.ttf"

DONOR_WEIGHT = 550
DONOR_WIDTH = 100

DEMO_TEXT = (
    "Аа Бб Вв Гг Ґґ Дд Ее Єє Жж Зз Ии\n"
    "Іі Її Йй Кк Лл Мм Нн Оо Пп Рр Сс\n"
    "Тт Уу Фф Хх Цц Чч Шш Щщ Ьь Юю Яя\n"
    "\n"
    "0123456789\n"
    "\n"
    "Це було тьмяно освітлене приміщення."
)

LOWER_TO_UPPER = [
    ("ф", "Ф", True),
    ("у", "У", True),
    ("р", "Р", True),
    ("y", "Y", True),
    ("p", "P", True),
    ("g", "G", True),
]

DIGITS = "0123456789"


def read_name(font: TTFont, name_id: int) -> str:
    name_table = font["name"]
    record = name_table.getName(name_id, 3, 1, 0x409)

    if record is None:
        record = next(r for r in name_table.names if r.nameID == name_id)

    return record.toUnicode()


def rename_font(font: TTFont) -> None:
    family_old = read_name(font, 1)  # Noto Sans Mono
    ps_old = family_old.replace(" ", "")  # NotoSansMono
    family_new = f"{family_old} PG"
    ps_new = f"{ps_old}PG"

    rules = {
        1: (family_old, family_new),
        3: (ps_old, ps_new),
        4: (family_old, family_new),
        6: (ps_old, ps_new),
        16: (family_old, family_new),
        18: (family_old, family_new),
        21: (family_old, family_new),
    }

    for record in font["name"].names:
        rule = rules.get(record.nameID)
        if rule is None:
            continue

        old, new = rule
        text = record.toUnicode()
        if old in text:
            record.string = text.replace(old, new)


def instantiate(path: Path, wght: float, wdth: float) -> TTFont:
    return instantiateVariableFont(TTFont(path), {"wght": wght, "wdth": wdth})


def replace_digits(
    font: TTFont, digit_src: Path, digits: str, is_monospace: bool
) -> None:
    digit_font = TTFont(digit_src)
    digit_cmap = digit_font.getBestCmap()
    digit_glyf = digit_font["glyf"]
    digit_glyphset = digit_font.getGlyphSet()
    digit_hmtx = digit_font["hmtx"]

    cmap = font.getBestCmap()
    glyf = font["glyf"]
    hmtx = font["hmtx"]

    for ch in digits:
        src_name = digit_cmap[ord(ch)]
        dst_name = cmap[ord(ch)]
        src_glyph = digit_glyf[src_name]
        src_glyph.recalcBounds(digit_glyf)

        if is_monospace:
            orig_adv, _ = hmtx[dst_name]
            outline_w = src_glyph.xMax - src_glyph.xMin
            dx = (orig_adv - outline_w) / 2 - src_glyph.xMin
            new_adv = orig_adv
            new_lsb = round((orig_adv - outline_w) / 2)

        else:
            src_adv, src_lsb = digit_hmtx[src_name]
            dx = 0
            new_adv = src_adv
            new_lsb = src_lsb

        recorder = DecomposingRecordingPen(digit_glyphset)
        digit_glyphset[src_name].draw(recorder)

        pen = TTGlyphPen(None)
        recorder.replay(TransformPen(pen, (1.0, 0, 0, 1.0, dx, 0)))
        glyf[dst_name] = pen.glyph()

        hmtx[dst_name] = (new_adv, new_lsb)


def build_modified_font(src: Path, heavy: TTFont, dst: Path) -> None:
    font = TTFont(src)
    cmap = font.getBestCmap()
    heavy_cmap = heavy.getBestCmap()
    glyf = font["glyf"]
    heavy_glyf = heavy["glyf"]
    heavy_glyphset = heavy.getGlyphSet()
    hmtx = font["hmtx"]
    heavy_hmtx = heavy["hmtx"]

    o_glyph = glyf[cmap[0x043E]]
    o_glyph.recalcBounds(glyf)
    target_top = o_glyph.yMax

    is_monospace = font["OS/2"].panose.bProportion == 9

    for lower_ch, upper_ch, downscale in LOWER_TO_UPPER:
        lower_name = cmap[ord(lower_ch)]
        heavy_upper_name = heavy_cmap[ord(upper_ch)]
        upper_glyph = heavy_glyf[heavy_upper_name]
        upper_glyph.recalcBounds(heavy_glyf)
        scale = (target_top / upper_glyph.yMax) if downscale else 1.0

        if is_monospace:
            orig_adv, _ = hmtx[lower_name]
            outline_w = (upper_glyph.xMax - upper_glyph.xMin) * scale
            dx = (orig_adv - outline_w) / 2 - upper_glyph.xMin * scale
            new_adv = orig_adv
            new_lsb = round((orig_adv - outline_w) / 2)

        else:
            upper_adv, upper_lsb = heavy_hmtx[heavy_upper_name]
            dx = 0
            new_adv = round(upper_adv * scale)
            new_lsb = round(upper_lsb * scale)

        recorder = DecomposingRecordingPen(heavy_glyphset)
        heavy_glyphset[heavy_upper_name].draw(recorder)

        pen = TTGlyphPen(None)
        recorder.replay(TransformPen(pen, (scale, 0, 0, scale, dx, 0)))
        glyf[lower_name] = pen.glyph()

        hmtx[lower_name] = (new_adv, new_lsb)

    replace_digits(font, DIGIT_FONT, DIGITS, is_monospace)

    rename_font(font)
    font.save(dst)


def main() -> None:
    donor = instantiate(VARIABLE_FONT, DONOR_WEIGHT, DONOR_WIDTH)
    build_modified_font(SOURCE_FONT, donor, MODIFIED_FONT)
    print(f"Згенерували {DEMO_IMAGE.name}")


if __name__ == "__main__":
    main()
