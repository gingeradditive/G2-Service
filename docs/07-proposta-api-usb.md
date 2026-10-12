# 07 — API: Chiavetta USB

> Contratto **implementato**, da verificare su una macchina vera. Le convenzioni trasversali
> (prefisso `/service`, `camelCase`, modello degli errori, job asincroni) stanno in
> [02 — Architettura](02-architettura.md#convenzioni-comuni-a-tutte-le-api) e non si ripetono qui.

## Perché passa da qui e non da Moonraker

G2-OS monta la chiavetta **in sola lettura su `/media`** (pmount, modulo `61-EnableUSB`).
Fino a prima esisteva anche il symlink `gcodes/media → /media`, così la chiavetta compariva in
Moonraker come una cartella qualsiasi. Era sbagliato in tre modi:

- GingerView offriva rinomina, spostamento, eliminazione e upload dentro un filesystem in sola
  lettura, e ogni operazione falliva;
- una chiavetta vuota e nessuna chiavetta erano indistinguibili (`/media` vuota in entrambi i
  casi), e il mount sopra una cartella già osservata non genera eventi inotify, quindi Moonraker
  non se ne accorgeva comunque;
- Moonraker indicizzava i file della chiavetta (metadati, miniature) leggendoli da USB.

Il symlink non esiste più. La chiavetta non è un posto da cui si stampa: è un posto **da cui si
importa** nella memoria interna, e l'import lo fa questo servizio, che gira come root e può
leggere `/media` direttamente. Il file importato finisce in `gcodes`, dove Moonraker lo vede
comparire e lo indicizza da sé.

## 1. Presenza della chiavetta

| Metodo | Path | Risposta |
|---|---|---|
| GET | `/service/usb` | `{ "mounted": true }` |

`mounted` è `os.path.ismount("/media")`: vero solo se c'è un filesystem montato, anche vuoto.
GingerView lo interroga a intervalli regolari mentre è aperto il file manager — questo servizio
non ha un canale push, e una chiamata che legge un solo `stat` costa niente.

## 2. Contenuto di una cartella della chiavetta

| Metodo | Path | Query | Risposta |
|---|---|---|---|
| GET | `/service/usb/files` | `path` (relativo alla chiavetta, `""` = radice) | vedi sotto |

```json
{
  "path": "lavori/aprile",
  "dirs": [ { "name": "prove" } ],
  "files": [ { "name": "vaso.gcode", "size": 1048576, "modified": "2026-04-02T10:15:00Z" } ]
}
```

- Solo i file **stampabili**: `.gcode`, senza distinguere maiuscole e minuscole. Gli altri non
  compaiono, perché non c'è niente che l'utente possa farci.
- Sono esclusi i nomi nascosti (`.qualcosa`) e le cartelle di sistema che Windows e macOS
  lasciano sulle chiavette (`System Volume Information`, `$RECYCLE.BIN`).
- Cartelle e file sono ordinati alfabeticamente, senza distinguere maiuscole e minuscole.

Errori: `409 USB_NOT_MOUNTED`, `404 NOT_FOUND` (la cartella non esiste), `400 INVALID_INPUT`
(percorso che esce dalla chiavetta), `503 USB_READ_ERROR` (la lettura fallisce, tipicamente
perché la chiavetta è stata tolta a metà).

## 3. Import di un file

| Metodo | Path | Richiesta | Risposta |
|---|---|---|---|
| POST | `/service/usb/import` | `{ "source", "destDir", "onConflict" }` | `202` + job `usb-import` |

- `source`: percorso del file relativo alla chiavetta.
- `destDir`: cartella di destinazione relativa a `gcodes`, `""` = radice. Deve esistere.
- `onConflict`: cosa fare se in `destDir` c'è già un file con lo stesso nome.
  - `fail` (default): **`409 FILE_EXISTS` subito**, senza avviare il job. È il modo in cui il
    client scopre il conflitto e chiede all'utente cosa fare, senza un endpoint in più.
  - `overwrite`: sostituisce il file.
  - `rename`: importa come `nome (1).gcode`, `nome (2).gcode`, … — il primo nome libero.

Il job si segue su `GET /service/jobs/{jobId}`; a buon fine `result` è
`{ "filename": "vaso (1).gcode", "path": "lavori/vaso (1).gcode" }`, con il nome **finale** e il
percorso relativo a `gcodes`.

Esiti negativi del job:
- `USB_READ_ERROR`: la lettura si interrompe, la chiavetta è stata tolta;
- `STORAGE_WRITE_ERROR`: la scrittura nella memoria interna fallisce, tipicamente per spazio
  esaurito. È separato dal precedente perché all'utente si dice una cosa diversa;
- `FILE_EXISTS`: con `fail`, se il file è comparso fra la richiesta e la copia.

Un solo import alla volta: un secondo mentre il primo è in corso è `409 CONFLICT`, come per
tutti i job.

### Come avviene la copia

1. Il file si copia in `printer_data/.g2-import/<id>.part`: stesso filesystem di `gcodes`, ma
   fuori dalle radici di Moonraker. Moonraker non vede mai un file a metà.
2. `fsync`, poi permessi `644` e proprietario uguale a quello di `gcodes` (`pi`): il servizio
   gira come root, e un file di root in `gcodes` non si potrebbe più cancellare da GingerView.
3. `os.replace` sulla destinazione: lo spostamento è atomico, e per Moonraker il file compare
   completo in un colpo solo.
4. Se qualcosa fallisce, il `.part` si cancella.

Il servizio **non** sa se il file da sovrascrivere è quello in stampa: lo sa Moonraker, e
GingerView non offre la sovrascrittura in quel caso.

## Codice

`services/usb/real.py` contiene tutta la logica, ed è filesystem puro. `services/usb/mock.py`
cambia solo il criterio di presenza — la cartella `.devdata/media` esiste — perché su macOS non
c'è un mount da cercare. La cartella si sposta con `G2_SERVICE_MEDIA_DIR`.
