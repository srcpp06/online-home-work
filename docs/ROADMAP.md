# ROADMAP — Online Home Work

**Joriy bosqich: Phase 0 (PoC).**

Qoidalar: vazifalar tartib bilan bajariladi. Tugagan vazifa `[x]` bilan belgilanadi va yoniga bir qator izoh yoziladi (nima qilindi, qayerda). Bosqich tugaganda "Joriy bosqich" yangilanadi. "Qaror nuqtasi" — Erkin bilan natijani ko'rib chiqmasdan keyingi bosqichga o'tilmaydi.

## Phase 0 — PoC: faqat judge, sayt yo'q

Maqsad: "topshiriq paketi + o'quvchi zipi → natija" zanjiri ARM64 serverda ishlashini va qancha vaqt olishini isbotlash. Loyihaning eng katta xavfi shu yerda.

- [x] Repo skeleti: `uv`, ruff, pytest, Makefile, `.env.example`, `.gitignore`, `docs/decisions.md` — `pyproject.toml`, `Makefile`, pre-commit, `judge/` qatlamlari va ularning bog'liqlik testi (`tests/test_architecture.py`)
- [x] `judge/core`: event, verdict, manifest entity'lari — `events.py`, `manifest.py`, `progress.py` (oqimni manifest bilan solishtirish), `verdict.py` (`decide_verdict`, SPEC §3.4 tartibi)
- [x] `dart_json` parser + yozib olingan chiqishlar bilan fixture testlar — `judge/parsers/dart_json.py`; Dart 3.13.5 dagi 8 ta haqiqiy chiqish (`make fixtures-dart`), fixture → verdict zanjiri testlangan
- [x] Zip validator + zararli zip testlari (zip-slip, symlink, zip-bomb, absolyut yo'l) — `judge/packaging/zip_validator.py`; zararli zip'lar testda yasaladi, fuzz testi ikki xato topdi va ular tuzatildi
- [x] Base image'lar: `profiles/dart`, `profiles/flutter` (multi-arch, `FLUTTER_VERSION` bilan) — `make base-images`; ikkalasi internetsiz uid 1000 bilan smoke-test qilinadi. Flutter'ning `apt-get` qadami sessiya muhitida tekshirilmadi (`deb.debian.org` bloklangan), lokal `make base-images` da tasdiqlanadi
- [x] Image builder: birlashtirilgan test fayli, o'qituvchi yechimi bilan isitish, manifest — `judge/infra/image_builder.py`, `judge/infra/sandbox.py`; isitilgan image yangi kodni tekshirishi dart va flutter'da integration test bilan isbotlangan (`make test-docker`)
- [x] Runner: limitlar, `put_archive`, chiqishni streaming o'qish, birinchi xatoda to'xtash, timeout va OOM aniqlash — `judge/infra/runner.py` + `judge/packaging/submission.py`; cheksiz sikl, xotira, chiqish oqimi, soxta JSON va butun loyiha zipi Docker testlarida tekshirilgan
- [ ] Statik import tekshiruvi (dart/flutter)
- [ ] `python -m judge.cli build` va `python -m judge.cli run`
- [ ] `examples/dart-*` va `examples/flutter-*` — barcha yechim turlari bilan (SPEC §7)
- [ ] Lokal o'lchov (x86_64)
- [ ] ARM64 serverda o'lchov: cold va warm vaqt, RAM cho'qqisi, 2 slot bir vaqtda; `dart test` Flutter loyiha ichida ishlashi; isitilgan kesh qancha tezlashtirgani. Natijalar `docs/poc-results.md` ga
- [ ] **Qaror nuqtasi:** natijalarni Erkin bilan ko'rib chiqish; profil limitlari va `two_stage` bo'yicha qaror

## Phase 1 — MVP veb

- [ ] Django loyiha, env orqali settings, PostgreSQL (`compose.dev.yml`)
- [ ] `User` (rollar), `Center`, `Group`; ruxsatlar qatlami (`for_user`, `get_for_user_or_404`) + IDOR testlari
- [ ] Superadmin uchun Django admin; markaz admini sahifalari (CRUD, parolni tiklash), birinchi kirishda parol almashtirish
- [ ] Dizayn tizimi asoslari: tokenlar, shriftlar, base layout, daftar sahifasi, holat belgisi
- [ ] `RunnerProfile` seed (`dart`, `flutter`)
- [ ] `Task` / `TaskVersion`: yaratish ustasi, paket yuklash va struktura tekshiruvi, build job, jonli build logi, e'lon qilish
- [ ] `Assignment`: guruhga biriktirish, muddat
- [ ] `Submission`: yuklash, validatsiya, cooldown va faol yechimlar limiti, `Job` yaratish
- [ ] `judge_worker`: slotlar va lane'lar, SKIP LOCKED, lease/heartbeat, reaper, xotira sig'ishi tekshiruvi
- [ ] Jonli natija sahifasi: HTMX polling, navbatdagi o'rin, verdict muhri
- [ ] Jurnal
- [ ] `compose.prod.yml`, Caddy, `docs/deploy.md`; serverga birinchi deploy
- [ ] **Qaror nuqtasi:** bitta haqiqiy guruh bilan sinov

## Phase 2 — Sifat

- [ ] Starter zip generatsiyasi va yuklab olish
- [ ] Flutter 2 bosqichli tekshiruv (PoC natijasiga qarab)
- [ ] Kompilyatsiya xatolarini tozalash; hidden test xabarlarini yashirish
- [ ] Qayta tekshirish (rejudge)
- [ ] CSV import (o'quvchilar), jurnal eksporti (CSV)
- [ ] Markaz topshiriqlar banki: o'qituvchilar bir-birining topshirig'idan nusxa oladi
- [ ] `/system` sahifasi
- [ ] Audit log
- [ ] Dark mode "Doska"

## Phase 3 — Backend va frontend

- [ ] `ohw_jsonl` pytest plugini va platforma conftest'i
- [ ] `backend-python`: `app` + `tester` konteynerlari, umumiy network namespace, server ishga tushishini kutish
- [ ] `web-static`: Playwright
- [ ] `backend-node`
- [ ] Har bir profil uchun `examples/` va integration testlar
- [ ] O'qituvchilar uchun har bir yo'nalish bo'yicha yo'riqnoma sahifasi

## Phase 4 — Kengaytirish

- [ ] Telegram bot orqali bildirishnomalar
- [ ] LISTEN/NOTIFY (tezroq navbat) yoki SSE
- [ ] Brauzerda kod muharriri (bitta faylli Dart va algoritm topshiriqlari)
- [ ] Plagiat tekshiruvi
- [ ] gVisor (`JUDGE_RUNTIME=runsc`), ko'p node, S3-compatible storage
- [ ] Rus tili (i18n)
