# DSP408FIR Control - ikony

Copyright © 2026 Łukasz Białas · [gremium.tech](https://gremium.tech).

- `dsp408.svg`: kanoniczny znak używany przy nazwie aplikacji.
- `dsp408-16.png`, `-24`, `-32`, `-48`, `-64`, `-128`, `-256`, `-512`:
  PNG z przezroczystymi narożnikami.
- `dsp408.ico`: jeden plik Windows z rozmiarami16/24/32/48/64/128/256.

Odtwarzanie z katalogu projektu:

```powershell
.\.venv\Scripts\python.exe tools\build_icons.py
```

Nie edytuj PNG/ICO osobno od SVG. Okno aplikacji i przyszły
`DSP408_Control.spec` wskazują ten sam ICO. Samo przygotowanie ikony/spec
nie oznacza, że zbudowano i sprawdzono końcową dystrybucję EXE.

## macOS

The native packaging pipeline renders Retina PNGs up to 1024 px from `dsp408.svg`
and compiles `dsp408.icns` with macOS iconutil. Generated files are build output,
not a separate logo source. See `packaging/macos/README.md` in the repository.
