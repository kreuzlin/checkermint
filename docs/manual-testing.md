# Manual testing

Things the automated tests cannot cover, checked by hand in the local
development setup (`docker compose up`, see README).

## Phone upload and live update (#28, #29)

Goal: a photo taken with a phone appears in the draft on the laptop within
about 5 seconds, without reloading the page.

### Prerequisites

- Laptop and phone on the **same Wi-Fi** (guest networks often isolate
  devices from each other).
- The laptop's IP address in that network, on macOS e.g.:

  ```bash
  ipconfig getifaddr en0        # e.g. 192.168.1.23
  ```

- In `.env`, add that IP to `ALLOWED_HOSTS` (keep `DEBUG=true`):

  ```bash
  ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.23
  ```

  Then recreate the web container, because `docker compose up -d` does not
  pick up changes inside `.env`:

  ```bash
  docker compose up -d --force-recreate web
  ```

- On the laptop, open the site **via the IP**, not via `localhost`:
  `http://192.168.1.23:8000`. The QR code contains the address the laptop
  browser uses; with `localhost` the phone would try to reach itself.
- If the phone cannot load `http://192.168.1.23:8000` at all: check that
  the macOS firewall allows incoming connections for Docker
  (System Settings → Network → Firewall → Options).

### Test data (once, in the admin)

1. Log in to `/admin/` as superuser.
2. Create a topic, a task and a version with a **photo requirement** (e.g.
   key `fotos`, 1 to 3 photos), publish the version and tick "Für
   Teilnehmende sichtbar" on the task.
3. Create a participant account (Benutzer → hinzufügen, with profile).

### Steps

1. Laptop: log out of the admin and log in as the participant
   (`/anmelden/`).
2. Open the task under "Aufgaben", click "Lösung erfassen" and then
   "Entwurf speichern". The box "Fotos mit dem Handy" now shows a QR code
   and the text "Fotos vom Handy erscheinen hier automatisch".
3. Phone: scan the QR code with the camera. The page "Fotos hochladen"
   opens without a login.
4. Phone: choose or take a photo and tap "Hochladen". The phone shows
   "1 Datei ist hochgeladen."
5. Laptop: **do not reload**. Within about 5 seconds the photo appears in
   the photo block of the form, with a thumbnail and the file name.

### What else to check

- **No unnecessary swaps:** in the laptop browser's developer tools
  (Network tab), a request to `…/loesung/gespeichert/fotos/?stand=…` runs
  every 5 seconds and answers **204** while nothing changes, and **200**
  once after an upload.
- **Ticked boxes survive:** tick "Entfernen" on a photo, then upload
  another photo from the phone. After the refresh, the box is still ticked.
- **Limit:** upload more photos than allowed (e.g. a fourth one with a
  maximum of 3). The phone shows "Höchstens 3. …", and the laptop shows
  only the allowed photos.
- **iPhone photos (HEIC):** an iPhone photo arrives as JPEG; the thumbnail
  shows it the right way up.
- **Polling stops:** click "Einreichen" on the laptop. The phone page then
  says the draft no longer exists. On the form page that is left open in
  another tab, polling stops after the next request (status **286** in the
  Network tab).
- **Link expiry:** a QR code is valid for 30 minutes. After that, the phone
  page says the link has expired; reloading the form on the laptop shows a
  new code.

### Afterwards

Remove the IP from `ALLOWED_HOSTS` again if you like, and recreate `web`.
