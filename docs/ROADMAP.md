# ROADMAP — Online Home Work

**Joriy bosqich: Phase 1 (MVP veb).** Phase 0 tugadi (2026-10-03).

Qoidalar: vazifalar tartib bilan bajariladi. Tugagan vazifa `[x]` bilan belgilanadi va yoniga bir qator izoh yoziladi (nima qilindi, qayerda). Bosqich tugaganda "Joriy bosqich" yangilanadi. "Qaror nuqtasi" — Erkin bilan natijani ko'rib chiqmasdan keyingi bosqichga o'tilmaydi.

## Phase 0 — PoC: faqat judge, sayt yo'q

Maqsad: "topshiriq paketi + o'quvchi zipi → natija" zanjiri ARM64 serverda ishlashini va qancha vaqt olishini isbotlash. Loyihaning eng katta xavfi shu yerda.

- [x] Repo skeleti: `uv`, ruff, pytest, Makefile, `.env.example`, `.gitignore`, `docs/decisions.md` — `pyproject.toml`, `Makefile`, pre-commit, `judge/` qatlamlari va ularning bog'liqlik testi (`tests/test_architecture.py`)
- [x] `judge/core`: event, verdict, manifest entity'lari — `events.py`, `manifest.py`, `progress.py` (oqimni manifest bilan solishtirish), `verdict.py` (`decide_verdict`, SPEC §3.4 tartibi)
- [x] `dart_json` parser + yozib olingan chiqishlar bilan fixture testlar — `judge/parsers/dart_json.py`; Dart 3.13.5 dagi 8 ta haqiqiy chiqish (`make fixtures-dart`), fixture → verdict zanjiri testlangan
- [x] Zip validator + zararli zip testlari (zip-slip, symlink, zip-bomb, absolyut yo'l) — `judge/packaging/zip_validator.py`; zararli zip'lar testda yasaladi, fuzz testi ikki xato topdi va ular tuzatildi
- [x] Base image'lar: `profiles/dart`, `profiles/flutter` (multi-arch, `FLUTTER_VERSION` bilan) — `make base-images`; ikkalasi internetsiz uid 1000 bilan smoke-test qilinadi. Flutter'ning `apt-get` qadami lokal `make base-images` da tasdiqlandi (CachyOS, 2026-10-01)
- [x] Image builder: birlashtirilgan test fayli, o'qituvchi yechimi bilan isitish, manifest — `judge/infra/image_builder.py`, `judge/infra/sandbox.py`; isitilgan image yangi kodni tekshirishi dart va flutter'da integration test bilan isbotlangan (`make test-docker`)
- [x] Runner: limitlar, `put_archive`, chiqishni streaming o'qish, birinchi xatoda to'xtash, timeout va OOM aniqlash — `judge/infra/runner.py` + `judge/packaging/submission.py`; cheksiz sikl, xotira, chiqish oqimi, soxta JSON va butun loyiha zipi Docker testlarida tekshirilgan
- [x] Statik import tekshiruvi (dart/flutter) — `judge/packaging/dart_imports.py`; 26 ta aylanib o'tish usuli haqiqiy Dart'da sinalgan va hammasi rad etiladi. Oqimga (`judge.cli run`) keyingi vazifada ulanadi
- [x] `python -m judge.cli build` va `python -m judge.cli run` — `judge/cli.py`, `judge/config.py`, `judge_zip`; image o'z ma'lumotini label'da saqlaydi, `run --json` PoC o'lchovlari uchun
- [x] `examples/dart-*` va `examples/flutter-*` — barcha yechim turlari bilan (SPEC §7) — `examples/dart-cart`, `examples/flutter-todo`; 17 ta yechim `tests/examples/` da, `make poc` jadval chiqaradi
- [x] Lokal o'lchov (x86_64) — CachyOS, 17/17 verdict kutilgandek; `docs/poc/x86_64-20261001-2059.md`, xulosa va takliflar `docs/poc-results.md` da
- [x] ARM64 serverda o'lchov: cold va warm vaqt, RAM cho'qqisi, 2 slot bir vaqtda; `dart test` Flutter loyiha ichida ishlashi; isitilgan kesh qancha tezlashtirgani. Natijalar `docs/poc-results.md` ga. Yo'riqnoma: `docs/poc.md`. — Oracle A1 (2 OCPU, Ubuntu 24.04), 2026-10-03: `make test-docker` 117/117, `make poc` ikki marta 17/17; `docs/poc/aarch64-20261003-*.md`
- [x] **Qaror nuqtasi:** natijalarni Erkin bilan ko'rib chiqish; profil limitlari va `two_stage` bo'yicha qaror — 2026-10-03: flutter RAM 1536 MB, vaqt limiti tayyor image'dagi iliq tekshiruvdan (min dart 15 s / flutter 30 s), `two_stage` MVP'da yo'q, `JUDGE_SLOTS=heavy:1,fast:1`; `docs/decisions.md`, `docs/poc-results.md`; ARM'da yangi limitlar bilan `make poc` 17/17 (`docs/poc/aarch64-20261003-0744.md`)

## Phase 1 — MVP veb

- [x] Django loyiha, env orqali settings, PostgreSQL (`compose.dev.yml`) — `config/` (sozlamalar `config/env.py` orqali, kodda standart qiymat yo'q), `apps/accounts` da birinchi migratsiyadan o'z `User` modeli, `make db`/`migrate`/`dev`; veb testlari haqiqiy PostgreSQL 17 da (`tests/config/`)
- [x] `User` (rollar), `Center`, `Group`; ruxsatlar qatlami (`for_user`, `get_for_user_or_404`) + IDOR testlari — `apps/accounts/models.py` (rol qoidalari bazada `CheckConstraint`), `apps/accounts/access.py`; rol × boshqa markaz IDOR testlari, har model `for_user` ga va har parametrli URL IDOR testiga ega bo'lishini tekshiruvchi qo'riqchi testlar (`tests/apps/`); Erkin so'rovi bilan markaz menejeri roli (faqat ko'rish) va rollar jadvali `apps/accounts/permissions.py`
- [x] Dizayn tizimi asoslari: tokenlar, shriftlar, base layout, daftar sahifasi, holat belgisi — Erkin roziligi bilan keyingi vazifadan oldinga olindi (sahifalar bir marta yozilsin). `assets/source.css` (Tailwind v4, faqat UI.md ranglari), self-hosted shriftlar (Literata, Golos Text, JetBrains Mono + `ʻ` uchun OHW Marks), `apps/ui` (`{% icon %}`, `{% status_badge %}`, `/ui/` styleguide), `templates/base.html` va `layouts/app.html`, WhiteNoise; desktop va telefon skrinshotlari bilan tekshirildi
- [x] Superadmin uchun Django admin; markaz admini sahifalari (CRUD, parolni tiklash), birinchi kirishda parol almashtirish — kirish/chiqish, birinchi kirishda majburiy parol almashtirish, django-axes (login + IP bo'yicha), rolga qarab bosh sahifa va menyu; o'qituvchi, o'quvchi, menejer va guruhlar sahifalari (`apps/accounts/views/`), menejer va o'qituvchi uchun faqat ko'rish; vaqtinchalik parol bir marta ko'rsatiladi; har bir id URL uchun GET+POST IDOR testi
- [x] `RunnerProfile` seed (`dart`, `flutter`) — `manage.py load_profiles` (`make migrate` ishga tushiradi) `profiles/*/profile.json` dan; fayli yo'q profil o'chiriladi, o'chirilmaydi
- [x] `Task` / `TaskVersion`: yaratish ustasi, paket yuklash va struktura tekshiruvi, build job, jonli build logi, e'lon qilish — `apps/tasks/views.py` (3 qadam: topshiriq va paket → image yig'ish → e'lon), paket saytda tekshiriladi, image `judge.adapters.jobs.run_build` da; log har qadamda yangilanadi
- [x] `Assignment`: guruhga biriktirish, muddat — `/tasks/<id>/assign/`: ochilish vaqti, muddat, kechikishga ruxsat, urinishlar limiti; bir guruhga bir marta, muddat ochilishdan keyin (baza cheklovi)
- [x] `Submission`: yuklash, validatsiya, cooldown va faol yechimlar limiti, `Job` yaratish — `apps/submissions/services.py`: muddat, urinishlar, faol limit, cooldown, o'quvchi bo'yicha qulf; zip saytda worker bilan bir xil funksiya bilan tekshiriladi, rad etilgani darhol "Rad etildi" oladi va navbatga tushmaydi; "Topshiriqlarim" va topshiriq sahifasi (shart, boshlang'ich loyiha, muhit, urinishlar tarixi)
- [x] `judge_worker`: slotlar va lane'lar, SKIP LOCKED, lease/heartbeat, reaper, xotira sig'ishi tekshiruvi — `make worker`; `judge/adapters/worker.py` (slot thread'lari), `apps/system/queue.py` (claim/lease/reap, 3 urinishdan keyin `system_error`); image'i yo'q node uni paketdan qayta yig'adi; heavy slot bo'sh qolsa fast ishni oladi
- [x] Jonli natija sahifasi: HTMX polling, navbatdagi o'rin, verdict muhri — `/submissions/<id>/`: daftar qatorlari, "yozilmoqda" qatori, muhr, kompilyatsiya xatosi tozalangan holda; o'qituvchi, admin va menejer uchun kod (Pygments), o'qituvchiga "Qayta tekshirish"; real worker bilan brauzerda tekshirildi
- [x] Jurnal — `/groups/<id>/journal/` (`apps/submissions/journal.py`): `+`, `+N`, `−N`, `…`, kechikkan `*`; saralash yechildi ↓, urinishlar ↑, ism; sticky sarlavha va ism ustuni; katak yechimni ochadi, yechim sahifasida o'quvchining barcha urinishlari; o'quvchiga faqat guruhda yoqilgan bo'lsa va faqat o'z kataklari ochiladi
- [x] `compose.prod.yml`, Caddy, `docs/deploy.md` — bitta image (`Dockerfile`: web, worker, migrate), `scripts/create-env.sh --production DOMAIN`, `make deploy`, `scripts/backup.sh`; sandboxda to'liq stek bilan tekshirildi: HTTPS, build → yechim → "Qabul qilindi", worker'ning SIGTERM'da to'xtashi, zaxira
- [ ] Serverga birinchi deploy — Erkin, `docs/deploy.md` bo'yicha
- [ ] **Qaror nuqtasi:** bitta haqiqiy guruh bilan sinov

### Sinovda topilgan kamchiliklar (to'planadi, keyin birga tuzatiladi)

- [ ] Topshiriq yaratish sahifasi paket formatini tushuntirmaydi: tuzilish sxemasi va "Namuna paketni yuklab olish" (Dart, Flutter) kerak — Erkin oddiy Flutter loyihasini yuklab, xatolar ro'yxatini oldi
- [ ] Jurnalni o'quvchilarga ochishni faqat markaz admini qila oladi (guruh tahriri); o'qituvchi ham o'z guruhida qila olsin
- [ ] Yashirin test xabarini o'quvchiga ochish sozlamasi (`show_hidden_messages`, SPEC §3.8) yo'q

## Phase 1.5 — Erkin sinovidan keyin: professional platforma

Erkin birinchi deploydan keyin so'radi (2026-10-03): qulay, zamonaviy, imkoniyatlari ko'p, premium. Javoblari `docs/decisions.md` da. Har bosqich oxirida: testlar, skrinshotlar, deploy.

**1-bosqich — rollar, kirish, profil**
- [x] Yangi rollar: menejer hammasini ko'radi va faqat adminlarni boshqaradi; admin faqat o'qituvchi, o'quvchi va guruhlar bilan ishlaydi, topshiriq, natija va jurnallarni ko'rmaydi; menejerni superadmin yaratadi
- [x] Alohida kirish: o'quvchilar va xodimlar (o'qituvchi, menejer, admin) uchun alohida sahifa; bosh sahifa — `/login/`, `/staff/login/`, `/` (oddiy bosh sahifa; animatsiyali — 6-bosqich)
- [ ] Superadmin paneli internetdan yopiq: faqat serverga SSH tunnel orqali
- [ ] Shaxsiy profil: rasm, aloqa, o'zi haqida, rolga qarab statistika

**2-bosqich — admin ish joyi**
- [ ] Har ro'yxatda qidiruv va filtrlar (guruh, yo'nalish, holat), sahifalash
- [ ] O'quvchilarni belgilab, ommaviy guruhga qo'shish; guruh ichida qidirib qo'shish; CSV import
- [ ] Admin bosh sahifasi: raqamlar, oxirgi o'zgarishlar

**3-bosqich — mavzular daraxti va topshiriq muharriri**
- [ ] Har o'qituvchining Notion kabi mavzular daraxti (mavzu → ichki mavzu → topshiriqlar); o'quvchi topshiriqqa o'qituvchisining daraxti orqali kiradi
- [ ] Muharrir: tugmali panel (Markdown ichkarida), o'ngda daftar varag'ida jonli ko'rinish, LaTeX formulalar (KaTeX, self-hosted), rasm yuklash; qiyinchilik, toifa, ball
- [ ] Paket formati sxemasi va namuna paketlar (Dart, Flutter) sahifadan yuklab olinadi
- [ ] Topshiriqlarda qidiruv va filtr

**4-bosqich — algoritmik masalalar (acmp kabi)**
- [ ] Yangi tur: stdin/stdout testlari (kiruvchi va chiquvchi ma'lumot), vaqt va xotira limiti, namunaviy testlar sahifada; checker (aniq moslik, keyin maxsus checker)

**5-bosqich — statistika va yulduzlar**
- [ ] O'qituvchi va menejer uchun statistika: kim ko'p bajaryapti — guruh, yo'nalish, markaz kesimida
- [ ] O'quvchi topshiriqni yechgach yulduz qo'yadi; o'qituvchi reytingi — jami yulduzlar; menejerga o'qituvchilar reytingi

**6-bosqich — bosh sahifa va sayqal**
- [ ] Animatsiyali bosh sahifa (sayt haqida), butun sayt premium darajada; bo'sh joylardan unumli foydalanish

## Phase 2 — Sifat

- [x] Starter zip generatsiyasi va yuklab olish — Phase 1 da qilindi (`judge/packaging/starter.py`, o'quvchi topshiriq sahifasidan yuklab oladi)
- [ ] Flutter 2 bosqichli tekshiruv (PoC natijasiga qarab)
- [x] Kompilyatsiya xatolarini tozalash; hidden test xabarlarini yashirish — Phase 1 da qilindi (`judge/parsers/compile_message.py`; yashirin test xabari faqat `VIEW_FULL_LOG` rollariga)
- [x] Qayta tekshirish (rejudge) — Phase 1 da qilindi: o'qituvchi yechim sahifasidan, o'sha versiya bilan, eng past prioritetda
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
