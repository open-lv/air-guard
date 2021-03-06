# Air Guard 💨

[![Join the chat at https://gitter.im/open-lv/air-guard](https://badges.gitter.im/open-lv/air-guard.svg)](https://gitter.im/open-lv/air-guard)

Air Guard is a do-it-yourself electronics kit for building an **air quality monitor** for your school, home or office.

## Project Goals

Create a kit of electronics components, software tools and instructions for kids (and anyone) to create air quality monitors for their living spaces using affordable and readily available components and friendly programming tools.

## Design Goals

- Use existing electronics modules for all components to ensure the parts are available and affordable.

- Build on the experience of other electronics platforms such as [micro:bit](https://microbit.org), [M5Stack](https://m5stack.com), [MicroPython](https://micropython.org), [ESPHome](https://esphome.io) which provide user-friendly tools and concepts for exploring the hardware and software features.

- Allow space for customization and creative expression to encourage use and ownership of the devices.

- Let users experience quick wins early to encourage continued exploration.

- Design for groups of people building the kit and splitting responsibilities.

## Technical Design

- Rely on permanent power supply over USB to avoid limiting the available sensor components (due to their power consumption) and to encourage creative expression in software through the use of LEDs, buzzers and displays. See [issue #4](https://github.com/open-lv/air-guard/issues/4) for the discussion around energy usage.

- Use [MicroPython](https://micropython.org) as the software platform due to the available tooling and accessible programming environments. See [issue #6](https://github.com/open-lv/air-guard/issues/6) for discussion.

- Use ESP32 based microcontrollers due to extensive support for MicroPython and the selected sensor components, and affordable development kits. See [issue #7](https://github.com/open-lv/air-guard/issues/7) for the suggested bill of materials.


## Contribute

Join our [chat on Gitter](https://gitter.im/open-lv/air-guard) to discuss ways to contribute. Issues and pull requests are always welcome!

## Credits

Created [by contributors](https://github.com/open-lv/air-pilot/graphs/contributors).

## License

This is an open source project where the [software](software) and [documentation](docs) are licensed under [MIT](LICENSE) while [the hardware](hardware) is licensed under [CC BY-NC-SA 4.0](hardware/LICENSE).