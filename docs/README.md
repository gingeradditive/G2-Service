# Documentazione G2-Service

- [01 — Panoramica](01-panoramica.md) — cos'è G2-Service, perché esiste, di cosa si occupa (e di cosa no)
- [02 — Architettura](02-architettura.md) — collocazione nello stack G2, convenzioni comuni a tutte le API (prefisso, errori, job asincroni), privilegi, organizzazione del codice
- [03 — API: Rete e Timezone](03-proposta-api-rete-timezone.md) — endpoint WiFi/Ethernet, timezone, health
- [04 — API: Configurazioni stampante](04-proposta-api-configurazioni.md) — sincronizzazione da G2-Printers, seriale di fabbrica (deciso, futuro)
- [05 — Deploy e sviluppo](05-deploy-e-sviluppo.md) — porta, nginx, update_manager di Moonraker, `install.sh`, `rundev.sh`, mock, test
- [TODO.md](TODO.md) — gli step di sviluppo in ordine, divisi tra implementazione corrente e implementazioni future
- [Q&A.md](Q&A.md) — solo le domande ancora aperte. Quando una riceve risposta, esce da qui ed entra nella documentazione

Lo stato di implementazione è uno solo: c'è **la struttura trasversale** (prefisso `/service`,
`camelCase`, modello degli errori, job asincroni, selezione reale/mock) e **tutti gli endpoint
di [03](03-proposta-api-rete-timezone.md)** — health, rete, fuso orario — **più il deploy**
(unit systemd, nginx, `install.sh`). Quello che manca è la verifica su una macchina vera: le
configurazioni stampante ([04](04-proposta-api-configurazioni.md)) sono decisioni prese, non
codice esistente.
