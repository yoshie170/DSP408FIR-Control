# DSP408FIR Control

[English](README.en.md) · Polski · [GitHub](https://github.com/yoshie170/DSP408FIR-Control)

**Wersja 0.9.1** · [Pobierz](https://github.com/yoshie170/DSP408FIR-Control/releases/latest) · [Zmiany w wydaniach](CHANGELOG.md)

**DSP408FIR Control** to niezależny edytor procesora **t.racks FIR DSP 408**
dla Windows i macOS. Pozwala sterować kanałami wejściowymi i wyjściowymi,
konfigurować PEQ, crossover, delay, dynamikę i FIR oraz zarządzać presetami
i kopiami zapasowymi. Konfiguracje można również przygotowywać i zapisywać
offline, bez podłączonego urządzenia.

| System | Pobierz wersję 0.9.1 |
| --- | --- |
| Windows 10/11, 64-bit | [Instalator Windows (.exe)](https://github.com/yoshie170/DSP408FIR-Control/releases/download/0.9.1/DSP408FIR-Control-0.9.1-Setup-win.exe) |
| macOS 14.4+, Apple Silicon | [Wersja macOS (.dmg)](https://github.com/yoshie170/DSP408FIR-Control/releases/download/0.9.1/DSP408FIR-Control-0.9.1-macOS-arm64.dmg) |

Gotowe pakiety zawierają środowisko uruchomieniowe — nie trzeba instalować
Pythona ani bibliotek. **USB HID i Ethernet są obsługiwane zarówno na Windowsie,
jak i macOS.** Wariant dla komputerów Mac z procesorem Intel jest planowany.

Aplikacja jest przeznaczona dla **FIR DSP 408 z firmware 1.15/1.15P**.
To niezależny projekt, niepowiązany oficjalnie z producentem urządzenia.

Copyright © 2026 Łukasz Białas · [gremium.tech](https://gremium.tech)

## Spis treści

- [Uruchomienie](#uruchomienie)
- [Połączenie z procesorem](#połączenie-z-procesorem)
- [Co znajduje się w interfejsie](#co-znajduje-się-w-interfejsie)
- [Linkowanie kanałów](#linkowanie-kanałów)
- [Konfiguracje, presety i backup](#konfiguracje-presety-i-backup)
- [FIR](#fir)
- [Ustawienia i pomiary](#ustawienia-i-pomiary)
- [Informacje o programie i licencje](#informacje-o-programie-i-licencje)
- [Problemy i ograniczenia](#problemy-i-ograniczenia)
- [O projekcie](#o-projekcie)

## Uruchomienie

### Z instalatora Windows

Pobierz instalator Windows z tabeli powyżej i uruchom plik `.exe`.

Domyślny katalog instalacji to `C:\Program Files\DSP408FIR Control`.
Kreator pozwala wybrać instalację dla wszystkich lub bieżącego użytkownika
oraz utworzyć skrót na pulpicie.

Jeśli program jest już zainstalowany, wybierz **Aktualizuj**, **Zainstaluj drugą
niezależną kopię** albo **Odinstaluj**. Aktualizacja zachowuje folder i ustawienia;
wybierz ten sam tryb użytkowników co poprzednio. Druga kopia ma osobne ustawienia,
skróty i dzienniki. Odinstalowanie zachowuje dane użytkownika.

Przed aktualizacją zapisz konfigurację, rozłącz DSP i zamknij aplikację.
Jeśli jest nadal otwarta, instalator poprosi o jej zamknięcie i ponowienie próby.
Szczegóły aktualizacji i niezależnych kopii opisuje
[dokumentacja instalatora](packaging/windows/README.md).

### Z pakietu macOS

1. Pobierz plik `.dmg` dla Apple Silicon.
2. Otwórz go i przeciągnij **DSP408FIR Control** do folderu **Aplikacje**.
3. Uruchom program z folderu **Aplikacje**.

Wersja macOS nie wymaga używania Terminala. Instrukcje uruchamiania ze źródeł
i budowania własnego pakietu są w [dokumentacji macOS](packaging/macos/README.md).

### Z katalogu projektu

Jeśli środowisko `.venv` jest już przygotowane, uruchom **START_DSP408FIR_CONTROL.cmd** albo istniejący skrót **DSP408FIR Control**. Możesz też użyć PowerShella w katalogu projektu:

```powershell
.\.venv\Scripts\python.exe main.py
```

Program zaczyna w trybie **DEMO / OFFLINE**. Nie łączy się sam z DSP i nie wysyła przygotowanych ustawień przy uruchomieniu.

## Połączenie z procesorem

Przed połączeniem zamknij inne edytory obsługujące ten sam DSP. USB i Ethernet są alternatywnymi sposobami połączenia — aplikacja używa jednego transportu naraz.

### USB

1. Podłącz procesor do komputera przez USB.
2. Otwórz **Connection…**, wybierz **USB** i odpowiedni **DSP ID**.
3. Kliknij **Connect** i poczekaj na zakończenie odczytu.
4. Po pojawieniu się gotowości do sterowania możesz edytować ustawienia.

USB służy tutaj także do sterowania procesorem, nie tylko aktualizacji firmware. Aplikacja nie wykonuje aktualizacji firmware.

### Ethernet — bezpośrednio PC–DSP

1. Połącz komputer i DSP kablem Ethernet.
2. W systemowych ustawieniach karty sieciowej ustaw adres komputera w tej samej podsieci co DSP. Przykład: komputer `192.168.1.12`, maska `255.255.255.0`, DSP `192.168.1.101`. Komputer i DSP muszą mieć różne adresy.
3. W **Connection…** wybierz **Ethernet**, wpisz **DSP IP address** i **DSP ID**, a następnie kliknij **Connect**. W dotychczasowych próbach używany był ID `1`.

W aplikacji podajesz adres **procesora**, nie adres karty komputera. Program korzysta z routingu systemu i nie zmienia konfiguracji karty sieciowej. **Save target** zapamiętuje cel połączenia na komputerze; nie zmienia IP ani ID w DSP.

### Tryby połączenia

| Tryb | Co oznacza |
| --- | --- |
| **DEMO / OFFLINE** | Edycja i zapis lokalnej konfiguracji bez komunikacji z DSP. Metery są puste. |
| **Connect / Control** | Odczyt urządzenia i sterowanie jego bieżącą konfiguracją. |
| **Read only** | Odczyt i podgląd bez zmieniania ustawień DSP. |
| **Disconnect** | Rozłączenie aktywnej sesji. Przycisk zastępuje Connect po połączeniu. |

Podłączenie wczytuje stan DSP; nie wgrywa automatycznie wcześniejszego projektu offline. Dłuższe operacje mają okno postępu. Pełny bank FIR jest pobierany dopiero wtedy, gdy wymaga go np. eksport PRS, backup lub operacja na FIR.

## Co znajduje się w interfejsie

Po lewej są cztery **INPUTS**, po prawej osiem **OUTPUTS**. Wybranie kanału otwiera jego ustawienia w środkowej części okna. Widoczne zakładki zależą od tego, czy edytujesz wejście, czy wyjście.

| Widok | Zastosowanie |
| --- | --- |
| **MAIN** | Przegląd wszystkich kanałów: poziomy, Mute, aktywne funkcje i bypassy. |
| **CHANNEL** | Nazwa kanału, gain, Mute, polaryzacja, delay, Link i kopiowanie ustawień. |
| **PEQ** | Edycja pasm na wykresie i faderach, Magnitude/Phase oraz porównanie wielu kanałów. |
| **XOVER** | Crossover wyjść: IIR albo FIR, z podglądem charakterystyk. |
| **DELAY** | Opóźnienia wszystkich kanałów, jednostki ms/m/ft, temperatura otoczenia i opcjonalna korekcja wilgotności/ciśnienia w Advanced. |
| **GATE / COMP** | Bramka i kompresor wejściowy. |
| **LIMIT** | Limiter wyjściowy. |
| **FIR** | Współczynniki FIR wejść: import, nazwa, wykres, bypass i Clear. |
| **ROUTING** | Przypisanie wejść do wyjść i poziomy miksowania. |
| **SETUP** | Analog/AES, generator, hasło, motyw, backup banku i ustawienia urządzenia. |

W **MAIN** lewy klik pola obsługującego bypass przełącza pomijanie funkcji, a prawy otwiera jej edycję. Niebieski oznacza aktywną funkcję, pomarańczowy z **BP** — bypass, wygaszenie — funkcję nieaktywną. FIR wyjściowy edytujesz w XOVER.

Gate, Compressor, Limiter i Delay mają programowe pomijanie: aplikacja zapamiętuje poprzednie ustawienia i chwilowo ustawia wartości pomijające działanie. Kolejny klik przywraca ustawienia. Ręczna edycja danej funkcji usuwa zapamiętany bypass. Ta pamięć obowiązuje tylko w bieżącej sesji.

Przydatne skróty obsługi:

- Dwuklik fadera gain przywraca **0,0 dB**, a rolka zmienia gain o **0,1 dB**.
- W PEQ przeciąganie punktu zmienia częstotliwość i gain; rolka zmienia szerokość filtra. Dwuklik punktu zeruje jego gain.
- **Compare** pozwala wybrać kilka kanałów. **Include XOVER** na wyjściu pokazuje wpływ crossovera na sumaryczną krzywą; wyłączenie tej opcji zmienia tylko podgląd.
- Skala Magnitude PEQ wynosi **−12…+12 dB**. Charakterystyka crossovera może schodzić poza obszar wykresu. W Phase punkty gain mają osobną skalę dB.
- **Copy…** kopiuje wybrane sekcje do wskazanych kanałów tej samej grupy IN lub OUT.
- **Mute ALL / Unmute ALL** pod OUTPUTS dotyczy wszystkich ośmiu wyjść.

## Linkowanie kanałów

W **CHANNEL → Link channels…** wybierz członków grupy, sprawdź **Review…** i zatwierdź **Apply Link**. Wybrany kanał zawsze należy do grupy i nie jest pokazywany wśród przełączników — wybierasz tylko pozostałych członków. Możesz tworzyć osobne grupy wejściowe i wyjściowe; nie można połączyć IN z OUT.

Przy dołączaniu kanału ustawienia i FIR są kopiowane z członka o **najniższym numerze**. Potem edycja dowolnego członka obejmuje wspólne parametry grupy: gain, Mute, polaryzację, delay, PEQ i właściwą dynamikę/crossover. Import i Clear FIR także uwzględniają grupę.

**Niezależne pozostają nazwy kanałów oraz routing/mix wyjść.** Nazwa FIR jest kopiowana przy dołączeniu, ale późniejsze jej zmiany dotyczą danego kanału. Klamra, plakietka i obramowania kart mają kolor swojej grupy. W MAIN ten sam kolor pojawia się jako cienki znacznik i delikatna obwódka wiersza; po najechaniu na nazwę zobaczysz członków grupy. Krzyżujące się grupy korzystają z osobnych torów klamry.

Aby odłączyć kanał, zostaw w wyborze tylko jego samego. Rozłączenie nie przywraca dawnych ustawień. Ten sam sposób tworzenia grup działa offline i przy połączonym DSP; grupy można zachować w pliku konfiguracji.

## Konfiguracje, presety i backup

To trzy różne operacje:

| Operacja | Gdzie zapisuje dane | Kiedy jej używać |
| --- | --- | --- |
| **Save config…** | Plik na komputerze lub pendrivie | Przenoszenie jednej konfiguracji i przygotowanie projektu offline. |
| **Store preset…** | Wybrany slot P01–P19 w DSP | Zachowanie bieżących ustawień jako preset urządzenia. |
| **SETUP → Back up…** | Plik `.dspbank` | Kopia całego banku zapisanych presetów oraz bieżącej konfiguracji. |

### Pliki konfiguracji

- **`.prs`** — format oryginalnego edytora, z parametrami i współczynnikami FIR. Po połączeniu **Save config…** może pobrać pełny FIR przed eksportem. **Load config…** pokazuje zmiany i wymaga potwierdzenia zastosowania pliku w DSP.
- **`.json`** — lokalny format aplikacji, przydatny do pracy offline. Zapisuje dane obecne w modelu aplikacji; snapshot wykonany po podłączeniu nie zastępuje pełnego eksportu PRS z odczytanym FIR. Bezpośredni import do DSP korzysta z PRS.
- **`.dspbank`** — archiwum banku presetów. Nie służy do zwykłego otwierania jednej konfiguracji.

**Przygotowanie ustawień wcześniej:** otwórz PRS offline, ustaw parametry i grupy, zapisz PRS na komputerze lub pendrivie. Na miejscu połącz się z DSP, wybierz Load config…, sprawdź zmiany i zatwierdź import. Jeśli chcesz zachować konfigurację w slocie procesora, wykonaj potem Store preset….

Zapis PRS offline wymaga oryginalnego szablonu załadowanego z plikiem. Pozwala to zachować nieznane pola formatu. Nowy projekt bez takiego szablonu zapiszesz jako JSON. Lokalne sloty Store w DEMO są pamięcią sesji — do zachowania projektu po zamknięciu programu użyj **Save config…**.

### Presety w DSP i kopia banku

Wybierz preset na liście, a następnie użyj **Load preset…**, aby go przywołać, lub **Store preset…**, aby zapisać bieżące ustawienia. Operacje wymagają potwierdzenia; samo zaznaczenie pozycji na liście nie ładuje presetu.

W **SETUP → PRESET BANK BACKUP** dostępne są:

- **Back up…** — kopia zapisanych P01–P19 i bieżącej konfiguracji z FIR, bez przełączania presetów.
- **Extract backup…** — rozpakowanie archiwum offline do osobnych PRS i surowych odczytów.
- **Restore bank…** — przywrócenie zapisanych slotów z archiwum v2; przed zapisem powstaje kopia obecnego banku. Bieżąca konfiguracja pozostaje bez zmian.

Starszy backup v1 można rozpakować, ale do zbiorczego przywracania potrzebny jest v2. Przywracanie banku nie jest atomowe: po przerwaniu część slotów może być już zmieniona. Zachowaj połączenie do zakończenia operacji.

## FIR

**Wejścia IN A–D:** import CSV/TXT do **512 współczynników na wejście**. Bypass i Clear są odrębnymi operacjami: bypass pomija filtr, zachowując dane, a Clear usuwa jego współczynniki.

**Wyjścia OUT 1–8:** w **XOVER** wybierz **FIR**, ustaw typ filtra, częstotliwości, okno i liczbę taps, potem użyj **Apply crossover…**. To projekt crossovera generowanego przez DSP. Dostępne są BYPASS, LOW PASS, HIGH PASS i BAND PASS; długości 256–1024 taps co 32. Typ określa, które suwaki HPF/LPF są dostępne.

Wspólny budżet aktywnych filtrów FIR wynosi **4096 taps**. Operacje na współczynnikach mogą wymagać pełnego odczytu, czasowego Mute i sprawdzenia danych po zapisie. Zmiana grupy Link używa natywnej kopii w DSP i nie wykonuje pełnego skanowania FIR.

## Ustawienia i pomiary

W **SETUP** znajdziesz:

- **INPUT SOURCE · A–B** — przełączenie wejść A–B między Analog i AES; wejścia C–D pozostają analogowe. Nagłówek pokazuje krótkie Input Analog / AES / EBU; zakres A–B jest opisany w SETUP.
- **SIGNAL GENERATOR** — szum różowy, biały lub sinus. To ustawienie globalne, oddzielne od wyboru Analog/AES. Stan generatora pokazuje ostatni wybór zastosowany w sesji, ponieważ jego bieżącego trybu nie odczytujemy z urządzenia.
- **Warunki otoczenia w DELAY** — temperatura jest widoczna od razu: domyślnie 20 °C, zakres −40…60 °C. W **Advanced** można opcjonalnie włączyć wilgotność i ciśnienie (propozycje: 50% RH i 1013,25 hPa). Bez korekcji zachowany przelicznik producenta 343,5 m/s przy 20 °C. Włączona korekcja Cramera obejmuje 0–30 °C oraz lokalne bezwzględne ciśnienie 760–1020 hPa; poza zakresem temperatury widnieje **estimate** i działa dotychczasowe przybliżenie. Zmiana warunków zachowuje ms i ustawienia DSP; przelicza metry/stopy. Nowa ręcznie wpisana odległość korzysta z aktualnych warunków. Preferencje są zapamiętywane lokalnie.
- **PASSWORD / LOCK** — blokada procesora i odblokowanie istniejącym hasłem. Przy odblokowaniu wybierz **Permanent** (odblokuj tę sesję, zachowaj hasło na kolejne połączenia) albo **One Time** (odblokuj i usuń zapisaną blokadę). Są to oryginalne nazwy trybów producenta — „Permanent” oznacza trwałość ochrony. Offline ma osobną blokadę edycji w sesji: odłączenie zablokowanego DSP pozwala przygotowywać pliki, a ponowne połączenie nadal wymaga odblokowania procesora. Hasło nie jest zapisywane w konfiguracjach ani dziennikach aplikacji.
- **APPEARANCE** — motyw Dark/Light i przełącznik **Dynamics IN / OUT / Gain Reduction**.
- **Processor IP / ID…** — odczyt ustawień i zmiana IP DSP przez USB, po potwierdzeniu. Numer urządzenia zmienia się na panelu DSP; pole ID w Connection wybiera tylko cel połączenia.

**VU refresh** w Connection ustawia nominalny odstęp odpytywania na 100 lub 300 ms dla obu transportów. Długie operacje mogą zatrzymać metery. Poziomy kanałów, sygnalizacja aktywności COMP/LIM i DSP usage pochodzą z odczytów procesora.

Wskaźniki dynamiki **IN, OUT, Gain Reduction i ruchoma kropka** są obliczane z poziomu kanału i statycznej charakterystyki. Nie są osobnymi pomiarami audio pre/post. Wyjaśnienie oraz możliwość ich ukrycia znajdują się w SETUP. Offline nie ma symulowanych poziomów ani aktywności. RTA nie jest częścią aplikacji.

## Informacje o programie i licencje

Menu **Help** zawiera **About**, **Open Source Licenses**, **Changelog**,
**Copy Diagnostics**, **Report an Issue (GitHub)** i aktywny link **gremium.tech**.
About pokazuje ikonę, wersję, numer buildu, autora, technologie oraz aktywne linki
do strony autora i projektu. Licencje i
changelog można przeczytać bez internetu, także w wersji zainstalowanej.

Autorski kod aplikacji udostępniono na [licencji MIT](LICENSE).
Copyright © 2026 Łukasz Białas · [gremium.tech](https://gremium.tech).
Biblioteki, w tym PySide6/Qt, zachowują własne warunki; pełne teksty są w Help
oraz `dsp408/assets/licenses/`. [Informacje o składnikach](THIRD_PARTY_NOTICES.md).
Instalator wyświetla informację o autorze i ekran akceptacji licencji MIT.

**Copy Diagnostics** kopiuje do schowka wersje aplikacji i bibliotek, system
operacyjny oraz podstawowy stan połączenia: USB/Ethernet, Control/Read only,
blokadę i okres odpytywania VU. Nie kopiuje IP, MAC, numerów seryjnych, haseł,
nazw konfiguracji/kanałów, plików ani ścieżek. Niczego automatycznie nie wysyła.
**Report an Issue** otwiera formularz GitHuba; użytkownik sam opisuje problem
i decyduje, czy wkleić diagnostykę. Do wysłania zgłoszenia potrzebne jest konto
na GitHubie.

Przy normalnym uruchomieniu pojawia się krótkie angielskie ostrzeżenie o ryzyku
uszkodzenia sprzętu przez nieprawidłowe ustawienia DSP. **Don't show again**
zapamiętuje wybór lokalnie, osobno dla każdej instalacji. W **About → Safety
notice…** można przeczytać ostrzeżenie ponownie i zmienić ten wybór.

Jest to niezależne oprogramowanie dla t.racks FIR DSP 408, oficjalnie
niepowiązane z producentem urządzenia, przez niego niezatwierdzone ani niewspierane.

## Problemy i ograniczenia

| Objaw | Co sprawdzić |
| --- | --- |
| **Connection failed** | Zamknij drugi edytor; sprawdź kabel, transport, DSP ID i przy Ethernet adresy sieciowe. Szczegóły są w Connection. |
| DSP jest zablokowany | Połącz się i użyj **SETUP → Unlock…** z istniejącym hasłem. |
| Nie można edytować parametrów | Sprawdź Read only, blokadę oraz trwającą operację odczytu/zapisu. |
| Pierwszy backup lub eksport FIR trwa długo | Wymagany jest pełny odczyt danych, a nie sam podgląd startowy. |
| Nie można zapisać nowego projektu jako PRS | Zacznij od załadowania oryginalnego PRS albo zapisz projekt jako JSON. |

Zalecane jest bezpośrednie połączenie Ethernet komputer–DSP; działanie przez
router lub Wi-Fi wymaga dalszej weryfikacji. Wersja macOS obsługuje komputery
Apple Silicon; wariant dla komputerów Mac z procesorem Intel jest planowany.
Aktualizacje aplikacji instaluje się ręcznie z sekcji Releases.

Więcej wskazówek znajdziesz w [rozwiązywaniu problemów](docs/TROUBLESHOOTING.md).

## O projekcie

Autor: **Łukasz Białas** · [gremium.tech](https://gremium.tech).
Copyright © 2026 Łukasz Białas. Autorski kod ma [licencję MIT](LICENSE).
Biblioteki zachowują własne licencje opisane w
[THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md) i dostępne w menu Help.

Ustawienia zainstalowanej wersji Windows są w
`%LOCALAPPDATA%\gremium.tech\DSP408 Control`, a wersji macOS w
`~/Library/Application Support/gremium.tech/DSP408FIR Control`.
Konfiguracje PRS/JSON i kopie DSPBANK zapisujesz w wybranym przez siebie folderze.

[Pobierz aplikację](https://github.com/yoshie170/DSP408FIR-Control/releases/latest)
· [Zgłoś problem](https://github.com/yoshie170/DSP408FIR-Control/issues)
