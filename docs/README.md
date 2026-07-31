# Documentazione G2-Service

- [01 — Panoramica](01-panoramica.md) — cos'è G2-Service, perché esiste, di cosa si occupa (e di cosa no)
- [02 — Architettura](02-architettura.md) — collocazione nello stack G2, convenzioni comuni a tutte le API (prefisso, errori, job asincroni), privilegi, organizzazione del codice
- [03 — API: Rete e Timezone](03-proposta-api-rete-timezone.md) — endpoint WiFi/Ethernet, timezone, health
- [04 — API: Configurazioni stampante](04-proposta-api-configurazioni.md) — sincronizzazione da G2-Printers, seriale di fabbrica (deciso, futuro)
- [05 — Deploy e sviluppo](05-deploy-e-sviluppo.md) — porta, nginx, update_manager di Moonraker, `install.sh`, `rundev.sh`, mock, test
- [Q&A.md](Q&A.md) — solo le domande ancora aperte. Quando una riceve risposta, esce da qui ed entra nella documentazione

Lo stato di implementazione è uno solo: **niente è implementato tranne `GET /health`**. Tutti i
documenti qui descrivono decisioni prese, non codice esistente.
