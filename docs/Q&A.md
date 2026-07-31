# Q&A

Domande aperte che servono per procedere con lo sviluppo. Rispondi sotto ogni `A:`, anche in
momenti diversi.

**Come funziona il file.** Quando una domanda riceve risposta, viene rimossa da qui e la
decisione finisce nella documentazione (`01`–`03`). L'obiettivo è arrivare ad avere questo
file **vuoto**.

La numerazione **non** viene mai riusata: le nuove domande partono da dove finiscono le
vecchie, così i rimandi `Qn` nella documentazione restano validi nel tempo.

---

**Q1: Va tenuta la convenzione `snake_case` del contratto WiFi già atteso da GingerView, o va
uniformata al `camelCase` del contratto timezone?**
Contesto: i tipi WiFi in GingerView (`WiFiNetwork`, `NetworkStatus`, ...) usano `snake_case`
(`signal_strength`, `is_hidden`), mentre i tipi timezone (`TimezoneStatus`) usano `camelCase`
(`ntpSynchronized`). Implementando esattamente questi due contratti così come sono cablati nel
client, l'API risulterebbe con due convenzioni diverse per due gruppi di endpoint. Uniformarla
significherebbe aggiornare anche GingerView.
A:

**Q2: Serve ancora un flusso di Access Point per il primo setup WiFi, quando la macchina non
ha ancora nessuna rete configurata?**
Contesto: la versione precedente di G2-Service (rimossa nel reset del progetto) esponeva un
Access Point su un'interfaccia dedicata proprio per configurare il WiFi la prima volta, in
assenza di rete. Va deciso se questo onboarding serve ancora nello scope attuale, o se si
assume che il Raspberry Pi sia sempre raggiungibile in altro modo (es. Ethernet, hotspot già
configurato in fabbrica) per la prima configurazione.
A:

**Q3: `/api/wifi/status` va rinominato in qualcosa come `/api/network/status`, o resta con il
nome storico anche se finisce per coprire anche lo stato Ethernet?**
Contesto: GingerView deriva già se la connessione è via cavo dal campo `adapter.type` della
risposta di `GET /api/wifi/status` — quell'endpoint è quindi già pensato per essere uno stato
di rete generico, nonostante il nome. Rinominarlo in `/api/network/status` sarebbe più onesto
ma richiede di aggiornare anche GingerView; tenerlo com'è evita l'update lato client ma lascia
un nome fuorviante.
A:
