# GearsBot in Checkermint – Anleitung für Coaches

_Stand: 21. November 2026. Deutsch, weil sie sich an die Coaches richtet
(GearsBot-Brief, Abschnitt 3.6); die übrige Dokumentation ist englisch._

GearsBot ist ein Roboter-Simulator im Browser. Die Kinder programmieren
dort einen virtuellen Roboter mit Blöcken oder Python. Checkermint betreibt
eine eigene Kopie unter **https://sim.checkermint.ch**. Sie lädt nichts von
fremden Servern und speichert keine Daten über die Kinder. Was ein Kind in
GearsBot baut, bleibt in seinem Browser, bis es das Projekt selbst
herunterlädt.

## 1. So funktioniert eine GearsBot-Aufgabe

Eine GearsBot-Aufgabe ist eine normale Checkermint-Aufgabe. Ihre Version
hat zusätzlich einen Abschnitt **«Simulator (GearsBot)»**. Für das Kind
sieht das so aus:

1. Auf der Aufgabenseite klickt es auf **«Im Simulator öffnen»**. GearsBot
   öffnet sich in einem neuen Tab, auf Deutsch, gleich mit der richtigen
   Welt. Es sieht nur die Blöcke, die für diese Aufgabe gedacht sind.
2. Es baut sein Programm im Tab «Blöcke» und startet es im Tab
   «Simulator» mit ▶.
3. Bei einer **Challenge** zeigt GearsBot bei Erfolg «COMPLETED!» und einen
   **Completion code**. Diesen Code trägt das Kind in Checkermint ein.
4. Freiwillig speichert es sein Projekt unter **«Datei» → «Exportiere eine
   zip Datei auf deinen Computer»** und lädt die ZIP-Datei in Checkermint
   hoch.
5. Danach reicht es ein wie bei jeder anderen Aufgabe.

Teams: Mehrere Kinder dürfen eine Challenge zusammen lösen. Jedes reicht
trotzdem selbst ein.

### Die 61 Basic Challenges

Die Challenges aus GearsBot («Basic Challenges») sind am 21. November 2026
als **unveröffentlichte** Aufgaben im Thema **«Code»** angelegt worden. Die
Kinder sehen sie erst, wenn ihr sie freischaltet.

| Gruppe | Aufgaben | Grundpunkte | Ab Level | Sichtbare Blöcke |
|---|---|---|---|---|
| Grundlagen | 5 | 10 | 1 | Fahren und Drehen («Movement») |
| Warten | 2 | 10 | 1 | + Warten |
| Labyrinth | 6 | 15 | 2 | wie Warten |
| Verlies | 7 | 15 | 2 | wie Warten |
| Schleifen | 16 | 20 | 3 | + Wiederholen |
| Bedingungen | 14 | 25 | 4 | + Wenn, Farbe, Vergleiche, Und/Oder, Wahr/Falsch |
| Funktionen | 11 | 30 | 5 | + Variablen und Funktionen |

Die Punkte und Level sind ein Vorschlag. Ihr könnt sie ändern. Die Mission
jeder Challenge steht auf Englisch in der Anleitung, weil GearsBot sie nur
englisch kennt. Die Kategorien «Movement» und «Conditions» heissen auch in
der deutschen Oberfläche englisch.

### Eine Challenge freischalten

1. In der Verwaltung **Aufgaben** öffnen. Mit dem Filter nach Thema «Code»
   findet ihr die Challenges. Ihre Kurznamen beginnen mit `gearsbot-`.
2. Den **Entwurf** (Version 1) öffnen. Hier könnt ihr Titel, Anleitung,
   Punkte und Hinweise anpassen. Hinweise gibt es noch keine, die schreibt
   ihr selbst.
3. **«Vorschau»** anklicken und dort **«Im Simulator öffnen»** ausprobieren:
   Öffnet sich die richtige Welt? Lässt sich die Challenge lösen?
4. **«Veröffentlichen»**. Danach lässt sich die Version nicht mehr ändern.
   Für Änderungen gibt es «Neue Version erstellen».
5. In der Aufgabe **«Für Teilnehmende sichtbar»** anhaken und speichern.

**Vor der ersten Challenge:** GearsBot braucht 3D-Grafik. Probiert es
einmal auf den Geräten des Clubs aus (Laptops, Tablets), bevor die Kinder
damit arbeiten. Bekannt: Bei «Funktionen 4» meldet ein Browser ohne
Bildschirm einen Grafikfehler. Auf einem echten Gerät ist das noch zu
prüfen.

## 2. Eine GearsBot-Lösung bewerten

Die Lösung erscheint wie jede andere in der **Warteschlange**. Auf der
Bewertungsseite seht ihr zusätzlich:

- neben dem Completion code **«✓ Code stimmt»** oder **«✗ Code stimmt
  nicht – erwartet: …»**. Gross- und Kleinschreibung und Leerzeichen spielen
  keine Rolle;
- wenn eine ZIP-Datei hochgeladen wurde: das **Python-Programm** daraus,
  farbig hervorgehoben. GearsBot legt es auch für Block-Programme an. So
  seht ihr die Lösung, ohne GearsBot zu öffnen.

Ihr entscheidet weiterhin selbst. Checkermint nimmt nichts automatisch an.
Der Code ist kein Geheimnis: Er steht öffentlich in GearsBot. Ein richtiger
Code zeigt nur, dass die Challenge geschafft wurde. Wie gut das Programm
ist, seht ihr am Projekt. Ein falscher Code ist oft nur ein Tippfehler. Dann
«Überarbeitung nötig» mit einem kurzen Hinweis.

Checkermint prüft jede ZIP-Datei beim Hochladen: höchstens 50 Dateien, nur
die Dateien, die GearsBot selbst speichert (`gearsBlocks.xml`,
`gearsRobot.json`, `meta.json`, `*.py`), keine Ordner. Eine andere ZIP-Datei
wird mit einer Fehlermeldung abgelehnt.

## 3. Eine eigene GearsBot-Aufgabe mit eigener Welt

Ihr könnt auch eine Aufgabe mit einer anderen Welt anlegen, zum Beispiel
einer Linienfolger-Strecke.

### In GearsBot: die Welt speichern

1. https://sim.checkermint.ch öffnen.
2. Unter **«Welten» → «Select World»** eine Welt wählen und einstellen, oder
   unter **«Welten» → «World Builder»** eine eigene bauen.
3. **«Welten» → «Speichern unter»** speichert die Welt als JSON-Datei.
4. Optional: einen eigenen Roboter unter **«Roboter» →
   «Roboterkonfigurator»** bauen und unter **«Roboter» → «Speichern unter»**
   speichern.

In die Welt gehört nur Aufgabeninhalt, **nie Namen oder Fotos von Kindern**:
Die Dateien sind ohne Anmeldung abrufbar (unter einer nicht erratbaren
Adresse).

### In der Verwaltung: die Aufgabe anlegen

1. Neue Aufgabe anlegen, dann **«Neue Version erstellen»**.
2. Im Entwurf Titel, Anleitung und Punkte ausfüllen.
3. Abschnitt **«Simulator (GearsBot)»**:
   - **Welt-Skripte**: leer lassen (nur die Basic Challenges brauchen
     `challenges_basic`).
   - **Erwarteter Code**: leer lassen. Eigene Welten zeigen keinen
     Completion code.
4. Abschnitt **«Simulator-Dateien»**, je eine Zeile:
   - Art **«Welt»**: die gespeicherte Welt bei «JSON-Datei hochladen»
     wählen. Der Dateiname wird ausgefüllt.
   - Art **«Roboter»** (optional): der gespeicherte Roboter. Ohne Roboter
     nimmt GearsBot den Standard-Roboter.
   - Art **«Blockauswahl»** (optional): welche Blöcke das Kind sieht. Den
     Inhalt könnt ihr aus einer importierten Challenge kopieren oder aus dem
     Beispiel unten nehmen. Ohne Blockauswahl sieht das Kind alle Blöcke.
5. Abschnitt **«Anforderungen»**: was das Kind einreichen soll. Für das
   GearsBot-Projekt eine Anforderung der Art **«Datei»**, Bezeichnung z. B.
   «GearsBot-Projekt (.zip)», Optionen:
   `{"extensions": [".zip"], "gearsbot_project": true}`. Dann prüft
   Checkermint die ZIP-Datei und zeigt das Programm in der Bewertung. Dazu
   passt oft ein Foto oder ein Text («Was hat dein Roboter gemacht?»).
6. **Vorschau** → «Im Simulator öffnen» ausprobieren, dann veröffentlichen
   und die Aufgabe sichtbar machen (wie oben).

### Beispiel Blockauswahl

Nur Fahren, Drehen und Warten (so wie bei «Warten»):

```json
{
  "deny": {"categories": ["Motion", "Motor", "Sensors", "Sound", "Pen",
    "Experimental", "Control", "Logic", "Loops", "Math", "Text", "Lists",
    "Variables", "Functions"]},
  "show": {"categories": ["Movement"], "blocks": ["sleep"]}
}
```

`deny` blendet Kategorien aus, `show` zeigt einzelne wieder an. Die Namen
sind die englischen Namen aus GearsBot, auch in der deutschen Oberfläche.
Weitere Blöcke der importierten Gruppen: `controls_repeat_ext`
(Wiederholen), `tw_color` (Farbe), `logic_compare`, `logic_operation`,
`logic_boolean`; Kategorien `Conditions`, `Variables`, `Functions`.

## 4. Wenn GearsBot aktualisiert wird

Checkermint verwendet eine feste Version von GearsBot. Sie ändert sich
nicht von selbst.

- Am 1. jedes Monats prüft GitHub, ob es eine neuere GearsBot-Version gibt.
  Wenn ja, entsteht ein Pull Request «Update GearsBot to …» mit einer Liste,
  welche Challenges sich geändert haben (Welt, Code, Blockgrenze).
- **Der Maintainer** schaut ihn an und merged ihn. Danach läuft die neue
  Version auf sim.checkermint.ch.
- Haben sich Challenges geändert, führt Claude den Import danach noch
  einmal aus (mit OK des Maintainers). Veröffentlichte Versionen bleiben,
  wie sie sind. Für geänderte Challenges entsteht ein neuer **Entwurf** mit
  der Notiz «GearsBot-Update: Welt oder Code der Challenge geändert.». Ihr
  prüft ihn und veröffentlicht ihn. Kinder, die schon angefangen haben,
  sehen dann den Hinweis auf die neuere Version, wie bei jeder anderen
  Aufgabe.
- Eigene Welten (Abschnitt 3) sind in der Aufgabe gespeichert und ändern
  sich bei einem Update nicht. Läuft eine eigene Welt nach einem Update
  nicht mehr, braucht die Aufgabe eine neue Version.

Technische Einzelheiten: ADR 0019–0022 in `docs/decisions/`,
`sim/gears/README.md`.
