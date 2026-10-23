# HP USB AirPrint Server voor Home Assistant OS

Eerste ontwikkelversie (0.1.0), specifiek voor de HP LaserJet P1102w op een
Raspberry Pi 4 met 64-bits Home Assistant OS. Ook een amd64-build is mogelijk.

De app draait CUPS met foo2zjs-z2, een eigen D-Bus en Avahi in één container.
Windows verstuurt opdrachten via IPP; iPhone ontdekt dezelfde wachtrij via
AirPrint/mDNS. CUPS converteert documenten op de Pi en verstuurt ze via USB.
Er is geen cloudservice nodig. Home Assistant Core verwerkt de printbestanden
niet. Deze versie heeft de CUPS-beheerinterface, nog geen dashboard-sensoren.

```text
Windows / iPhone → IPP :631 → CUPS → blijvende wachtrij → foo2zjs → USB → P1102w
                         ↑
                Avahi / AirPrint :5353 UDP
```

## Installatie op je Pi

### Via de GitHub-repository

Open **Instellingen → Apps / Add-ons → Appwinkel / Add-onwinkel → ⋮ →
Repositories**, voeg `https://github.com/creativewizard42/HAPrintserver` toe
en installeer **HP USB AirPrint Server**. Stel daarna `admin_password` in
(minimaal twaalf tekens) en start de app. De eerste installatie bouwt het
image op de Pi en heeft internet nodig. Volg vanaf stap 6 hieronder voor
de beheerinterface en clientinstellingen.

### Handmatig als lokale add-on

1. Kopieer de volledige map `hp_printserver` uit dit project naar
   `/addons/hp_printserver` op de Home Assistant-host. Bijvoorbeeld via de
   officiële Samba share-app met de gedeelde map `addons`, indien ingeschakeld.
   De doelmap bevat rechtstreeks `config.yaml`, `Dockerfile` en `rootfs`.
   Dit is de hostmap `/addons`, niet een map binnen `/config`.
2. Open **Instellingen → Apps / Add-ons → Appwinkel / Add-onwinkel** en kies
   **Controleren op updates** in het menu. Herlaad indien nodig de pagina.
3. Open bij **Local apps / Local add-ons** de app **HP USB AirPrint Server**
   en kies **Installeren**. De eerste installatie bouwt het containerimage op
   de Pi; hierbij is internet nodig voor Debian-pakketten.
4. Stel onder Configuratie `admin_password` in op minimaal twaalf tekens.
   Laat `device_uri` leeg voor automatische USB-detectie.
5. Start de app. Activeer **Start bij opstarten** en eventueel **Watchdog**
   als Home Assistant die optie aanbiedt. De app blijft draaien wanneer de
   printer nog niet beschikbaar is en probeert detectie iedere 15 seconden.
6. Controleer de logs op `Printer gereed`. Open daarna
   `https://<IP-VAN-HOME-ASSISTANT>:631`.

Beheerlogin: **printadmin**, met je ingestelde wachtwoord. CUPS gebruikt een
zelfondertekend TLS-certificaat; controleer dat je je eigen HA-adres opent en
accepteer daarvoor de browsermelding. De beheerinterface gebruikt een eigen
login; je HA-login werkt hier niet. Er is geen ingress in deze versie.

## iPhone

Verbind de iPhone met hetzelfde lokale netwerk als de Pi. Open bijvoorbeeld
een PDF → Deel → Druk af → Kies printer → **HP LaserJet P1102w**.
De naam volgt de optie `printer_description`.

AirPrint vereist multicast/mDNS (UDP 5353) en bereikbaarheid van TCP 631.
Een gastnetwerk met clientisolatie werkt niet. Bij aparte VLAN's is een
gerichte mDNS-gateway plus een firewallregel voor IPP nodig. De app schakelt
geen algemene mDNS-reflector in.

## Windows 11

Open **Instellingen → Bluetooth en apparaten → Printers en scanners →
Apparaat toevoegen**. Kies de gepubliceerde printer als Windows die toont.
Anders: **Handmatig toevoegen → Een gedeelde printer op naam selecteren**:

```text
http://<IP-VAN-HOME-ASSISTANT>:631/printers/HP_P1102w
```

Gebruik waar aangeboden **Microsoft IPP Class Driver**. Wanneer Windows een
legacy driverdialoog opent of installatie weigert: stop daar en noteer de
Windows-versie en foutmelding. Kies niet willekeurig een generieke PCL-driver:
de P1102w begrijpt die uitvoer niet. IPP-driverkeuze en documentonderhandeling
moeten op de echte laptop worden getest. Installeer de printer via de Pi en
gebruik daarbij niet de oude directe wifi-printerwachtrij.

## Configuratie

| Optie | Betekenis |
|---|---|
| `admin_password` | Verplicht eigen beheerwachtwoord, minimaal 12 tekens |
| `printer_name` | Technische wachtrijnaam; standaard `HP_P1102w` |
| `printer_description` | Zichtbare naam voor AirPrint en CUPS |
| `device_uri` | Leeg voor detectie, anders exacte `usb://…`-URI |
| `usb_unidir` | Standaard `true`; schakel het USB-terugleeskanaal uit als compatibiliteitsmodus. `false` herstelt bidirectioneel verkeer. |
| `usb_no_reattach` | Standaard `true`; laat CUPS na een job de kernelprinterdriver usblp niet opnieuw koppelen. Compatibiliteitspoging op basis van P1102; effect op P1102w nog te testen. |
| `debug_logging` | Standaard `false`; tijdelijk `true` voor uitgebreide CUPS-filter- en USB-backendlogs. |

Wijzig `printer_name` niet nadat clients zijn ingericht: er wordt dan een
nieuwe wachtrij gemaakt; een oude wachtrij wordt bewust niet automatisch gewist.
Bij meerdere P1102w-printers is een expliciete URI vereist. Via de CUPS-interface
kun je beschikbare USB-apparaten bekijken.

## Wachtrij en slaapstand

Configuratie, spool en cache staan in `/data`, dus blijven behouden bij
app-herstarts en updates. Neem app-data mee in HA-back-ups: die kunnen ook
wachtende documenten bevatten. Verwijderen van de app kan deze data verwijderen.
Afgehandelde documentbestanden worden niet bewaard; jobhistorie wel.
Er geldt een limiet van 100 jobs en 50 MiB per aanvraag.

Bij tijdelijke apparaatfouten gebruikt CUPS vanaf 0.1.6 `retry-job`, met 60 seconden
interval en retrylimiet 3. Dit treedt in werking wanneer de backend een fout
teruggeeft; een backend die blijft wachten kan niet met deze limiet worden
onderbroken. Daarna kan handmatig ingrijpen nodig zijn;
controleer de jobstatus in CUPS. Een ontbrekende printer hoort de ontvangst van
nieuwe jobs niet te blokkeren zodra de wachtrij eenmaal is aangemaakt.
De app hervat een bewust gepauzeerde wachtrij niet automatisch.

Een normale USB-printopdracht hoort de printer uit Auto-Off te wekken.
Volledig uitgeschakeld, stroomloos, papierstoring of een vastgelopen USB-interface
vereist herstel aan de printer. Deze app schakelt geen slimme stekker en maakt
geen lege afdrukken om de printer wakker te houden.
Een verzonden job is geen bewijs van fysieke afdruk; dien een onduidelijke job
niet blind opnieuw in vanwege mogelijke dubbele afdrukken.

Vanaf 0.1.6 worden IPP-printerstatus, foutredenen, jobstatus en eindstatus gelogd.
Openstaande jobs krijgen na 60, 120 en 240 seconden zonder paginavoortgang een
USB-detectiecontrole voor hun exacte apparaatadres. Dit is diagnostiek, geen
bevestigd weksignaal. Ontwaken wordt via de oorspronkelijke printdata geprobeerd.
De monitor maakt geen nieuwe job, hervat geen handmatige pauzes en reset geen
USB-apparaten. De SSD en Zigbee-radio worden niet aangestuurd. Na drie controles
verschijnt een melding dat controle aan de printer nodig is. Grote documenten
kunnen deze tijdsdrempels ook tijdens normaal verwerken bereiken.

## Opdracht blijft op printing, printer blijft in standby

`printing` betekent dat CUPS de verwerking gestart heeft; het bewijst niet dat
USB-data de printer heeft bereikt. Ook een gestarte USB-backend kan nog wachten
op het apparaat of op filteruitvoer. De voortgangscontrole via USB-detectie is
geen wekcommando. CUPS herprobeert alleen wanneer de backend een fout teruggeeft.

Vanaf 0.1.8 staat `usb_unidir` standaard aan. Dit gebruikt de ondersteunde
CUPS-backendoptie `usb-unidir` om het terugleeskanaal uit te schakelen. Het is een
compatibiliteitspoging voor mogelijke USB-communicatieproblemen, geen bewezen
oplossing voor deze printer in Auto-Off. Het verandert geen USB-apparaten of
hostinstellingen en maakt geen extra printopdracht.

1. Werk de app bij naar 0.1.10 en stel `usb_unidir: true` en tijdelijk
   `debug_logging: true` in. Herstart de app. De startlog toont beide opties.
2. Controleer bestaande jobs in CUPS voordat je een nieuwe opdracht verstuurt.
   Een reeds vastgelopen job krijgt gewijzigde wachtrijdefaults niet gegarandeerd
   mee. Annuleer die zo nodig bewust in CUPS en houd rekening met mogelijke
   gedeeltelijke uitvoer. Verstuur daarna één kleine testpagina.
3. Test eerst terwijl de printer met de eigen knop wakker is gemaakt. Test
   vervolgens dezelfde pagina nadat de printer weer in standby staat. Werkt
   alleen de eerste test, dan is het probleem specifiek aan slaapstand gekoppeld;
   werkt geen van beide, onderzoek dan ook de filterketen en USB-toegang.
4. Bewaar bij mislukken het log vanaf de appstart tot minstens vier minuten na
   de opdracht. Zoek naar filter-exitcodes, `libusb`, `Waiting for printer`,
   `Unable to open` en USB-schrijfmeldingen. Die maken onderscheid tussen
   filterproblemen, apparaatclaim/toegang en het verzenden zelf. Deel geen
   onnodige documentnamen of andere persoonsgegevens uit debuglogs.
5. Zet `debug_logging` na de test weer uit. Als de compatibiliteitsmodus geen
   verbetering geeft, kan `usb_unidir: false` als vergelijking worden getest.

Vanaf 0.1.9 worden HTTP-debugregels uit het app-log gefilterd; opdrachtregels,
backendmeldingen, waarschuwingen en fouten blijven zichtbaar. De monitor toont
ook `USB-opties per job`. Een oude opdracht kan nog een andere of ontbrekende
optie hebben. `USB-busaanwezig` controleert uitsluitend de USB-identiteit en het
serienummer via sysfs; dit bewijst geen toegang tot de interface of ontwaken.
Bij een expliciete `device_uri` wordt geen automatische USB-detectie gestart.

Iedere minuut hoort nu `IPP-monitor actief` te verschijnen. Ontbreekt dat ook
na de opstartmelding van 0.1.8, dan draait de verwachte versie niet of loopt de
monitor vast; alleen afwezigheid van CUPS-logregels bewijst geen standbyfout.
Fysiek ontwaken moet op de Pi worden bevestigd.

## Onderzoek: USB blijft hangen bij de eerste schrijfopdracht

In het ontvangen log van 23 oktober 2026 heeft Job 5 `usb-unidir: true`.
De filterketen levert data; de USB-backend meldt `Read 8192 bytes of print data`,
maar in het beschikbare fragment volgt geen `Wrote ... bytes`. De sysfs-controle
blijft de printer zien. Dit wijst op de USB-verzendfase, maar bewijst niet of de
printer slaapt, intern vastgelopen is of dat de USB-verbinding blokkeert.
`PAGE: 1 1` en `job-impressions-completed: 1` komen uit de verwerking en zijn
hier geen bewijs dat er papier is uitgekomen.

Online bronnen en hun beperkingen:

- [CUPS issue 5310](https://github.com/apple/cups/issues/5310) beschrijft een
  P1102 die na een job niet meer print tot uit-/inschakelen. De bevestigde
  workaround is `usb-no-reattach-default=true`. CUPS heeft hiervoor een regel
  voor **03f0:002a**; onze P1102w heeft **03f0:102a**. Versie 0.1.10 maakt dezelfde
  ondersteunde instelling beschikbaar voor deze wachtrij. Dit is een gerichte
  extrapolatie, geen bevestigde P1102w-fix en geen actie die de printer wakker maakt.
- [cups-filters issue 58](https://github.com/OpenPrinting/cups-filters/issues/58)
  beschrijft dezelfde melding `sending data to printer`. Het oorspronkelijke
  filterprobleem werd in 2018 opgelost; het is geen bewijs van datzelfde defect
  in onze huidige image. Een latere reactie beschrijft vastlopende printerfirmware
  waarbij stroomloos maken nodig was. Dat is een gebruikersmelding, geen
  gegarandeerde diagnose voor dit apparaat.
- [CUPS USB-backend](https://github.com/OpenPrinting/cups/blob/v2.4.2/backend/usb-libusb.c)
  doet na `Read ... bytes` een USB bulk-write met timeout 0 (onbegrensd).
  Daardoor kan een job blijven hangen zonder backendfout en zonder CUPS-retry.
  `usb-no-reattach` beïnvloedt het sluiten van het apparaat na een job; het
  onderbreekt of herstelt niet een al hangende write.

Een aparte, geverifieerde wekprocedure voor dit specifieke model is met dit
onderzoek niet vastgesteld. Een willekeurig USB-reset- of PJL-commando wordt
niet als wekactie toegevoegd.

Testprocedure zodra je bij de printer bent:

1. Annuleer de vastgelopen opdrachten in CUPS (login `printadmin`) en stop de app.
2. Schakel uitsluitend de printer uit, haal zijn stroom en USB los, wacht circa
   30 seconden en sluit hem weer aan. Laat Pi, SSD en Zigbee aangesloten.
3. Installeer 0.1.10 en behoud de exacte `device_uri`. Zet `usb_unidir: true`,
   `usb_no_reattach: true` en tijdelijk `debug_logging: true`. Start de app.
4. Print één kleine testpagina terwijl de printer wakker is. Controleer papier
   én `Wrote ... bytes` / voltooiing in het log. Dien geen tweede job in zolang
   de eerste nog vaststaat.
5. Laat de printer in standby gaan en print dezelfde pagina opnieuw. Werkt
   uitsluitend de eerste test, dan is slaapstand als onderscheidende factor
   vastgesteld. Werkt geen van beide, test de USB-kabel/poort en dezelfde printer
   rechtstreeks vanaf een computer voordat je een wekcommando zoekt.
6. Als alleen de standbytest faalt, maak de printer tijdens de wachtende opdracht
   handmatig wakker en noteer of die opdracht daarna doorgaat. Deel dat resultaat
   met het log vanaf de appstart. Zet debuglogging na de test weer uit.

## Vereiste praktijktest vóór dagelijks gebruik

- Print één PDF vanaf Windows en één vanaf iPhone; controleer schaal en A4.
- Laat Auto-Off ingaan en print opnieuw. Herhaal na een nacht.
- Trek USB los, dien een job in en verbind USB opnieuw: de job moet doorgaan.
- Herstart de app met een wachtende job: deze moet behouden blijven.
- Test papier op / klep open en herstel. Controleer wachtrijstatus en hervatten.
- Herstart HA OS en controleer opnieuw USB-detectie én iPhone-ontdekking.
- Controleer via CUPS de geadverteerde documentformaten en gebruik
  `ipptool`/een AirPrint-client voor protocolvalidatie voordat je de versie
  als stabiel beschouwt. De statische AirPrint-capabilities moeten overeenkomen
  met de werkelijk geïnstalleerde cups-filters.

## Ontwikkelen en controleren

```powershell
python -m unittest discover -s tests -v
```

Op een Linux-machine met Docker (of via de HA OS-installatie):

```sh
docker build -t hp-usb-airprint:0.1.0 hp_printserver
docker run --rm --entrypoint /bin/sh hp-usb-airprint:0.1.0 -c \
  'cupsd -t && test -x /usr/bin/foo2zjs && /usr/lib/cups/driver/foo2zjs list | grep -i p1102w'
```

De meegeleverde GitHub Actions-workflow bouwt het image op Linux en voert
`tests/container_smoke.py` uit: die controleert de CUPS-configuratie, maakt
een testwachtrij en converteert een PDF door de volledige P1102w-filterketen.
Daarbij wordt niets naar een fysieke printer gestuurd. De workflow is lokaal
toegevoegd; hij is hier nog niet uitgevoerd of gepubliceerd.

Deze ontwikkelomgeving heeft geen Docker-engine of toegang tot de Pi/printer.
Unit-tests controleren logica en metadata; containerbuild, echte filters,
USB-permissies, mDNS-samenwerking met HA OS en fysiek ontwaken moeten nog op de
doelomgeving worden gevalideerd. Deze versie is daarom **experimenteel**.

## Technische keuzes en bronnen

- Debian Bookworm voor CUPS 2 en de beschikbare ARM64 foo2zjs-pakketten.
- Host networking voor rechtstreeks bereikbare IPP en mDNS; geen host-D-Bus
  of Supervisor-/HA-API-token nodig. USB wordt via de add-onconfiguratie gedeeld.
- Alleen lokale subnets mogen CUPS bereiken; beheer vereist authenticatie.
  Iedereen in die toegestane netwerken kan printen. Publiceer poort 631 niet
  naar internet. Printinhoud via gewone IPP is niet versleuteld.
- [HA-appconfiguratie](https://developers.home-assistant.io/docs/add-ons/configuration/)
- [HP-handleiding, Auto-Off p. 51](https://h10032.www1.hp.com/ctg/Manual/c04697535.pdf)
- [Debian foo2zjs](https://packages.debian.org/bookworm/printer-driver-foo2zjs)
- [CUPS-configuratie](https://www.cups.org/doc/man-cupsd.conf.html)
