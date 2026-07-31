# Q&A

Domande aperte che servono per procedere con lo sviluppo. Rispondi sotto ogni `A:`, anche in
momenti diversi.

**Come funziona il file.** Quando una domanda riceve risposta, viene rimossa da qui e la
decisione finisce nella documentazione (`01`–`04`). L'obiettivo è arrivare ad avere questo
file **vuoto**.

La numerazione **non** viene mai riusata: le nuove domande partono da dove finiscono le
vecchie, così i rimandi `Qn` nella documentazione restano validi nel tempo.

---

**Q4: Dove va persistito il seriale di fabbrica sul Raspberry Pi, e quanto deve essere
resistente?**
Contesto: hai detto "salvato da qualche parte sul raspberry più stabilmente possibile" senza
specificare dove — vedi [04 — Configurazioni](04-proposta-api-configurazioni.md#1-seriale-di-fabbrica).
Opzioni: un file semplice (es. `/etc/g2/serial`, sopravvive ad aggiornamenti software ma non a
un riflash della SD), qualcosa scritto durante il first-boot in un punto pensato per
sopravvivere anche a un riflash (richiederebbe supporto in G2-OS, non solo in G2-Service), o
entrambe le cose per ridondanza. Deve sopravvivere solo a riavvii/aggiornamenti, o anche a una
reinstallazione completa del sistema?
A:

**Q5: Il repository `G2-Printers` è pubblico o privato? Se privato, come si autentica
G2-Service verso GitHub per leggerlo?**
Contesto: contiene le configurazioni macchina — ragionevole che sia privato. Se lo è, ogni
stampante deve potersi autenticare verso GitHub in autonomia, senza intervento umano, il che
tocca anche come viene distribuita la credenziale nelle immagini G2-OS. È lo stesso problema
già affrontato per clonare G2-Service stesso: il modulo `69-G2-Service` in G2-OS usa
`GITHUB_TOKEN` oppure una chiave SSH per-utente. Si riusa lo stesso meccanismo, o serve altro
(es. deploy key dedicata e read-only solo per `G2-Printers`, dato che è un repository diverso
con un livello di sensibilità diverso)?
A:

**Q6: Come si determina se i file online sono "più nuovi" di quelli locali?**
Contesto: vedi [04 — Configurazioni](04-proposta-api-configurazioni.md#2-sincronizzazione-configurazione).
Due approcci: confronto tra commit Git (fetch e confronto tra l'ultimo commit noto localmente
e l'HEAD remoto che tocca la cartella della stampante) oppure un manifest di versione scritto
a mano dentro ogni cartella stampante (es. `G2-Printers/<seriale>/version.json`). Il primo è
automatico ma lega "versione" al repository condiviso; il secondo è esplicito ma va
aggiornato a mano a ogni modifica.
A:

**Q7: Serve un rollback automatico se l'aggiornamento configurazione fallisce o Klipper non
riparte con i nuovi file?**
Contesto: è una sincronizzazione non presidiata, eseguita da sola a ogni avvio, potenzialmente
su macchine remote/clienti — vedi [04 — Configurazioni](04-proposta-api-configurazioni.md#3-comportamento-allavvio).
Una config rotta pubblicata per errore su `G2-Printers` potrebbe impedire a Klipper di
avviarsi del tutto. Senza un meccanismo che torni automaticamente ai file precedenti noti
funzionanti, la macchina resterebbe bloccata finché qualcuno non interviene manualmente (es.
da remoto via SSH, o fisicamente).
A:
