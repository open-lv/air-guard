#badgelife Parts
================

Various resources for building PCBs with SAO and LSAO ports for building badges or badge addons.

 - The SAO connector is the original standardised connector, exposing power and I2C from the host badge to an addon.
 - The LSAO connector is an iteration on the DEFCON SAO port which adds UART (or 2x GPIO), SPI, and the RST signal if implemented, to help with badge programming.
 - The SAO v1.69bis connector is an iteration of the DEFCON SAO port with adds 2x GPIO (or UART) to the original SAO 

Typically voltage is 3.3v on the badge VCC connector on all these ports.

The physical connector is a pin header on a badge, and socket on the add-on. Ideally, the pins should not be pre-soldered, this should be an exercise left to the delegate. It is
recommended to use higher quality and shrouded connectors to prevent orientation issues on LSAO and v1.69bis SAO.

Examples
--------

*SAO*

 - [AND!XOR's reference designs](https://github.com/ANDnXOR/sao-reference-designs)
 - _insert exceptionally long list of badges and addons here_

*LSAO*

 - The original reference badge for LSAO is devec0's [BSidesCBR/Cybernats 2019 "Nopia 1337" badge.](https://github.com/BSidesCbr/2019badge)
 - The best reference badge is filsy's [OzSec 2019 badge](https://github.com/ozseccon/ozseccon2019_badge)

*SAO v1.69bis*

 - _insert growing list of SAO v1.69bis addons and badges here_

Current Resources
-----------------

- `LSAO.lib` - KiCad schematic footprint for LSAO. Includes SAO.
- `badgelife_sao_v169bis.*` - KiCad schematic footprints and library files for SAO v1.69bis, by 

Use either the "Connector_PinSocket_2.54mm:PinSocket_2x05_P2.54mm_Vertical" (for addons) or "Connector_PinHeader_2.54mm:PinHeader_2x05_P2.54mm_Vertical" (for badges) PCB footprint.

TODO
----

Pull requests accepted!

* A custom KiCAD PCB footprint for badge an add-on connectors to add pin definitions to the silkscreen.
* Footprints and PCB layout files for EasyEDA, Eagle, etc. Pick your poison.
* More example schematic and PCBs!

Related
-------
- [SAO v1.69 BIS announcement](https://hackaday.io/project/52950-shitty-add-ons/log/159806-introducing-the-shitty-add-on-v169bis-standard)
- [Shitty Add-Ons Community on Hackaday](https://hackaday.io/project/52950-shitty-add-ons)

Contacts
--------

Feel free to reach out to me (ec0) on Twitter @devec0 for help with any of this.
There are many very knowledgeable people in the community who will also gladly help you. Feel free to PR your name in here as a contact if you're one of them.
