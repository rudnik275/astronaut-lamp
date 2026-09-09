#!/bin/sh
# Полный цикл: плата → схема → проверки → трассировка → заливка → DRC → выгрузка.
# Использование: sh run.sh [build|check|route|finish|export|all]
set -e
cd "$(dirname "$0")"
KAPP="$HOME/Applications/KiCad/KiCad.app/Contents"
PY="$KAPP/Frameworks/Python.framework/Versions/Current/bin/python3"
CLI="$KAPP/MacOS/kicad-cli"
JAVA=/opt/homebrew/opt/openjdk/bin/java
FR="${FREEROUTING_JAR:-$HOME/.claude/jobs/eb17a63c/tmp/freerouting.jar}"
step="${1:-all}"

drc_summary() {
  python3 - "$1" <<'PYEOF'
import json, sys, collections
d = json.load(open(sys.argv[1]))
c = collections.Counter(v['type'] for v in d['violations'])
print('DRC:', dict(c), '| unconnected:', len(d.get('unconnected_items', [])))
for u in d.get('unconnected_items', [])[:12]:
    print('  НЕ СОЕДИНЕНО:', ' | '.join(f"{i['description'][:55]} @({i['pos']['x']:.1f},{i['pos']['y']:.1f})" for i in u['items']))
for v in d['violations']:
    if v['type'] in ('silk_overlap', 'silk_over_copper', 'text_height', 'lib_footprint_mismatch', 'lib_footprint_issues'):
        continue
    its = ' | '.join(i['description'] for i in v['items'])
    p = v['items'][0]['pos']
    print(' ', v['type'], round(p['x'], 1), round(p['y'], 1), its[:140])
PYEOF
}

if [ "$step" = build ] || [ "$step" = all ]; then
  "$PY" build_kicad.py build 2>&1 | grep -v 'assert'
  python3 build_schematic.py
fi
if [ "$step" = check ] || [ "$step" = build ] || [ "$step" = all ]; then
  "$CLI" sch export netlist --format kicadsexpr -o out/sch.net out/astro-driver.kicad_sch >/dev/null
  python3 build_schematic.py check out/sch.net
  "$CLI" sch erc --format json --severity-all -o out/erc.json out/astro-driver.kicad_sch >/dev/null || true
  python3 -c "
import json, collections
d = json.load(open('out/erc.json'))
c = collections.Counter(v['type'] for s in d['sheets'] for v in s['violations'])
print('ERC:', dict(c))
for s in d['sheets']:
    for v in s['violations']:
        if v['type'] not in ('lib_symbol_issues','footprint_link_issues','lib_symbol_mismatch'):
            print(' ', v['type'], v['description'][:100], [i['description'][:60] for i in v['items']][:2])
" | head -30
  "$CLI" pcb drc --format json --severity-all -o out/drc.json out/astro-driver.kicad_pcb >/dev/null || true
  drc_summary out/drc.json | head -40
fi
if [ "$step" = route ] || [ "$step" = all ]; then
  rm -f out/astro-driver.ses
  "$JAVA" -Djava.awt.headless=true -jar "$FR" -de out/astro-driver.dsn -do out/astro-driver.ses -mp 100 -mt 6 2>&1 | grep -E 'Auto-routing stage completed|Optimization stage completed|Successfully saved' | tail -3
fi
if [ "$step" = finish ] || [ "$step" = all ]; then
  "$PY" build_kicad.py finish 2>&1 | grep -v assert
  "$CLI" pcb drc --format json --severity-all -o out/drc-routed.json out/astro-driver.kicad_pcb >/dev/null || true
  drc_summary out/drc-routed.json | head -40
fi
if [ "$step" = export ] || [ "$step" = all ]; then
  rm -rf out/gerbers && mkdir -p out/gerbers
  "$CLI" pcb export gerbers -o out/gerbers/ --layers F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts --subtract-soldermask --no-x2 out/astro-driver.kicad_pcb >/dev/null
  "$CLI" pcb export drill -o out/gerbers/ --format excellon --excellon-units mm --generate-map --map-format gerberx2 out/astro-driver.kicad_pcb >/dev/null
  (cd out/gerbers && rm -f ../astro-driver-gerbers.zip && zip -q ../astro-driver-gerbers.zip ./*)
  "$CLI" pcb render --side top --width 1600 --height 1200 --zoom 1.0 --quality high -o out/render-top.png out/astro-driver.kicad_pcb >/dev/null
  "$CLI" pcb render --side bottom --width 1600 --height 1200 --zoom 1.0 --quality high -o out/render-bottom.png out/astro-driver.kicad_pcb >/dev/null
  "$CLI" sch export pdf -o out/astro-driver-schematic.pdf out/astro-driver.kicad_sch >/dev/null
  ls -la out/astro-driver-gerbers.zip out/render-top.png out/render-bottom.png out/astro-driver-schematic.pdf out/jlc-bom.csv out/jlc-cpl.csv
fi
