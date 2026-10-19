# Rozwiązywanie problemów / Troubleshooting

## Polski

### Nie można połączyć się z DSP

Zamknij inne edytory korzystające z procesora. W **Connection…** wybierz
właściwe połączenie i DSP ID; przy Ethernet podaj adres procesora.
Sprawdź kabel i zasilanie oraz dokładny komunikat w oknie Connection.
USB i Ethernet są dostępne na Windowsie i macOS.

Przy bezpośrednim Ethernet komputer i DSP muszą mieć różne adresy IPv4
w tej samej podsieci. Przykład: komputer `192.168.1.12`, DSP `192.168.1.101`,
maska `255.255.255.0`. Adres komputera ustawia się w ustawieniach systemu.
Na Macu sprawdź również zgodę na dostęp do sieci lokalnej.
Połączenie przez router lub Wi-Fi wymaga dalszej weryfikacji.

### Parametry są nieaktywne

Sprawdź, czy wybrano **Read only**, czy procesor jest zablokowany lub trwa
operacja odczytu/zapisu. Do odblokowania użyj **SETUP → Unlock…** i własnego
hasła DSP. Blokada edycji offline jest oddzielna od blokady urządzenia.

### Backup lub eksport trwa dłużej niż połączenie

Pełny PRS, backup i operacje FIR mogą wymagać pobrania dodatkowych danych.
Poczekaj na zakończenie paska postępu; nie zmieniaj w tym czasie presetu
na panelu urządzenia ani nie odłączaj DSP.

### Nie można zapisać konfiguracji PRS

Najpierw otwórz plik PRS i użyj go jako podstawy konfiguracji. Nowy projekt
bez szablonu PRS można zapisać jako JSON. Do zachowania projektu na komputerze
używaj **Save config…**; lokalne sloty DEMO są pamięcią bieżącej sesji.

### Instalator zgłasza otwartą aplikację

Zapisz konfigurację, rozłącz DSP, zamknij aktualizowaną kopię programu
i kliknij **Ponów próbę**. Jeśli jest już zamknięta, sprawdź uprawnienia
do folderu instalacji. Instalator sam nie przerywa połączenia z DSP.

### Zgłoszenie problemu

W **Help → Copy Diagnostics** skopiuj informacje o wersji, systemie i stanie
połączenia. Do zgłoszenia dodaj opis kroków i dokładny komunikat błędu.
Przed załączeniem własnych plików sprawdź, czy nie zawierają prywatnych danych.
Zgłoszenia: [GitHub Issues](https://github.com/yoshie170/DSP408FIR-Control/issues).

## English

| Problem | What to check |
| --- | --- |
| Cannot connect | Close other DSP editors. Check power, cable, transport, DSP ID and the full error in Connection. For Ethernet, enter the DSP address. USB and Ethernet are available on Windows and macOS. |
| Direct Ethernet fails | Set distinct computer/DSP IPv4 addresses in the same subnet using system settings. On macOS also check local-network permission. Router/Wi-Fi use requires further verification. |
| Controls are disabled | Check Read only, an ongoing operation or device lock. Use SETUP → Unlock with your own DSP password. Offline editing has a separate lock. |
| Backup/export takes longer | Full PRS, backup and FIR operations may need additional data. Wait for completion and keep the DSP connected. |
| Cannot save PRS | Load an existing PRS as a template first, or save a new project as JSON. Use Save config for persistent files; local DEMO slots are session-local. |
| Installer says the app is open | Save, disconnect and close the selected copy, then Retry. If it is closed, check folder permissions. Setup never forcibly closes a DSP session. |

For a bug report, use **Help → Copy Diagnostics** and include the steps and
exact error. Review attachments for personal information before uploading.
[Report an issue](https://github.com/yoshie170/DSP408FIR-Control/issues).
