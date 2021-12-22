# GAISA SARGS Hardware

![GAISA SARGS proto image](https://gaisasargs.lv/assets/img/prototipi600.jpg)

GAISA SARGS is an open source air quality monitor DIY kit for kids & teenagers.

It consists of 3 boards:
The main board

Current revision: **02**

Known bugs: **none yet**

Authors: **Skrubis & Zahars Ze**


The project consists of 3 PCBs you need to order:
1) [The main PCB x1 ](https://github.com/open-lv/air-guard/tree/main/hardware/main-pcb) 
2) [The side PCB x2 ](https://github.com/open-lv/air-guard/tree/main/hardware/side-pcb)
3) [The rear PCB x1 ](https://github.com/open-lv/air-guard/tree/main/hardware/rear-pcb)

The PCBs are drawn in Kicad 5.1.x
The schematic of the main board: [airguard_v1.pdf](https://github.com/open-lv/air-guard/blob/main/hardware/main-pcb/airguard_v1.pdf)

All boards are your run of the mill pcbhouse 
(OSH, pcbway, jlcpcb, etc.) standard process compatible. 

Just upload the Gerber ZIP file and choose the options specified below:


Layers: 2

Thicness: 1.6mm

Soldermask color: Blue 
(as intended by the artist Zahars Ze, however we invite you to experiment and show us the results)

Surface finish: RoHS HASL
if used by kids; show us how it looks in ENIG, if you ever make one

The DIY kit BOM can be viewed in the BOM folder, however at this time it is very preliminary in nature. 
Most likely not much will change, but please keep it in mind while viewing it.

**The simple BOM is as follows**:
1) Main PCB - x1
2) Side PCB - x2
3) Rear PCB - x1
4) 19pin 2.54mm female header - x2
5) ESP-32 DevkitC V4 or older version (check pinouts in the main pcb schematic) - x1
6) 4pin 2.54mm female header - x1
7) 5pin 2.54mm female header - x1
8) Winsen MHZ19-C (or -B) - x1
9) 4.7k TH Resistor - x9
10) 2N2222 NPN transistor TO-92 or similar - x4
11) 10mm TH LED Green - 1x
12) 10mm TH LED Red - 1x
13) 10mm TH LED Orange(Yellow) - 1x
14) 3mm TH LED White - 2x
15) 68R TH Resistor - 3x
16) 33R TH Resistor - 2x
17) Buzzer 10mm pin to pin - 1x
18) Standard TH push button 6mm - 1x
19) SSD1306 based I2C OLED 0.96" 128x64px - 1x - check voltage and pinout on the pcb!!

That's it! It's a very simple project electroncis wise, so feel free to experiment, customize or improve it!


This portion of the project is licensed under [CC BY-NC-SA 4.0](hardware/LICENSE).