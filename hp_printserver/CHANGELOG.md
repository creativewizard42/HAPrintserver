# 0.1.6

- IPP-printer- en jobstatus met foutredenen, voortgangscontroles na 60/120/240 seconden en USB-bereikbaarheid van uitsluitend de geconfigureerde printer.
- CUPS herprobeert gemelde backendfouten met 60 seconden interval en limiet 3.
- Log voltooiing als CUPS-status, zonder onbevestigd fysiek ontwaken als succes te melden.
- Geen dubbele jobindiening, USB-resets of automatisch hervatten van vastgehouden jobs.

# 0.1.5

- Log printerstatus en openstaande jobs bij wijzigingen, ook na het aanmaken van de wachtrij.
- CUPS-logniveau info voor afdrukverwerking en backendstatus.
- Herstel lp-groepstoegang op de persistente spoolmap zonder bestaande jobbestanden te wijzigen.

# 0.1.4

- Herken ook de USB-modelnaam "HP LaserJet Professional P 1102w" met een spatie tussen P en 1102w.

# 0.1.3

- Herstel schrijfrechten van de blijvende CUPS-cache, ook bij bestaande installaties.
- Detectie vereist HP als fabrikant en P1102w als model; andere apparaten en serienummers worden niet als model geselecteerd.
- Log USB-apparaten bij ontbrekende printerdetectie, bij opstart en iedere vijf minuten.
- Beperk AirPrint-publicatie tot fysieke netwerkinterfaces indien beschikbaar.

# 0.1.2

- Webinterface-URL gecorrigeerd naar het verplichte Home Assistant-poortsjabloon; dit voorkomt dat Supervisor de appconfiguratie afwijst.

# 0.1.1

- Appmarkering gewijzigd naar stable, zodat de app zonder experimentele-appfilter zichtbaar is.
- Printerwerking en AirPrint moeten nog op de doelapparatuur worden getest.

# 0.1.0

- Eerste experimentele versie voor HA OS op aarch64 en amd64.
- CUPS met P1102w foo2zjs-driver en automatische USB-detectie.
- AirPrint/mDNS-publicatie en IPP voor Windows.
- Persistente wachtrij en beheer via TLS met eigen wachtwoord.
