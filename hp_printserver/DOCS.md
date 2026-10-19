# Gebruik

Stel eerst `admin_password` in op minimaal twaalf tekens. Start daarna de app
met de HP P1102w aangesloten via USB. Zie de logs voor automatische detectie.

Beheer: `https://<HA-IP>:631`, gebruiker `printadmin`.
Printadres: `http://<HA-IP>:631/printers/HP_P1102w`.
iPhone: kies **HP LaserJet P1102w** in het AirPrint-printermenu op hetzelfde LAN.

De browser toont bij beheer een waarschuwing voor het zelfondertekende
certificaat. De gebruikersnaam en het wachtwoord zijn afzonderlijk van HA.

Bij `Wacht op HP P1102w` controleer je voeding en kabel. Als de printer als
USB-opslag verschijnt, kan HP Smart Install actief zijn; schakel dat met een
geschikt HP-hulpmiddel uit en probeer opnieuw. Bij een gestopte wachtrij kun
je die als beheerder hervatten in CUPS.

Experimentele versie: valideer Windows, AirPrint en slaapstand op je eigen
apparatuur. Uitgebreide installatie, beperkingen en teststappen staan in de
README van het project. Een herstart bewaart wachtende jobs; het verwijderen
van de app niet noodzakelijk.
