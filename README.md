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
