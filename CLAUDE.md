# Online Home Work — CLAUDE.md

IT o'quv markazlari uchun loyiha tekshiruv platformasi. O'qituvchi topshiriq shartini, kutubxonalarni va testlarni yuklaydi; o'quvchi yechimini yuboradi; platforma uni izolyatsiyalangan Docker konteynerda testlab, har bir test natijasini jonli ko'rsatadi. Ishlash prinsipi acmp.ru va LeetCode'ga o'xshaydi, lekin algoritm emas, **loyihalar** tekshiriladi: Flutter, Dart, backend, frontend.

## Hujjatlar

Bu fayl har sessiyada to'liq yuklanadi, shuning uchun qisqa. Batafsil ma'lumot alohida fayllarda — kerak bo'lganda o'qi:

- `docs/ROADMAP.md` — bosqichlar va vazifalar. **Har sessiya boshida o'qi** va joriy vazifani shu yerdan ol.
- `docs/SPEC.md` — rollar, domen modeli, judge (tekshiruvchi), xavfsizlik, konfiguratsiya, testlash, deploy. Model, ruxsat yoki judge'ga tegishli ishdan oldin tegishli bo'limini o'qi.
- `docs/UI.md` — dizayn tizimi, sahifalar, UI matnlari. Har qanday shablon yoki CSS ishidan oldin o'qi.
- `docs/decisions.md` — arxitektura qarorlari jurnali (sana, qaror, sabab). Uni sen yuritasan.
- `docs/poc-results.md` — Phase 0 o'lchovlari (Phase 0 davomida yaratiladi).

## Ishlash qoidalari

- Erkin bilan **o'zbek tilida (lotin)** gaplash. Kod, identifikatorlar, kod izohlari, commit xabarlari — inglizcha. UI matnlari — o'zbekcha (`docs/UI.md` qoidalari bo'yicha).
- Erkin Flutter dasturchi va kiberxavfsizlik talabasi; Python va Django unga yangi bo'lishi mumkin. Yangi tushunchani (Django ORM, migratsiya, Docker SDK, `SKIP LOCKED`, HTMX va h.k.) ishlatishdan oldin uni bilish-bilmasligini so'ra; kerak bo'lsa mantiqini va sababini qisqa tushuntir, keyin kod yoz.
- Har bir vazifadan oldin qisqa reja ber: nima qilinadi, nega, qanday tekshiriladi. Katta ishlar plan mode'da rejalashtiriladi va tasdiqdan keyin bajariladi.
- Kod oddiy va tushunarli, Clean Architecture ruhida: domen mantiq framework'dan ajratilgan, bog'liqliklar ichkariga qaraydi, ortiqcha abstraksiya yo'q.
- Kichik qadamlar: bitta vazifa → testlar → `make check` → commit (Conventional Commits).
- Xatoni tuzatishdan oldin uni takrorlaydigan test yoz.
- "Qat'iy qarorlar" yoki "Hech qachon" bo'limlariga zid ish kerak bo'lsa: to'xta, sababini tushuntir, ruxsat so'ra va qarorni `docs/decisions.md` ga yoz.
- Vazifa tugaganda `docs/ROADMAP.md` dagi katakchani belgila va bir qator izoh qo'sh.
- Erkinning terminali **Fish shell**: unga buyruq berganda `export X=1` o'rniga `set -x X 1`, heredoc ishlatma. Loyiha skriptlari bash'da (`#!/usr/bin/env bash`) yoziladi va Makefile orqali chaqiriladi.
- Lokal mashina: CachyOS (Arch, x86_64). Prod: linux/arm64. Faqat multi-arch base image'lar; arxitekturaga bog'liq narsa hardcode qilinmaydi.

## Infratuzilma va masshtab

- Prod: Oracle Cloud Always Free, Ampere A1 — **linux/arm64, 2 OCPU, 12 GB RAM**.
- Boshida 2 ta parallel tekshiruv sloti: 1 ta `heavy` (Flutter) + 1 ta `fast` (Dart, backend, frontend).
- Server keyin kuchaytiriladi. Talab: parallel tekshiruvlar soni **faqat konfiguratsiya bilan** oshadi — `JUDGE_SLOTS=heavy:3,fast:2` qilib worker qayta ishga tushiriladi yoki yangi serverda qo'shimcha worker ishga tushiriladi (o'sha bazaga ulanadi, image'larni o'zi yig'adi). Buning uchun kod o'zgarmasligi kerak.

## Qat'iy qarorlar

| Qism | Tanlov |
|---|---|
| Til va paketlar | Python 3.12, `uv` |
| Backend | Django 5.2 LTS, bitta monolit |
| Baza | PostgreSQL 17 |
| Navbat | `Job` jadvali + `select_for_update(skip_locked=True)` — Redis/Celery yo'q |
| Frontend | Django templates + HTMX 2 + Alpine.js 3 — SPA yo'q |
| CSS | Tailwind CSS v4, `django-tailwind-cli` (standalone, Node'siz) |
| Jonli natija | HTMX polling (1 s); tekshiruv tugaganda server HTTP 286 qaytaradi va polling to'xtaydi |
| Izolyatsiya | Docker, Python `docker` SDK; keyinchalik ixtiyoriy gVisor (`runsc`) |
| Markdown | `markdown-it-py` + `nh3` sanitizatsiya |
| Kod ko'rinishi | Pygments (server tomonda) |
| Statik fayllar | WhiteNoise; HTMX, Alpine, shriftlar, ikonlar self-hosted (CDN yo'q) |
| Prod | Docker Compose: `caddy`, `web` (gunicorn), `worker`, `db` |
| Sifat | ruff (lint + format), pytest + pytest-django, djLint, django-axes |

Sabablar: Django auth, admin panel, ORM va formalarni tayyor beradi; navbat bazada bo'lgani uchun bitta servis kam; server-rendered sahifalar zaif kompyuterlarda ham tez ochiladi.

## Arxitektura

```
Brauzer ─HTTPS─> caddy ─> web (Django) ─────> db (PostgreSQL)
                                                 ▲  Job navbati, natijalar
                          worker (judge_worker) ─┘
                             │ Docker API — faqat worker
                             ▼
                vaqtinchalik konteynerlar (internetsiz, limitlar bilan)
```

- `web` hech qachon Docker bilan gaplashmaydi. Docker socket'ga faqat `worker` kiradi.
- O'quvchi kodi faqat izolyatsiyalangan konteynerda bajariladi.
- Worker o'zi konteynerda ishlaydi: host yo'llarini bind mount qilma (yo'llar mos kelmaydi), fayllar konteynerga `put_archive` bilan beriladi.
- Fayllar Django storage API orqali saqlanadi, keyinchalik S3-compatible storage'ga o'tish oson bo'lishi uchun.

```
config/              settings (env orqali), urls, wsgi
apps/accounts/       User, rollar, Center, Group, ruxsatlar qatlami
apps/tasks/          RunnerProfile, Task, TaskVersion, Assignment
apps/submissions/    Submission, SubmissionTestResult, jurnal
apps/system/         Job, WorkerNode, /system sahifasi
judge/               tekshiruvchi yadrosi — Django'ni import qilmaydi
  core/              entity, event, verdict, use-case'lar (sof Python)
  parsers/           dart_json, ohw_jsonl → umumiy event formati
  packaging/         zip validator, paket strukturasi, all_test.dart va starter generatsiyasi
  infra/             docker runner, image builder
  adapters/          Django ORM repository'lari
  cli.py             python -m judge.cli build|run — Django'siz PoC va debug uchun
profiles/            base image Dockerfile'lari: dart/, flutter/, pytest-http/, playwright/
examples/            namuna topshiriqlar va turli yechimlar (testlar + o'qituvchilar uchun shablon)
templates/  static/  docs/
```

`judge/core`, `judge/parsers` va `judge/packaging` Docker'siz unit-test qilinadi.

## Hech qachon

- Parallel tekshiruvlar soni, RAM yoki CPU qiymatlarini kodga yozma — faqat konfiguratsiya.
- O'quvchi kodini konteynerdan tashqarida ishga tushirma; zipni validatsiyadan oldin ochma.
- O'quvchiga test kodini, xom stdout'ni yoki yashirin test kod parchalarini ko'rsatma.
- O'quvchiga kutubxona qo'shishga ruxsat berma — kutubxonalarni faqat o'qituvchi belgilaydi.
- Yechim tekshiruvida konteynerga internet berma. Internet faqat image yig'ishda, kutubxona o'rnatish uchun.
- `MEDIA` fayllarini ommaviy URL orqali berma — faqat ruxsatni tekshiradigan view orqali.
- Boshqa markaz ma'lumotiga yo'l qoldirma: obyekt faqat `get_for_user_or_404()` orqali olinadi.
- MVP'da Redis, Celery, Kubernetes, mikroservis yoki SPA freymvork qo'shma.

## Buyruqlar

```
make setup         # uv sync, pre-commit
make dev           # Postgres (compose.dev.yml) + runserver + tailwind watch
make worker        # python manage.py judge_worker
make base-images   # profiles/* ni joriy arxitekturada yig'ish
make poc           # examples/ ni judge CLI orqali ishlatish va o'lchash
make test          # tez testlar (Docker'siz)
make test-docker   # Docker talab qiladigan integration testlar (marker: docker)
make lint          # ruff check, ruff format --check, djlint
make check         # lint + test — har commitdan oldin
```

## Asosiy sozlamalar

To'liq ro'yxat: `docs/SPEC.md`, "Konfiguratsiya" bo'limi. Eng muhimlari:

- `JUDGE_SLOTS=heavy:1,fast:1` — parallel tekshiruv slotlari; server kuchaytirilganda faqat shu o'zgaradi.
- `JUDGE_RESERVED_MEMORY_MB` — sayt va baza uchun qoldiriladigan RAM; worker ishga tushganda slotlar sig'ishini tekshiradi.
- `SUBMISSION_COOLDOWN_S`, `SUBMISSION_MAX_ACTIVE_PER_STUDENT` — navbat adolati.
- `FLUTTER_VERSION` — Flutter base image shu aniq versiyada yig'iladi.
