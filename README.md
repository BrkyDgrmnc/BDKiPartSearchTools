# BDKiPartSearchTools (`com.berkaydegirmenci.bdkipartsearchtools`)

**BDKiPartSearchTools** (by Berkay Değirmenci) is a KiCad 8 / 9 / 10 plugin to search electronic components from online suppliers (**LCSC / EasyEDA**, **DigiKey**, and **Würth Elektronik** official libraries), preview and import their **Schematic Symbols (`.kicad_sym`)**, **PCB Footprints (`.kicad_mod`)**, and **3D Models (`.step` / `.wrl`)** into categorized libraries, and generate **priced Engineering BOMs** with live stock and part numbers.

> 🇹🇷 **Türkçe Kurulum ve Kullanım Kılavuzu için:** [KURULUM_KILAVUZU.md](./KURULUM_KILAVUZU.md) dosyasına bakabilirsiniz.

## Key Features
* **Direct Schematic & PCB Editor Integration:** Supports both KiCad 9/10 IPC API (`plugin.json` for Schematic Editor, Symbol Editor, PCB Editor, and Project Manager) and `pcbnew.ActionPlugin`.
* **Zero External Dependencies:** Built-in EasyEDA-to-KiCad 10 S-expression converter and 3D STEP/WRL downloader using KiCad's bundled Python and `wxPython`.
* **Category-Based Library Organization:** Automatically organizes components into dedicated category libraries (`Resistors`, `Capacitors`, `ICs_MCUs`, `Diodes_Protection`, `Transistors_FETs`, `Power_Regulators`, `Connectors`, etc.) in either Global or Project scope (`${KIPRJMOD}`).
* **Smart Engineering BOM & Live Pricing:** Extracts placed components from `.kicad_sch` and `.kicad_pcb`, queries live volume-break unit pricing and stock from LCSC and DigiKey API v4, and exports Engineering BOM CSV, JLCPCB PCBA BOM, or DigiKey Bulk Order CSV.

## Building Official KiCad PCM Package
Run with KiCad's Python interpreter:
```bash
python build_pcm_package.py
```
This validates `metadata.json` and `plugins/plugin.json` against KiCad's official JSON schemas and outputs:
* `dist/com.berkaydegirmenci.bdpartsearchtools-1.0.0-pcm.zip` (Installable via *KiCad -> Plugin and Content Manager -> Install from File...*)
* `dist/metadata-submission.json` (Includes `download_sha256`, `download_size`, and `install_size` for submitting to `https://gitlab.com/kicad/addons/metadata`)

## License
MIT License (GPL-compatible).
