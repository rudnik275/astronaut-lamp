"""Генератор принципиальной схемы KiCad (astro-driver.kicad_sch + .kicad_pro) из design.py.

Схема «на метках»: каждый символ стоит отдельно, к каждому выводу привязана глобальная
метка с именем цепи, неиспользуемые выводы помечены крестиком. Не красиво, зато
гарантированно совпадает с платой: и схема, и плата рождаются из одного NETS.
Проверка: kicad-cli sch export netlist → сравнить с design.NETS (см. check_netlist()).

Запуск обычным python3 (pcbnew не нужен): python3 build_schematic.py
"""
import json
import math
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
NAME = "astro-driver"
SYM_ROOT = os.path.expanduser("~/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols")

# символ схемы для каждой детали (библиотека KiCad 10); нумерация выводов = падам платы
SYMBOLS = {
    "U1": "RF_Module:ESP32-WROOM-32", "U2": "Interface_USB:CH340C", "U3": "Regulator_Linear:AMS1117-3.3",
    "J1": "Connector:USB_C_Receptacle_USB2.0_16P",
    "Q1": "Transistor_FET:AO3400A", "Q2": "Transistor_FET:AO3400A", "Q3": "Transistor_FET:AO3400A",
    "Q4": "Transistor_FET:AO3400A", "Q5": "Transistor_FET:AO3400A",
    "Q6": "Transistor_BJT:Q_NPN_BEC", "Q7": "Transistor_BJT:Q_NPN_BEC",   # S8050 SOT-23: 1 B, 2 E, 3 C
    "D1": "Diode:SS14", "D2": "Device:LED", "C1": "Device:C_Polarized",
    "J2": "Connector_Generic:Conn_01x04", "J3": "Connector_Generic:Conn_01x02",
    "J4": "Connector_Generic:Conn_01x02", "J5": "Connector_Generic:Conn_01x02",
    "SW1": "Switch:SW_Push", "SW2": "Switch:SW_Push",
}
for ref, p in design.PARTS.items():
    if ref in SYMBOLS:
        continue
    if ref.startswith("H"):
        SYMBOLS[ref] = "Mechanical:MountingHole"
    elif ref.startswith("C"):
        SYMBOLS[ref] = "Device:C"
    elif ref.startswith("R"):
        SYMBOLS[ref] = "Device:R"

# --------------------------------------------------------------- s-expr
class Str(str):
    """строка, которую при выводе нужно взять в кавычки"""


def tokenize(text):
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c in "()":
            yield c; i += 1
        elif c == '"':
            j = i + 1; buf = []
            while text[j] != '"':
                if text[j] == "\\":
                    buf.append(text[j:j + 2]); j += 2
                else:
                    buf.append(text[j]); j += 1
            yield Str("".join(buf)); i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in "()":
                j += 1
            yield text[i:j]; i = j


def parse(text):
    stack = [[]]
    for t in tokenize(text):
        if t == "(":
            stack.append([])
        elif t == ")":
            lst = stack.pop(); stack[-1].append(lst)
        else:
            stack[-1].append(t)
    return stack[0]


def dump(x, ind=0):
    if isinstance(x, Str):
        return '"' + x.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(x, str):
        return x
    if not x:
        return "()"
    if all(not isinstance(e, list) for e in x):
        return "(" + " ".join(dump(e) for e in x) + ")"
    pad = "\n" + "\t" * (ind + 1)
    head = [dump(e) for e in x if not isinstance(e, list)]
    tail = [dump(e, ind + 1) for e in x if isinstance(e, list)]
    return "(" + " ".join(head) + pad + pad.join(tail) + "\n" + "\t" * ind + ")"


_libcache = {}


def lib_symbols(lib):
    if lib not in _libcache:
        with open(os.path.join(SYM_ROOT, lib + ".kicad_sym"), encoding="utf-8") as f:
            tree = parse(f.read())[0]
        _libcache[lib] = {e[1]: e for e in tree if isinstance(e, list) and e and e[0] == "symbol"}
    return _libcache[lib]


def resolve(lib, name):
    """Плоский символ (extends раскрыт) с id Lib:Name, sub-units Name_x_y."""
    syms = lib_symbols(lib)
    sym = syms[name]
    ext = [e for e in sym if isinstance(e, list) and e[0] == "extends"]
    if ext:
        parent = resolve(lib, ext[0][1])
        pname = ext[0][1]
        child_props = {e[1]: e for e in sym if isinstance(e, list) and e[0] == "property"}
        out = [ "symbol", Str(f"{lib}:{name}") ]
        for e in parent[2:]:
            if isinstance(e, list) and e[0] == "property":
                e = child_props.pop(e[1], e)
            elif isinstance(e, list) and e[0] == "symbol":
                e = list(e); e[1] = Str(e[1].replace(pname, name, 1))
            out.append(e)
        out.extend(child_props.values())
        return out
    out = list(sym); out[1] = Str(f"{lib}:{name}")
    return out


def pins_of(symdef):
    """[(number, x, y, angle, length)] в координатах символа (y вверх)"""
    res = []
    for unit in symdef:
        if not (isinstance(unit, list) and unit[0] == "symbol"):
            continue
        for e in unit:
            if isinstance(e, list) and e[0] == "pin":
                at = next(a for a in e if isinstance(a, list) and a[0] == "at")
                ln = next(a for a in e if isinstance(a, list) and a[0] == "length")
                num = next(a for a in e if isinstance(a, list) and a[0] == "number")
                res.append((num[1], float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0, float(ln[1])))
    return res


def bbox(symdef):
    xs, ys = [0.0], [0.0]
    for unit in symdef:
        if not (isinstance(unit, list) and unit[0] == "symbol"):
            continue
        for e in unit:
            if not isinstance(e, list):
                continue
            for a in e:
                if isinstance(a, list) and a[0] in ("start", "end", "at", "xy", "center"):
                    xs.append(float(a[1])); ys.append(float(a[2]))
                if isinstance(a, list) and a[0] == "pts":
                    for p in a[1:]:
                        xs.append(float(p[1])); ys.append(float(p[2]))
            if e[0] == "pin":
                at = next(a for a in e if isinstance(a, list) and a[0] == "at")
                ln = next(a for a in e if isinstance(a, list) and a[0] == "length")
                ang = math.radians(float(at[3]) if len(at) > 3 else 0)
                xs.append(float(at[1]) + float(ln[1]) * math.cos(ang)); ys.append(float(at[2]) + float(ln[1]) * math.sin(ang))
    return min(xs), min(ys), max(xs), max(ys)


def grid(v, g=1.27):
    return round(round(v / g) * g, 2)


# --------------------------------------------------------------- generation
def build():
    os.makedirs(OUT, exist_ok=True)
    root_uuid = str(uuid.uuid4())
    pin_net = {}
    for net, pins in design.NETS.items():
        for ref, pad in pins:
            pin_net[(ref, pad)] = net

    order = ["U1", "U2", "U3", "J1", "J2", "J3", "J4", "J5", "SW1", "SW2", "C1"] + \
            [r for r in design.PARTS if r.startswith("Q")] + [r for r in design.PARTS if r.startswith("D")] + \
            [r for r in design.PARTS if r.startswith("R")] + \
            [r for r in design.PARTS if r.startswith("C") and r != "C1"] + [r for r in design.PARTS if r.startswith("H")]

    libsyms = {}
    items = []
    x, y, rowh = 30.0, 35.0, 0.0
    PAGE_W = 420.0
    LABEL_W = 22.0  # место под метки слева/справа
    for ref in order:
        lib, name = SYMBOLS[ref].split(":")
        key = f"{lib}:{name}"
        if key not in libsyms:
            libsyms[key] = resolve(lib, name)
        sd = libsyms[key]
        x0, y0, x1, y1 = bbox(sd)
        w = (x1 - x0) + 2 * LABEL_W
        h = (y1 - y0) + 14
        if x + w > PAGE_W - 20:
            x, y, rowh = 30.0, y + rowh, 0.0
        sx, sy = grid(x - x0 + LABEL_W), grid(y - y0)   # y символа «вверх» → ставим так, чтобы верх был у y
        # (в схеме y вниз: точка символа (px,py) → (sx+px, sy-py)); верх символа y1 → sy - y1 = y  ⇒ sy = y + y1
        sy = grid(y + y1)
        rowh = max(rowh, h)
        x += w
        uid = str(uuid.uuid4())
        p = design.PARTS[ref]
        sym = ["symbol", ["lib_id", Str(key)], ["at", f"{sx}", f"{sy}", "0"], ["unit", "1"],
               ["exclude_from_sim", "no"], ["in_bom", "yes" if not ref.startswith("H") else "no"], ["on_board", "yes"], ["dnp", "no"],
               ["uuid", Str(uid)],
               ["property", Str("Reference"), Str(ref), ["at", f"{sx}", f"{grid(sy - y1 - 2.54)}", "0"], ["effects", ["font", ["size", "1.27", "1.27"]]]],
               ["property", Str("Value"), Str(p["value"]), ["at", f"{sx}", f"{grid(sy - y0 + 2.54)}", "0"], ["effects", ["font", ["size", "1.27", "1.27"]]]],
               ["property", Str("Footprint"), Str(p["fp"]), ["at", f"{sx}", f"{sy}", "0"], ["hide", "yes"], ["effects", ["font", ["size", "1.27", "1.27"]]]],
               ["property", Str("Datasheet"), Str(""), ["at", f"{sx}", f"{sy}", "0"], ["hide", "yes"], ["effects", ["font", ["size", "1.27", "1.27"]]]],
               ["property", Str("LCSC"), Str(p["lcsc"] or ""), ["at", f"{sx}", f"{sy}", "0"], ["hide", "yes"], ["effects", ["font", ["size", "1.27", "1.27"]]]],
               ]
        for num, px, py, ang, ln in pins_of(sd):
            sym.append(["pin", Str(num), ["uuid", Str(str(uuid.uuid4()))]])
            # (at X Y A) вывода в библиотеке = точка подключения; угол A смотрит внутрь корпуса
            ex, ey = grid(sx + px), grid(sy - py)
            net = pin_net.get((ref, num))
            if net is None:
                items.append(["no_connect", ["at", f"{ex}", f"{ey}"], ["uuid", Str(str(uuid.uuid4()))]])
            else:
                rot = (int(ang) + 180) % 360
                just = "right" if rot in (180, 270) else "left"
                items.append(["global_label", Str(net), ["shape", "bidirectional"], ["at", f"{ex}", f"{ey}", f"{rot}"],
                              ["fields_autoplaced", "yes"],
                              ["effects", ["font", ["size", "1.27", "1.27"]], ["justify", just]],
                              ["uuid", Str(str(uuid.uuid4()))],
                              ["property", Str("Intersheetrefs"), Str("${INTERSHEET_REFS}"), ["at", f"{ex}", f"{ey}", "0"], ["hide", "yes"],
                               ["effects", ["font", ["size", "1.27", "1.27"]], ["justify", just]]]])
        sym.append(["instances", ["project", Str(NAME), ["path", Str("/" + root_uuid), ["reference", Str(ref)], ["unit", "1"]]]])
        items.append(sym)

    # PWR_FLAG на силовые цепи, чтобы ERC не ругался на «input power pin not driven»
    libsyms["power:PWR_FLAG"] = resolve("power", "PWR_FLAG")
    fx = 30.0
    fy = grid(y + rowh + 10)
    for net in ("+5V", "+3V3", "GND"):
        uid = str(uuid.uuid4())
        sd = libsyms["power:PWR_FLAG"]
        sym = ["symbol", ["lib_id", Str("power:PWR_FLAG")], ["at", f"{grid(fx)}", f"{fy}", "0"], ["unit", "1"],
               ["exclude_from_sim", "no"], ["in_bom", "no"], ["on_board", "no"], ["dnp", "no"], ["uuid", Str(uid)],
               ["property", Str("Reference"), Str("#FLG_" + net.strip("+")), ["at", f"{grid(fx)}", f"{fy - 5}", "0"], ["hide", "yes"], ["effects", ["font", ["size", "1.27", "1.27"]]]],
               ["property", Str("Value"), Str("PWR_FLAG"), ["at", f"{grid(fx)}", f"{fy - 3}", "0"], ["effects", ["font", ["size", "1.27", "1.27"]]]],
               ["property", Str("Footprint"), Str(""), ["at", f"{grid(fx)}", f"{fy}", "0"], ["hide", "yes"], ["effects", ["font", ["size", "1.27", "1.27"]]]],
               ["property", Str("Datasheet"), Str(""), ["at", f"{grid(fx)}", f"{fy}", "0"], ["hide", "yes"], ["effects", ["font", ["size", "1.27", "1.27"]]]],
               ]
        for num, px, py, ang, ln in pins_of(sd):
            sym.append(["pin", Str(num), ["uuid", Str(str(uuid.uuid4()))]])
            ex, ey = grid(fx + px), grid(fy - py)
            rot = (int(ang) + 180) % 360
            just = "right" if rot in (180, 270) else "left"
            items.append(["global_label", Str(net), ["shape", "bidirectional"], ["at", f"{ex}", f"{ey}", f"{rot}"],
                          ["effects", ["font", ["size", "1.27", "1.27"]], ["justify", just]], ["uuid", Str(str(uuid.uuid4()))]])
        sym.append(["instances", ["project", Str(NAME), ["path", Str("/" + root_uuid), ["reference", Str("#FLG_" + net.strip("+"))], ["unit", "1"]]]])
        items.append(sym)
        fx += 30

    sch = ["kicad_sch", ["version", "20250114"], ["generator", Str("astro-driver-gen")], ["generator_version", Str("10.0")],
           ["uuid", Str(root_uuid)], ["paper", Str("A2")],
           ["title_block", ["title", Str("Драйвер лампы-космонавта: ESP32 + 5 ключей")], ["date", Str("2026-09-09")], ["rev", Str("v1")],
            ["comment", "1", Str("Схема сгенерирована из hardware/design.py, метки = цепи платы")]],
           ["lib_symbols"] + list(libsyms.values())] + items + [["sheet_instances", ["path", Str("/"), ["page", Str("1")]]]]
    path = os.path.join(OUT, NAME + ".kicad_sch")
    with open(path, "w", encoding="utf-8") as f:
        f.write(dump(sch) + "\n")
    pro_path = os.path.join(OUT, NAME + ".kicad_pro")
    pro = {"meta": {"filename": NAME + ".kicad_pro", "version": 3}, "text_variables": {}}
    if os.path.exists(pro_path):            # pcbnew уже записал проект с правилами платы — не терять
        with open(pro_path, encoding="utf-8") as f:
            pro = json.load(f)
    pro["sheets"] = [[root_uuid, "Root"]]
    pro.setdefault("schematic", {"legacy_lib_dir": "", "legacy_lib_list": []})
    with open(pro_path, "w", encoding="utf-8") as f:
        json.dump(pro, f, indent=2)
    print("схема:", path, "символов:", len(libsyms), "элементов:", len(items))


def check_netlist(netfile):
    """Сравнить экспортированный KiCad-нетлист (kicadsexpr) с design.NETS."""
    with open(netfile, encoding="utf-8") as f:
        tree = parse(f.read())[0]
    nets = next(e for e in tree if isinstance(e, list) and e[0] == "nets")
    got = {}
    for net in nets[1:]:
        name = next(a for a in net if isinstance(a, list) and a[0] == "name")[1]
        nodes = frozenset((n[1][1], n[2][1]) for n in net if isinstance(n, list) and n[0] == "node")
        got[name] = nodes
    want = {n: frozenset(p) for n, p in design.NETS.items()}
    # в символе USB-C выводы VBUS совмещены: схема покажет A9/B4 на +5V, на плате их площадка пустая
    ignore = {("J1", "A9"), ("J1", "B4")}
    bad = 0
    for n in sorted(set(want) | set(got)):
        if n.startswith("unconnected-") or n == "VBUS_NC":
            continue
        if want.get(n, frozenset()) - ignore != got.get(n, frozenset()) - ignore:
            bad += 1
            print("РАСХОЖДЕНИЕ", n, "\n  design:", sorted(want.get(n, [])), "\n  схема: ", sorted(got.get(n, [])))
    print("цепей сверено:", len(want), "расхождений:", bad)
    return bad


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "check":
        sys.exit(1 if check_netlist(sys.argv[2]) else 0)
    build()
