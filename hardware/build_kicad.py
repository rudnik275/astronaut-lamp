"""Генератор платы драйвера лампы-космонавта для KiCad 10.

Запускать Python-ом из KiCad.app:
  PY=~/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
  $PY build_kicad.py build     # расставить детали, цепи, контур, зоны → astro-driver.kicad_pcb + .dsn
  $PY build_kicad.py finish    # после Freerouting: импорт .ses, заливка зон, BOM/CPL для JLCPCB
Freerouting между ними:
  java -jar freerouting.jar -de out/astro-driver.dsn -do out/astro-driver.ses -mp 60

Всё берётся из design.py (детали, цепи, координаты).
"""
import csv
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
NAME = "astro-driver"
PCB = os.path.join(OUT, NAME + ".kicad_pcb")
DSN = os.path.join(OUT, NAME + ".dsn")
SES = os.path.join(OUT, NAME + ".ses")
FP_ROOT = os.path.join(os.path.dirname(os.path.dirname(pcbnew.__file__)), "..", "..", "..", "..", "SharedSupport", "footprints")
FP_ROOT = os.path.normpath(FP_ROOT)
if not os.path.isdir(FP_ROOT):
    FP_ROOT = os.path.expanduser("~/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")

MM = pcbnew.FromMM
V = pcbnew.VECTOR2I_MM

POWER_NETS = {"+5V", "GND"} | {n for n in design.NETS if n.startswith(("DRAIN_", "LOAD_"))}


IO = pcbnew.PCB_IO_KICAD_SEXPR()   # helper pcbnew.FootprintLoad теряет тип плагина после первых вызовов
LIB_DIR = os.path.join(HERE, "lib", "astro.pretty")


def make_esp_footprint():
    """Копия ESP32-WROOM-32 из библиотеки KiCad, у которой courtyard сведён к корпусу модуля.

    Библиотечный courtyard включает 16 мм зоны вокруг антенны; у нас антенна свисает за край
    платы, поэтому зона там не нужна, а DRC иначе ругается на всё, что стоит левее модуля.
    Keepout-зона для меди под антенной остаётся."""
    from build_schematic import parse, dump, Str  # noqa: WPS433
    src = os.path.join(FP_ROOT, "RF_Module.pretty", "ESP32-WROOM-32.kicad_mod")
    with open(src, encoding="utf-8") as f:
        tree = parse(f.read())[0]
    def on_crtyd(e):
        return isinstance(e, list) and e and e[0] in ("fp_line", "fp_rect", "fp_poly", "fp_circle", "fp_arc") and \
            any(isinstance(a, list) and a[0] == "layer" and a[1] == "F.CrtYd" for a in e)
    out = [e for e in tree if not on_crtyd(e)]
    out[1] = Str("ESP32-WROOM-32_body")
    for e in out:   # переходные отверстия термопада: JLCPCB сверлит от 0.3 мм
        if isinstance(e, list) and e[0] == "pad" and e[1] == "39" and e[2] == "thru_hole":
            for a in e:
                if isinstance(a, list) and a[0] == "drill" and float(a[1]) < 0.3:
                    a[1] = "0.3"
    out.append(["fp_rect", ["start", "-9.25", "-14.95"], ["end", "9.25", "10.55"],
                ["stroke", ["width", "0.05"], ["type", "default"]], ["fill", "no"], ["layer", Str("F.CrtYd")],
                ["uuid", Str("b0d1e2f3-0000-4000-8000-000000000001")]])
    os.makedirs(LIB_DIR, exist_ok=True)
    with open(os.path.join(LIB_DIR, "ESP32-WROOM-32_body.kicad_mod"), "w", encoding="utf-8") as f:
        f.write(dump(out) + "\n")
    # таблица библиотек проекта, чтобы KiCad нашёл astro:* при открытии
    with open(os.path.join(OUT, "fp-lib-table"), "w", encoding="utf-8") as f:
        f.write('(fp_lib_table\n  (version 7)\n  (lib (name "astro")(type "KiCad")(uri "${KIPRJMOD}/../lib/astro.pretty")(options "")(descr "посадочные места проекта"))\n)\n')


def load_fp(fpid):
    lib, name = fpid.split(":")
    path = LIB_DIR if lib == "astro" else os.path.join(FP_ROOT, lib + ".pretty")
    fp = IO.FootprintLoad(path, name)
    if fp is None:
        raise SystemExit(f"нет посадочного места {fpid}")
    return fp


def build():
    os.makedirs(OUT, exist_ok=True)
    make_esp_footprint()
    board = pcbnew.BOARD()
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = MM(0.2)
    ds.m_MinClearance = MM(0.2)
    ds.m_ViasMinSize = MM(0.6)
    ds.m_MinThroughDrill = MM(0.3)
    ns = ds.m_NetSettings
    try:
        dnc = ns.GetDefaultNetclass()
        dnc.SetTrackWidth(MM(0.35))
        dnc.SetClearance(MM(0.2))
        dnc.SetViaDiameter(MM(0.7))
        dnc.SetViaDrill(MM(0.35))
        pnc = pcbnew.NETCLASS("Power")
        pnc.SetTrackWidth(MM(0.7))
        pnc.SetClearance(MM(0.2))
        pnc.SetViaDiameter(MM(0.9))
        pnc.SetViaDrill(MM(0.45))
        ns.SetNetclass("Power", pnc)
        for n in sorted(POWER_NETS):
            ns.SetNetclassPatternAssignment(n, "Power")
    except Exception as e:  # noqa: BLE001
        print("netclass API:", e)

    ds.m_SolderMaskExpansion = MM(0.05)
    ds.m_SolderMaskMinWidth = MM(0.0)

    # --- детали
    fps = {}
    small = ("R_0603", "C_0603", "C_0805", "SOT-23", "LED_0603", "D_SMA")
    for ref, p in design.PARTS.items():
        fp = load_fp(p["fp"])
        fp.SetReference(ref)
        fp.SetValue(p["value"])
        if any(s in p["fp"] for s in small):
            fp.Reference().SetVisible(False)   # мелочь: обозначения только на слое Fab, иначе шелкография в кашу
        x, y, rot = design.PLACE[ref]
        fp.SetPosition(V(x, y))
        fp.SetOrientationDegrees(rot)
        if p["fp"].startswith("Resistor_THT"):   # обозначение внутри контура, читается до запайки
            fp.Reference().SetPosition(V(x - 7.62, y)); fp.Reference().SetTextSize(V(0.9, 0.9)); fp.Reference().SetTextAngleDegrees(0)
        if p["fp"].startswith("Connector_PinHeader"):
            fp.Reference().SetVisible(False)
        board.Add(fp)
        fps[ref] = fp

    # --- цепи
    nets = {}
    for name in design.NETS:
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
        nets[name] = net
    missing = []
    for name, pins in design.NETS.items():
        for ref, padno in pins:
            hit = False
            for pad in fps[ref].Pads():
                if pad.GetNumber() == padno:
                    pad.SetNet(nets[name])
                    hit = True
            if not hit:
                missing.append(f"{ref}.{padno}")
    if missing:
        raise SystemExit("нет падов: " + ", ".join(missing))

    # --- шейки от падов VBUS USB-C: пады 0.6 мм в ряду с шагом 0.5, туда широкая шина не заходит.
    # Тонкий отвод вверх и наружу (мимо соседнего GND-пада), дальше ведёт Freerouting. Дорожки
    # заблокированы, чтобы трассировщик их не перекладывал.
    jx, jy, _ = design.PLACE["J1"]
    p5 = nets["+5V"]
    def track(x1, y1, x2, y2, w, net, layer=pcbnew.F_Cu):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(V(x1, y1)); t.SetEnd(V(x2, y2)); t.SetWidth(MM(w)); t.SetLayer(layer); t.SetNet(net)
        t.SetLocked(True); board.Add(t)
    def via(x, y, net, d=0.8, drill=0.4):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(V(x, y)); v.SetDrill(MM(drill)); v.SetWidth(MM(d))
        v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(net)
        v.SetLocked(True); board.Add(v)
    # шейка от площадки VBUS A4/B9 вверх и переходное отверстие: дальше +5 ведёт Freerouting
    # любым слоем; правее должны пройти D+, D-, CC1, CC2
    px = jx - 2.45
    track(px, jy - 4.045, px, jy - 7.0, 0.5, p5)
    via(px, jy - 7.0, p5)
    # дальше по нижнему слою к входу стабилизатора (U3 pin 3, у SOT-223 выводы слева
    # столбиком), мимо экрана USB-C
    u3in = next(p for p in fps["U3"].Pads() if p.GetNumber() == "3").GetPosition()
    u3x, u3y = pcbnew.ToMM(u3in.x), pcbnew.ToMM(u3in.y)
    track(px, jy - 7.0, 40.0, jy - 7.0, 0.7, p5, pcbnew.B_Cu)
    track(40.0, jy - 7.0, 40.0, 41.3, 0.7, p5, pcbnew.B_Cu)
    via(40.0, 41.3, p5)
    track(40.0, 41.3, u3x + 1.2, 41.3, 0.7, p5)
    track(u3x + 1.2, 41.3, u3x, u3y, 0.7, p5)
    c2in = next(p for p in fps["C2"].Pads() if p.GetNumber() == "1").GetPosition()
    track(pcbnew.ToMM(c2in.x), 41.3, pcbnew.ToMM(c2in.x), pcbnew.ToMM(c2in.y), 0.7, p5)   # входной конденсатор
    # D+ (A6, B6) мостиком сверху над падами; D- (A7, B7) мостиком снизу через переходные:
    # пары перемежаются, без этого трассировщик через раз не пролезает
    dp, dm = nets["USB_DP"], nets["USB_DM"]
    pad = lambda n: (lambda q: (pcbnew.ToMM(q.x), pcbnew.ToMM(q.y)))(next(p for p in fps["J1"].Pads() if p.GetNumber() == n).GetPosition())
    (a6x, a6y), (b6x, _), (a7x, _), (b7x, _) = pad("A6"), pad("B6"), pad("A7"), pad("B7")
    track(a6x, a6y, a6x, a6y - 1.36, 0.3, dp); track(a6x, a6y - 1.36, b6x, a6y - 1.36, 0.3, dp); track(b6x, a6y - 1.36, b6x, a6y, 0.3, dp)
    # D+ дальше вверх под корпусом CH340C к его пину 5 (коридор между R1 и R2)
    u2dp = next(p for p in fps["U2"].Pads() if p.GetNumber() == "5").GetPosition()
    mx = (a6x + b6x) / 2
    track(mx, a6y - 1.36, mx, pcbnew.ToMM(u2dp.y), 0.3, dp)
    track(mx, pcbnew.ToMM(u2dp.y), pcbnew.ToMM(u2dp.x), pcbnew.ToMM(u2dp.y), 0.3, dp)
    for xx in (a7x, b7x):
        track(xx, a6y, xx, a6y + 1.5, 0.25, dm)
        via(xx, a6y + 1.5, dm, d=0.7, drill=0.35)
    track(b7x, a6y + 1.5, a7x, a6y + 1.5, 0.3, dm, pcbnew.B_Cu)
    # CC1/CC2 прямо вверх к своим резисторам 5.1k (стоят над разъёмом между шейками)
    for pad, rref in (("A5", "R1"), ("B5", "R2")):
        pj = next(p for p in fps["J1"].Pads() if p.GetNumber() == pad)
        pr = next(p for p in fps[rref].Pads() if p.GetNumber() == "1")
        a, b = pj.GetPosition(), pr.GetPosition()
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(a); t.SetEnd(b); t.SetWidth(MM(0.3)); t.SetLayer(pcbnew.F_Cu); t.SetNet(nets["CC1" if pad == "A5" else "CC2"])
        t.SetLocked(True); board.Add(t)
    # +5 между соседними пинами разъёмов мотора и лазера (J3.2 → J4.1), трассировщику туда тесно
    x3, y3, _ = design.PLACE["J3"]; x4, y4, _ = design.PLACE["J4"]
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(V(x3, y3 + 2.54)); t.SetEnd(V(x4, y4)); t.SetWidth(MM(0.7)); t.SetLayer(pcbnew.B_Cu); t.SetNet(p5)
    t.SetLocked(True); board.Add(t)

    # --- контур
    W, H = design.BOARD_W, design.BOARD_H
    r = 2.0
    def seg(x1, y1, x2, y2):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(x1, y1)); s.SetEnd(V(x2, y2))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1))
        board.Add(s)
    def arc(cx, cy, sx, sy, ex, ey):
        a = pcbnew.PCB_SHAPE(board)
        a.SetShape(pcbnew.SHAPE_T_ARC)
        a.SetCenter(V(cx, cy)); a.SetStart(V(sx, sy)); a.SetEnd(V(ex, ey))
        a.SetLayer(pcbnew.Edge_Cuts); a.SetWidth(MM(0.1))
        board.Add(a)
    seg(r, 0, W - r, 0); seg(W, r, W, H - r); seg(W - r, H, r, H); seg(0, H - r, 0, r)
    # дуги по часовой стрелке в координатах KiCad (y вниз): start → end
    arc(W - r, r, W - r, 0, W, r)
    arc(W - r, H - r, W, H - r, W - r, H)
    arc(r, H - r, r, H, 0, H - r)
    arc(r, r, 0, r, r, 0)

    # зоны земли добавляются в finish(): в DSN они уходят как «плоскость», и Freerouting
    # считает землю разведённой, хотя чужие дорожки режут полигон на острова. Без зон он
    # разводит GND дорожками, а полигоны потом только усиливают.

    # --- шелкография
    def text(s, x, y, size=1.0, layer=pcbnew.F_SilkS, rot=0):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(s); t.SetPosition(V(x, y)); t.SetLayer(layer)
        t.SetTextSize(V(size, size)); t.SetTextThickness(MM(0.15))
        t.SetTextAngleDegrees(rot)
        board.Add(t)
    text("astro-driver v1", 20.0, 2.6, 1.0)
    # подписи разъёмов читаются сверху вниз, как идут пины
    text("V G R B", 5.6, 11.3, 0.8, rot=270); text("M +", 5.6, 20.3, 0.8, rot=270); text("+ -", 5.6, 26.8, 0.8, rot=270)
    text("+ -", 5.6, 33.3, 0.8, rot=270)
    text("LED", 2.5, 4.4, 0.8); text("MOT", 2.5, 16.4, 0.8); text("LSR", 2.5, 22.9, 0.8); text("5V", 2.5, 29.4, 0.8)
    text("BOOT", 27.0, 34.2, 0.8); text("EN", 27.0, 41.8, 0.8)

    pcbnew.SaveBoard(PCB, board)
    pcbnew.ExportSpecctraDSN(board, DSN)
    print("плата:", PCB)
    print("dsn:", DSN)
    print("деталей:", len(fps), "цепей:", len(nets))


def free_spot(board, pos, net, radius_mm, clearance_mm=0.25, skip=(), seg_from=None, seg_w=0.3):
    """Свободно ли место под переходное отверстие радиуса radius в точке pos (мм)
    и под отвод к нему от seg_from (если задан)? Учитывает пады, дорожки, запретные зоны."""
    probes = [pcbnew.SHAPE_CIRCLE(V(*pos), MM(radius_mm))]
    if seg_from is not None:
        probes.append(pcbnew.SHAPE_SEGMENT(V(*seg_from), V(*pos), MM(seg_w)))
    W, H = design.BOARD_W, design.BOARD_H
    if not (radius_mm + 0.5 < pos[0] < W - radius_mm - 0.5 and radius_mm + 0.5 < pos[1] < H - radius_mm - 0.5):
        return False
    for z in board.Zones():
        if z.GetIsRuleArea() and z.Outline().Collide(V(*pos), MM(radius_mm + 0.1)):
            return False
    for fp in board.GetFootprints():
        for z in fp.Zones():
            if z.GetIsRuleArea() and z.Outline().Collide(V(*pos), MM(radius_mm + 0.1)):
                return False
        for pad in fp.Pads():
            if pad in skip:
                continue
            same = pad.GetNetname() == net
            for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
                if not pad.IsOnLayer(layer):
                    continue
                for pr in probes:
                    if pad.GetEffectiveShape(layer).Collide(pr, MM(0.05 if same else clearance_mm)):
                        return False
        for g in fp.GraphicalItems():
            if g.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu):
                for pr in probes:
                    if g.GetEffectiveShape().Collide(pr, MM(clearance_mm)):
                        return False
    for t in board.GetTracks():
        same = t.GetNetname() == net
        for pr in probes:
            if t.GetEffectiveShape().Collide(pr, MM(0.05 if same else clearance_mm)):
                return False
    return True


def stitch_gnd(board):
    """Переходное отверстие у каждого SMD-пада земли на верхнем слое: полигон сверху рвётся дорожками
    на острова, а нижний слой цельный. Freerouting зон не знает, поэтому стежки ставим сами."""
    import math
    gnd = board.FindNet("GND")
    added = joined = failed = []
    added, joined, failed = 0, 0, []
    pth_gnd = [p for fp in board.GetFootprints() for p in fp.Pads()
               if p.GetNetname() == "GND" and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetname() != "GND" or pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or not pad.IsOnLayer(pcbnew.F_Cu):
                continue
            c = pad.GetPosition()
            cx, cy = pcbnew.ToMM(c.x), pcbnew.ToMM(c.y)
            placed = False
            for dist in (1.1, 1.4, 1.8, 2.3, 2.8):
                for ang in range(0, 360, 30):
                    px = cx + dist * math.cos(math.radians(ang))
                    py = cy + dist * math.sin(math.radians(ang))
                    if not free_spot(board, (px, py), "GND", 0.35, skip=(pad,), seg_from=(cx, cy)):
                        continue
                    via = pcbnew.PCB_VIA(board)
                    via.SetPosition(V(px, py)); via.SetDrill(MM(0.35)); via.SetWidth(MM(0.7))
                    via.SetViaType(pcbnew.VIATYPE_THROUGH); via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                    via.SetNet(gnd); board.Add(via)
                    tr = pcbnew.PCB_TRACK(board)
                    tr.SetStart(c); tr.SetEnd(V(px, py)); tr.SetWidth(MM(0.3)); tr.SetLayer(pcbnew.F_Cu); tr.SetNet(gnd)
                    board.Add(tr)
                    added += 1; placed = True
                    break
                if placed:
                    break
            if placed:
                continue
            # запасной путь: короткий отвод к сквозному GND-паду рядом (экран USB-C, кнопки)
            for tp in sorted(pth_gnd, key=lambda p: (p.GetPosition() - c).EuclideanNorm()):
                tpos = tp.GetPosition()
                if (tpos - c).EuclideanNorm() > MM(3.0):
                    break
                tx, ty = pcbnew.ToMM(tpos.x), pcbnew.ToMM(tpos.y)
                if free_spot(board, (tx, ty), "GND", 0.01, skip=(pad, tp), seg_from=(cx, cy)):
                    tr = pcbnew.PCB_TRACK(board)
                    tr.SetStart(c); tr.SetEnd(tpos); tr.SetWidth(MM(0.3)); tr.SetLayer(pcbnew.F_Cu); tr.SetNet(gnd)
                    board.Add(tr); joined += 1; placed = True
                    break
            if not placed:
                failed.append(f"{fp.GetReference()}.{pad.GetNumber()}")
    print("стежков GND добавлено:", added, "| отводов к сквозным GND:", joined, "| без стежка:", failed)


def add_zones(board):
    W, H = design.BOARD_W, design.BOARD_H
    gnd = board.FindNet("GND")
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(gnd)
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetMinThickness(MM(0.25))
        z.SetLocalClearance(MM(0.25))
        o = z.Outline(); o.NewOutline()
        for x, y in ((0.5, 0.5), (W - 0.5, 0.5), (W - 0.5, H - 0.5), (0.5, H - 0.5)):
            o.Append(V(x, y))
        board.Add(z)


def finish():
    board = pcbnew.LoadBoard(PCB)
    if os.path.exists(SES):
        ok = pcbnew.ImportSpecctraSES(board, SES)
        print("ses import:", ok)
    if not list(board.Zones()):
        add_zones(board)
    stitch_gnd(board)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcbnew.SaveBoard(PCB, board)
    # неразведённые связи
    board = pcbnew.LoadBoard(PCB)
    conn = board.GetConnectivity()
    unrouted = conn.GetUnconnectedCount(True)
    print("неразведённых связей:", unrouted)

    # BOM + CPL для JLCPCB (только SMD с кодом LCSC)
    bom_path = os.path.join(OUT, "jlc-bom.csv")
    cpl_path = os.path.join(OUT, "jlc-cpl.csv")
    groups = {}
    for ref, p in design.PARTS.items():
        if p["lcsc"]:
            groups.setdefault((p["value"], p["fp"].split(":")[1], p["lcsc"]), []).append(ref)
    with open(bom_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (val, fpn, lcsc), refs in sorted(groups.items(), key=lambda kv: kv[1][0]):
            w.writerow([val, ",".join(sorted(refs)), fpn, lcsc])
    with open(cpl_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for fp in board.GetFootprints():
            ref = fp.GetReference()
            if not design.PARTS.get(ref, {}).get("lcsc"):
                continue
            pos = fp.GetPosition()
            w.writerow([ref, f"{pcbnew.ToMM(pos.x):.3f}mm", f"{-pcbnew.ToMM(pos.y):.3f}mm", "Top", f"{fp.GetOrientationDegrees():.0f}"])
    print("bom:", bom_path); print("cpl:", cpl_path)


if __name__ == "__main__":
    {"build": build, "finish": finish}[sys.argv[1]]()
