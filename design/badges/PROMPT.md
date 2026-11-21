# How the badge images were made

The six badge images in this folder were created by the maintainer
(kreuzlin) with **ChatGPT** (image generation) and delivered on
2026-11-21. Claude Code did not draw or edit them (brief, section 11); it
only wrote the prompt below and generates the web versions with
`design/generate_assets.py`.

| Original | Badge | Web version (`badges/static/badges/img/`) |
|---|---|---|
| `01_Erste_LED.png` | Erste LED | `erste-led.png` |
| `02_Code_Starter.png` | Code-Starter | `code-starter.png` |
| `03_Greifarm.png` | Greifarm | `greifarm.png` |
| `04_Sensor_Profi.png` | Sensor-Profi | `sensor-profi.png` |
| `05_Konstrukteur.png` | Konstrukteur/in | `konstrukteur.png` |
| `06_Durchhalter.png` | Durchhalter/in | `durchhalter.png` |

All originals: 1024 × 1024 px, PNG with a transparent background, no
metadata. Checked at 40 px on the site's dark background (#020d16): every
symbol stays recognisable.

## Prompt

Claude Code suggested this prompt (in German, as given to ChatGPT) on
2026-11-21. The maintainer used it to create the set; ChatGPT was asked to
show badge 1 first and then make the others in the same style. Follow-up
corrections in the ChatGPT conversation are not recorded here.

To add a badge in the same style, reuse the prompt with a new line in the
list, or ask in the same ChatGPT conversation for one more badge "im exakt
gleichen Stil". Then put the PNG here, run `design/generate_assets.py` and
add a row to the table above.

```text
Du gestaltest ein Set von Abzeichen (Badges) für «Checkermint», die Trainingsplattform eines Robotik-Clubs für Kinder von 7 bis 16 Jahren. Kinder bekommen einen Badge, wenn sie eine bestimmte Aufgabe gelöst haben.

Erstelle für jeden Badge unten ein eigenes Bild. Alle Badges müssen wie ein zusammengehöriges Set aussehen.

Technische Vorgaben (wichtig):
- Quadratisch, 1024 × 1024 px, PNG mit echtem transparentem Hintergrund (kein Schachbrettmuster, keine Hintergrundfläche).
- Das Motiv füllt etwa 85 % der Fläche, mittig, mit etwas Rand.
- Die Badges werden auf der Website nur 40 × 40 px gross angezeigt, auf einem sehr dunklen Petrol-Hintergrund (#020d16). Deshalb:
  - einfache, klare Formen und ein einziges, gut erkennbares Symbol pro Badge
  - kräftige Konturen, keine feinen Linien, keine kleinen Details
  - KEIN Text, keine Buchstaben, keine Zahlen im Bild
  - genug Kontrast zum dunklen Hintergrund (helle Kontur oder heller Rand)

Stil:
- Einheitliche Grundform für alle: ein Sechseck-Abzeichen (wie ein Schild/Emblem), flach und modern, leicht leuchtend («Glow»), technisch, im Stil eines Hackathons.
- Farben aus dem Checkermint-Logo:
  - Mint: #a6fff9, #76fff5, #36f4e4, #00dcad
  - Petrol (dunkel): #031b23, #072a33, #0a3640
  - Eisweiss: #f5ffff
  Pro Badge darf eine zusätzliche Akzentfarbe vorkommen, sparsam eingesetzt.
- Freundlich und motivierend für Kinder, aber nicht kindisch.
- Keine Menschen, keine Gesichter von Kindern, keine Fotos.
- Keine Logos, Figuren oder Stile bekannter Marken, Spiele oder Filme.

Die Badges (Name – Symbol in der Mitte):
1. Erste LED – eine leuchtende Leuchtdiode
2. Code-Starter – spitze Klammern </> oder ein Terminal-Fenster
3. Greifarm – ein einfacher Roboter-Greifarm
4. Sensor-Profi – ein Ultraschall-Sensor mit Signalwellen
5. Konstrukteur/in – ein Zahnrad mit Schraubenschlüssel
6. Durchhalter/in – ein Roboter, der eine Flagge auf einen Gipfel steckt

Liefere jedes Badge als einzelnes PNG. Zeig mir zuerst Badge 1. Wenn es mir gefällt, erstellst du die anderen im exakt gleichen Stil, mit gleicher Grundform, Strichstärke und Leuchtwirkung.
```
