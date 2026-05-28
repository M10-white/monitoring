# Stack de Monitoring — Niveaux 1, 2 & 3

Stack complète de monitoring avec Docker Compose : Nginx, MariaDB, Prometheus, cAdvisor, Blackbox, Alertmanager, Loki, Promtail et Grafana.

> 📄 **Documentation technique complète** (explication de chaque ligne) : [`docs/explication-projet.pdf`](docs/explication-projet.pdf)

---

## Services

| Service | Rôle | Port |
|---|---|---|
| **Nginx** | Serveur web — sert les pages statiques, expose `/stub_status` | `80` |
| **MariaDB** | Base de données relationnelle | interne |
| **cAdvisor** | Collecte les métriques Docker (CPU, RAM, réseau, disque) | `8080` |
| **Blackbox** | Sondes HTTP (Nginx) et TCP (MariaDB) — mesure latence et disponibilité | `9115` |
| **Prometheus** | Scrape et stocke les métriques toutes les 15s, évalue les règles d'alerte | `9090` |
| **Alertmanager** | Reçoit les alertes de Prometheus et les route vers les receivers | `9093` |
| **webhook-logger** | Reçoit les alertes d'Alertmanager et les affiche dans ses logs | `5001` |
| **Loki** | Agrège et stocke les logs de tous les conteneurs | `3100` |
| **Promtail** | Collecte les logs Docker via socket et les envoie à Loki | interne |
| **Grafana** | Dashboard unifié — métriques Prometheus + logs Loki | `3000` |

---

## Schéma global des services

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Docker Network                              │
│                                                                     │
│  ┌─────────┐   ┌──────────┐                                        │
│  │  Nginx  │   │ MariaDB  │  ← Stack applicative                   │
│  │  :80    │   │ (intern) │                                        │
│  └────┬────┘   └────┬─────┘                                        │
│       │             │                                               │
│  ┌────▼─────────────▼──────┐   ┌─────────────────┐                │
│  │        cAdvisor          │   │    Blackbox      │               │
│  │  métriques CPU/RAM/réseau│   │  sondes HTTP+TCP │               │
│  └────────────┬─────────────┘   └────────┬─────────┘               │
│               │  scrape /metrics          │  scrape /probe          │
│               └──────────────┬────────────┘                        │
│                               ▼                                     │
│                      ┌─────────────────┐                           │
│                      │   Prometheus    │  ← cerveau métriques      │
│                      │  stockage TSDB  │                           │
│                      └───────┬─────────┘                           │
│                               │ alertes FIRING                      │
│                               ▼                                     │
│                      ┌─────────────────┐                           │
│                      │  Alertmanager   │  ← routage alertes        │
│                      └───────┬─────────┘                           │
│                               │ POST webhook                        │
│                               ▼                                     │
│                      ┌─────────────────┐                           │
│                      │ webhook-logger  │  ← notifications           │
│                      └─────────────────┘                           │
│                                                                     │
│  ┌──────────┐  logs   ┌──────┐  push   ┌──────┐                   │
│  │ Promtail │ ──────► │ Loki │ ──────► │      │                   │
│  └──────────┘         └──────┘         │      │                   │
│                                         │Grafana│ ← dashboard unifié│
│  ┌──────────────────────────────────── │      │                   │
│  │         Prometheus (métriques)  ──► │      │                   │
│  └──────────────────────────────────── └──────┘                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Lancement

```bash
docker compose up -d
```

### Accès aux interfaces

| Interface | URL | Identifiants |
|---|---|---|
| Nginx | http://localhost:80 | — |
| Prometheus | http://localhost:9090 | — |
| Prometheus Alerts | http://localhost:9090/alerts | — |
| Alertmanager | http://localhost:9093 | — |
| cAdvisor | http://localhost:8080 | — |
| Grafana | http://localhost:3000 | admin / admin |

---

## Niveau 2 — Alerting

### 3 règles d'alerte

| Règle | Expression PromQL | Seuil | Délai |
|---|---|---|---|
| **ContainerDown** | `probe_success{job=~"blackbox-nginx\|blackbox-mariadb"} == 0` | Immédiat | `for: 0s` |
| **DatabaseDiskFull** | `container_fs_usage_bytes{name="mariadb"} > 100MB` | 100 MB disque | `for: 1m` |
| **NginxHighLatency** | `probe_duration_seconds{job="blackbox-nginx"} > 0.5` | 500ms | `for: 1m` |

### Simulation de pannes

```bash
# 1. Arrêter nginx → déclenche ContainerDown (~20s) + NginxHighLatency (~1min)
docker stop nginx

# 2. Surveiller les alertes en temps réel
docker logs -f webhook-logger

# 3. Vérifier dans Alertmanager
#    → http://localhost:9093

# 4. Vérifier dans Prometheus
#    → http://localhost:9090/alerts

# 5. Relancer nginx → alerte RESOLVED
docker start nginx
```

**Timeline d'une alerte ContainerDown :**
```
t=0s   → docker stop nginx
t=5s   → Blackbox timeout : probe_success = 0
t=15s  → Prometheus scrape → règle évaluée → état FIRING
t=25s  → Alertmanager group_wait écoulé → POST vers webhook-logger
t=25s  → docker logs webhook-logger : [FIRING] [critical] ContainerDown
```

---

## Niveau 3 — Logs & Dashboard unifié

- **Loki** collecte et indexe les logs de tous les conteneurs
- **Promtail** découvre automatiquement les conteneurs via le socket Docker
- **Dashboard Grafana** combine métriques + logs sur le même écran

### Dashboard Grafana "Monitoring Stack"

Panels disponibles :
- CPU usage par conteneur (%)
- Mémoire utilisée par conteneur (MB)
- Réseau reçu / envoyé (KB/s)
- Latence Nginx (ms) avec seuil rouge à 500ms
- Conteneurs actifs (compteur)
- Alertes actives (compteur)
- **Logs de tous les conteneurs** (Loki) — en bas du dashboard

Le dashboard et les datasources sont **provisionnés automatiquement** au démarrage (aucune configuration manuelle).

![Dashboard Grafana](docs/grafana-dashboard.png)

---

## Structure du projet

```
monitoring/
├── docker-compose.yml              # Orchestration des 10 services
├── nginx/
│   ├── default.conf                # Config Nginx + stub_status
│   └── html/index.html             # Page web servie
├── prometheus/
│   ├── prometheus.yml              # Config scraping + alertmanagers
│   └── rules/alerts.yml            # 3 règles d'alerte PromQL
├── alertmanager/
│   └── alertmanager.yml            # Routage alertes → webhook
├── blackbox/
│   └── blackbox.yml                # Modules HTTP + TCP
├── webhook-logger/
│   ├── Dockerfile                  # Image Python alpine
│   └── server.py                   # Serveur HTTP qui reçoit les alertes
├── loki/
│   └── loki-config.yml             # Stockage logs filesystem
├── promtail/
│   └── promtail-config.yml         # Collecte logs via Docker socket
├── grafana/
│   └── provisioning/
│       ├── datasources/
│       │   ├── prometheus.yml      # Datasource Prometheus auto
│       │   └── loki.yml            # Datasource Loki auto
│       └── dashboards/
│           ├── dashboard.yml       # Loader de dashboards
│           └── monitoring.json     # Dashboard unifié métriques + logs
└── docs/
    ├── grafana-dashboard.png       # Screenshot du dashboard
    └── explication-projet.pdf     # Documentation technique complète
```

---

## Arrêt

```bash
# Arrêter les conteneurs (données conservées)
docker compose down

# Arrêter et supprimer les volumes (repart de zéro)
docker compose down -v
```
