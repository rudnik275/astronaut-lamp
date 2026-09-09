"""Описание платы драйвера лампы-космонавта: детали и цепи.

Единственный источник правды для генератора KiCad-проекта (build_kicad.py).
Каждая деталь: ref, value, footprint (библиотека KiCad 9), lcsc (код JLCPCB/LCSC для
сборки; None = не монтируется на заводе, паяет Дима), pos (x, y, rot) в мм.
Каждая цепь: имя -> список (ref, pad).
"""

# ---------------------------------------------------------------- детали
# SMD, монтирует JLCPCB (economic PCBA, одна сторона)
PARTS = {
    "U1": dict(value="ESP32-WROOM-32E", fp="astro:ESP32-WROOM-32_body", lcsc="C701341",
               desc="модуль ESP32, 4 МБ флеш; антенна свисает за край платы; посадочное место = библиотечное, courtyard по корпусу"),
    "U2": dict(value="CH340C", fp="Package_SO:SOIC-16_3.9x9.9mm_P1.27mm", lcsc="C84681",
               desc="USB-UART для прошивки, без кварца"),
    "U3": dict(value="AMS1117-3.3", fp="Package_TO_SOT_SMD:SOT-223-3_TabPin2", lcsc="C6186",
               desc="стабилизатор 3.3 В"),
    "J1": dict(value="USB-C 16p", fp="Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", lcsc="C165948",
               desc="питание 5 В и прошивка"),
    "Q1": dict(value="AO3400A", fp="Package_TO_SOT_SMD:SOT-23", lcsc="C20917", desc="ключ R"),
    "Q2": dict(value="AO3400A", fp="Package_TO_SOT_SMD:SOT-23", lcsc="C20917", desc="ключ G"),
    "Q3": dict(value="AO3400A", fp="Package_TO_SOT_SMD:SOT-23", lcsc="C20917", desc="ключ B"),
    "Q4": dict(value="AO3400A", fp="Package_TO_SOT_SMD:SOT-23", lcsc="C20917", desc="ключ мотора"),
    "Q5": dict(value="AO3400A", fp="Package_TO_SOT_SMD:SOT-23", lcsc="C20917", desc="ключ лазера"),
    "Q6": dict(value="S8050", fp="Package_TO_SOT_SMD:SOT-23", lcsc="C2146", desc="автосброс EN"),
    "Q7": dict(value="S8050", fp="Package_TO_SOT_SMD:SOT-23", lcsc="C2146", desc="автосброс IO0"),
    "D1": dict(value="SS14", fp="Diode_SMD:D_SMA", lcsc="C2480", desc="обратный диод мотора"),
    "D2": dict(value="LED red", fp="LED_SMD:LED_0603_1608Metric", lcsc="C2286", desc="индикатор 3.3 В"),
    "R1": dict(value="5.1k", fp="Resistor_SMD:R_0603_1608Metric", lcsc="C23186", desc="CC1"),
    "R2": dict(value="5.1k", fp="Resistor_SMD:R_0603_1608Metric", lcsc="C23186", desc="CC2"),
    "R3": dict(value="10k", fp="Resistor_SMD:R_0603_1608Metric", lcsc="C25804", desc="подтяжка EN"),
    "R4": dict(value="10k", fp="Resistor_SMD:R_0603_1608Metric", lcsc="C25804", desc="подтяжка IO0"),
    "R5": dict(value="10k", fp="Resistor_SMD:R_0603_1608Metric", lcsc="C25804", desc="база Q6 от RTS"),
    "R6": dict(value="10k", fp="Resistor_SMD:R_0603_1608Metric", lcsc="C25804", desc="база Q7 от DTR"),
    "R7": dict(value="1k", fp="Resistor_SMD:R_0603_1608Metric", lcsc="C21190", desc="индикатор"),
    "C2": dict(value="10uF", fp="Capacitor_SMD:C_0805_2012Metric", lcsc="C15850", desc="вход AMS1117"),
    "C3": dict(value="10uF", fp="Capacitor_SMD:C_0805_2012Metric", lcsc="C15850", desc="выход AMS1117"),
    "C4": dict(value="10uF", fp="Capacitor_SMD:C_0805_2012Metric", lcsc="C15850", desc="3.3 В у модуля"),
    "C5": dict(value="100nF", fp="Capacitor_SMD:C_0603_1608Metric", lcsc="C14663", desc="3.3 В у модуля"),
    "C6": dict(value="1uF", fp="Capacitor_SMD:C_0603_1608Metric", lcsc="C15849", desc="EN, задержка сброса"),
    "C7": dict(value="100nF", fp="Capacitor_SMD:C_0603_1608Metric", lcsc="C14663", desc="VCC CH340C"),
    "C8": dict(value="100nF", fp="Capacitor_SMD:C_0603_1608Metric", lcsc="C14663", desc="V3 CH340C"),
    # THT, паяет Дима (в BOM для сборки не входят)
    "C1": dict(value="1000uF/16V", fp="Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", lcsc=None,
               desc="электролит по 5 В, есть в закромах"),
    "RR": dict(value="5R6 2W", fp="Resistor_THT:R_Axial_DIN0414_L11.9mm_D4.5mm_P15.24mm_Horizontal", lcsc=None, desc="балласт R"),
    "RG": dict(value="3R3 2W", fp="Resistor_THT:R_Axial_DIN0414_L11.9mm_D4.5mm_P15.24mm_Horizontal", lcsc=None, desc="балласт G"),
    "RB": dict(value="3R3 2W", fp="Resistor_THT:R_Axial_DIN0414_L11.9mm_D4.5mm_P15.24mm_Horizontal", lcsc=None, desc="балласт B"),
    "RM": dict(value="6R8 2W", fp="Resistor_THT:R_Axial_DIN0414_L11.9mm_D4.5mm_P15.24mm_Horizontal", lcsc=None, desc="мотор (R18 донора)"),
    "RL": dict(value="10R 2W", fp="Resistor_THT:R_Axial_DIN0414_L11.9mm_D4.5mm_P15.24mm_Horizontal", lcsc=None, desc="лазер (R11 донора)"),
    "J2": dict(value="LED V G R B", fp="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", lcsc=None, desc="провода светодиода, порядок как на доноре"),
    "J3": dict(value="MOTOR", fp="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", lcsc=None, desc="1 = ключ, 2 = +5"),
    "J4": dict(value="LASER", fp="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", lcsc=None, desc="1 = +5, 2 = ключ (полярный!)"),
    "J5": dict(value="5V IN", fp="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", lcsc=None, desc="альтернативный вход 5 В от гнезда в стенке: 1 = +5, 2 = GND"),
    "SW1": dict(value="EN", fp="Button_Switch_THT:SW_PUSH_6mm", lcsc=None, desc="сброс, необязательна"),
    "SW2": dict(value="BOOT", fp="Button_Switch_THT:SW_PUSH_6mm", lcsc=None, desc="загрузчик, необязательна"),
    "H1": dict(value="M3", fp="MountingHole:MountingHole_3.2mm_M3", lcsc=None, desc=""),
    "H2": dict(value="M3", fp="MountingHole:MountingHole_3.2mm_M3", lcsc=None, desc=""),
    "H3": dict(value="M3", fp="MountingHole:MountingHole_3.2mm_M3", lcsc=None, desc=""),
    "H4": dict(value="M3", fp="MountingHole:MountingHole_3.2mm_M3", lcsc=None, desc=""),
}

# Пять каналов: (суффикс, GPIO, пад модуля, ключ, gate-резистор, pull-down, балласт, нагрузка)
CHANNELS = [
    ("R", 25, "10", "Q1", "RG1", "RP1", "RR", ("J2", "3")),
    ("G", 26, "11", "Q2", "RG2", "RP2", "RG", ("J2", "2")),
    ("B", 27, "12", "Q3", "RG3", "RP3", "RB", ("J2", "4")),
    ("M", 32, "8",  "Q4", "RG4", "RP4", "RM", ("J3", "1")),
    ("L", 33, "9",  "Q5", "RG5", "RP5", "RL", ("J4", "2")),
]
for _, gpio, _, _, rg, rp, _, _ in CHANNELS:
    PARTS[rg] = dict(value="220R", fp="Resistor_SMD:R_0603_1608Metric", lcsc="C22962", desc=f"затвор GPIO{gpio}")
    PARTS[rp] = dict(value="10k", fp="Resistor_SMD:R_0603_1608Metric", lcsc="C25804", desc=f"pull-down GPIO{gpio}")

# ---------------------------------------------------------------- цепи
# Нумерация падов: ESP32-WROOM-32 по даташиту (1 GND, 2 3V3, 3 EN, 8 IO32, 9 IO33, 10 IO25,
# 11 IO26, 12 IO27, 15 GND, 25 IO0, 34 RXD0, 35 TXD0, 38 GND, 39 термопад).
# SOT-23 AO3400A: 1 G, 2 S, 3 D. SOT-23 S8050: 1 B, 2 E, 3 C. SOT-223 AMS1117: 1 GND, 2 OUT(tab), 3 IN.
# CH340C SOP-16: 1 GND, 2 TXD, 3 RXD, 4 V3, 5 UD+, 6 UD-, 13 DTR#, 14 RTS#, 16 VCC.
# SMA диод: 1 K, 2 A. LED 0603: 1 K, 2 A. CP_Radial: 1 +, 2 -.
# USB-C HRO: пады A1B12/B1A12 GND, A4B9/B4A9 VBUS, A5 CC1, B5 CC2, A6/B6 D+, A7/B7 D-, S1 экран.
NETS = {
    "GND": [("U1", "1"), ("U1", "15"), ("U1", "38"), ("U1", "39"),
            ("U2", "1"), ("U3", "1"),
            ("J1", "A1"), ("J1", "A12"), ("J1", "B1"), ("J1", "B12"), ("J1", "SH"),
            ("R1", "2"), ("R2", "2"), ("C2", "2"), ("C3", "2"), ("C4", "2"), ("C5", "2"),
            ("C6", "2"), ("C7", "2"), ("C8", "2"), ("D2", "1"), ("C1", "2"), ("J5", "2"),
            ("SW1", "2"), ("SW2", "2"),
            ("Q1", "2"), ("Q2", "2"), ("Q3", "2"), ("Q4", "2"), ("Q5", "2"),
            ("RP1", "2"), ("RP2", "2"), ("RP3", "2"), ("RP4", "2"), ("RP5", "2")],
    # VBUS берём с одной сдвоенной площадки A4/B9 (два контакта, 2.5 А по спецификации Type-C);
    # в вилке кабеля все четыре VBUS соединены. Площадка A9/B4 не подключена: между ней и
    # A4/B9 идут D+, D-, CC1, CC2, и перемычка там не помещается.
    "+5V": [("J1", "A4"), ("J1", "B9"), ("U3", "3"), ("C2", "1"), ("C1", "1"), ("J5", "1"),
            ("J2", "1"), ("J3", "2"), ("J4", "1"), ("D1", "1")],
    "+3V3": [("U3", "2"), ("C3", "1"), ("C4", "1"), ("C5", "1"), ("U1", "2"),
             ("U2", "16"), ("U2", "4"), ("C7", "1"), ("C8", "1"),
             ("R3", "1"), ("R4", "1"), ("R7", "1")],
    "EN": [("U1", "3"), ("R3", "2"), ("C6", "1"), ("Q6", "3"), ("SW1", "1")],
    "IO0": [("U1", "25"), ("R4", "2"), ("Q7", "3"), ("SW2", "1")],
    "DTR": [("U2", "13"), ("Q6", "2"), ("R6", "1")],
    "RTS": [("U2", "14"), ("Q7", "2"), ("R5", "1")],
    "Q6B": [("R5", "2"), ("Q6", "1")],
    "Q7B": [("R6", "2"), ("Q7", "1")],
    "U0RXD": [("U1", "34"), ("U2", "2")],
    "U0TXD": [("U1", "35"), ("U2", "3")],
    "USB_DP": [("J1", "A6"), ("J1", "B6"), ("U2", "5")],
    "USB_DM": [("J1", "A7"), ("J1", "B7"), ("U2", "6")],
    "CC1": [("J1", "A5"), ("R1", "1")],
    "CC2": [("J1", "B5"), ("R2", "1")],
    "LED_A": [("R7", "2"), ("D2", "2")],
    "VBUS_NC": [("J1", "A9"), ("J1", "B4")],   # вторая площадка VBUS, намеренно не подключена (см. +5V)
}
for suf, gpio, pad, q, rg, rp, rb, load in CHANNELS:
    NETS[f"GPIO{gpio}"] = [("U1", pad), (rg, "1")]
    NETS[f"GATE_{suf}"] = [(rg, "2"), (rp, "1"), (q, "1")]
    NETS[f"DRAIN_{suf}"] = [(q, "3"), (rb, "1")]
    NETS[f"LOAD_{suf}"] = [(rb, "2"), load]
NETS["LOAD_M"].append(("D1", "2"))   # анод SS14 на моторе, катод на +5

# ---------------------------------------------------------------- плата
BOARD_W, BOARD_H = 60.0, 47.0   # мм; отсек ранца 63 × 52, модуль свисает антенной за верхний край на 3 мм

# Размещение (точка привязки посадочного места, поворот). Система координат KiCad: y вниз,
# начало в левом верхнем углу платы. Габариты посадочных мест взяты из библиотек KiCad 10.
# Слева направо: разъёмы у левого края, выводные балласты (ножка 2 к разъёмам), ключи
# SOT-23 стоком влево, затворные резисторы, колонка EN, модуль ESP32 (антенна вверх),
# справа автосброс IO0; внизу USB-C, CH340C, стабилизатор, кнопки, C1.
_ROWS = [7.7, 12.9, 18.1, 23.3, 28.5]
PLACE = {
    "U1": (46.5, 12.0, 0),
    "U2": (46.0, 29.0, 0), "C7": (50.6, 24.3, 90), "C8": (40.0, 27.0, 0),
    "Q7": (56.0, 25.5, 90), "R6": (56.0, 29.0, 90), "R4": (56.0, 32.5, 90),
    "D2": (27.0, 45.0, 0), "R7": (27.0, 42.6, 0),
    "J1": (46.0, 42.8, 0), "R1": (44.75, 35.9, 90), "R2": (47.75, 35.9, 90),   # CC-резисторы ровно над падами A5/B5
    "U3": (34.0, 38.5, 0), "C2": (38.0, 45.0, 0), "C3": (30.5, 45.0, 0),
    "C4": (35.0, 4.0, 90), "R3": (35.0, 7.5, 90), "C6": (35.0, 10.5, 90),
    "Q6": (35.2, 14.0, 90), "R5": (35.0, 17.5, 90), "C5": (35.0, 20.5, 90),
    "SW2": (16.6, 32.7, 0), "SW1": (16.6, 40.3, 0),
    "D1": (10.0, 33.0, 0),
    "J2": (2.5, 7.5, 0), "J3": (2.5, 19.0, 0), "J4": (2.5, 25.5, 0), "J5": (2.5, 32.0, 0),
    "C1": (7.2, 41.0, 0),
    "H1": (3.0, 2.0, 0), "H2": (56.5, 43.5, 0),
}
for i, (q, rg, rp, rb) in enumerate((("Q1", "RG1", "RP1", "RR"), ("Q2", "RG2", "RP2", "RG"), ("Q3", "RG3", "RP3", "RB"),
                                   ("Q4", "RG4", "RP4", "RM"), ("Q5", "RG5", "RP5", "RL"))):
    y = _ROWS[i]
    PLACE[q] = (26.8, y, 180)
    PLACE[rg] = (32.2, y - 1.1, 0)
    PLACE[rp] = (29.6, y + 1.2, 270)   # GND-пятачок (2) внизу, рядом с истоком ключа: один остров земли на двоих
    PLACE[rb] = (22.0, y, 180)
for h in ("H3", "H4"):
    PARTS.pop(h, None)
for h in ("H1", "H2"):
    PARTS[h]["fp"] = "MountingHole:MountingHole_2.7mm_M2.5"
    PARTS[h]["value"] = "M2.5"
