# SPEC — Online Home Work

Bu hujjat platforma nima qilishi va qanday ishlashi kerakligini belgilaydi. Undan chetga chiqish kerak bo'lsa — avval Erkin bilan kelishib, `docs/decisions.md` ga yoz.

## 1. Rollar va ruxsatlar

Besh rol: superadmin (Erkin), markaz menejeri, markaz admini, o'qituvchi, o'quvchi. Kim kimni boshqaradi: superadmin — markazlar va menejerlar; menejer — adminlar; admin — o'qituvchi va o'quvchilar (`MANAGES`).

| Amal | Superadmin | Markaz menejeri | Markaz admini | O'qituvchi | O'quvchi |
|---|---|---|---|---|---|
| Markazlar va markaz menejerlari | ✓ | — | — | — | — |
| Markaz adminlari: qo'shish, tahrirlash, o'chirish, parolni tiklash | ✓ | o'z markazi | — | — | — |
| O'qituvchi va o'quvchilar: qo'shish, tahrirlash, o'chirish, parolni tiklash | ✓ | — | o'z markazi | — | — |
| Odamlarni ko'rish | ✓ | o'z markazi | o'qituvchi va o'quvchilar | o'z o'quvchilari | — |
| Guruhlar: yaratish, tahrirlash, o'quvchilarni biriktirish | ✓ | — | o'z markazi | — | — |
| Guruhlarni ko'rish (o'qituvchi, o'quvchilar) | ✓ | o'z markazi | o'z markazi | o'z guruhlari | — |
| Topshiriq yaratish, paket yuklash, guruhga biriktirish, qayta tekshirish | — | — | — | o'z guruhlari | — |
| Topshiriqlarni ko'rish: shart, sozlamalar, test nomlari (paket va yashirin test kodi emas) | ✓ | o'z markazi | — | o'z guruhlari | biriktirilganlari |
| Jurnal | ✓ | o'z markazi | — | o'z guruhlari | guruhda yoqilgan bo'lsa |
| Yechim kodi va test natijalari | ✓ | o'z markazi | — | o'z guruhlari | faqat o'ziniki |
| Tekshiruvchining to'liq logi | ✓ | — | — | o'z guruhlari | — |
| Yechim yuborish | — | — | — | — | biriktirilgan topshiriqlarga |
| Runner profillar, `/system` sahifasi | ✓ | — | — | — | — |

Markaz menejeri — markaz rahbari: o'z markazidagi hamma narsani ko'radi (o'qituvchilar topshiriqlari, guruhlar, jurnallar, yechimlar, keyin statistika va reytinglar) va faqat markaz adminlarini qo'shadi, tahrirlaydi. Boshqa hech narsani o'zgartirmaydi. Yashirin test kodi (paket) va to'liq log unga ko'rsatilmaydi: kuzatish uchun kerak emas. Menejerni superadmin yaratadi.

Markaz admini — odamlar bilan ishlaydi: o'qituvchi va o'quvchilarni qo'shadi, tahrirlaydi, guruhlarga biriktiradi. Topshiriqlar, yechimlar va jurnallarni ko'rmaydi.

Jadvalning kod ko'rinishi — `apps/accounts/permissions.py` (`ROLE_ACTIONS`, `can()`, `MANAGES`, `manages()`): `can()` rol bu turdagi amalni umuman bajara oladimi, `for_user()` qaysi obyektlarga — degan savolga javob beradi; har bir view ikkalasini tekshiradi.

Qoidalar:
- Markazlar to'liq ajratilgan (multi-tenant). Har bir queryset `for_user(user)` orqali filtrlanadi; ID bilan obyekt olish faqat `get_for_user_or_404()` orqali.
- Har bir URL uchun boshqa markaz foydalanuvchisi bilan IDOR testi yoziladi (parametrlangan test).
- Superadmin `/admin/` (Django admin) dan foydalanadi; u internetdan ochilmaydi — faqat serverdagi maxfiy eshik (Caddy, `127.0.0.1:8443`, SSH tunnel) orqali (`docs/deploy.md`, 12-bo'lim). Qolgan rollar saytdagi ikki eshikdan kiradi: o'quvchilar `/login/`, xodimlar `/staff/login/`.
- Foydalanuvchilarni yuqoridagi tartibda yaratishadi. Login — username, email shart emas. Birinchi kirishda parol almashtiriladi.
- O'qituvchiga yo'nalishlar biriktiriladi: `flutter`, `backend`, `frontend`. Topshiriq yaratishda faqat shu yo'nalishlarning profillari ko'rinadi, forma ham shunga moslashadi.

## 2. Domen modeli

- `Center`: name, slug, is_active.
- `User` (AbstractUser): role (`superadmin`, `center_admin`, `center_manager`, `teacher`, `student`), center (superadmin uchun null), directions (o'qituvchi uchun), must_change_password.
- `Group`: center, name, teacher, students (M2M), show_journal_to_students.
- `RunnerProfile`: slug, title, direction, lane (`fast` yoki `heavy`), base_image, config (JSON: student_paths, build va test buyruqlari, parser, limitlar, forbidden_imports, two_stage). Faqat superadmin tahrirlaydi.
- `Task`: center, author, title, statement_md, profile, is_archived.
- `TaskVersion`: task, number, package (fayl), sha256, status (`building`, `build_failed`, `ready`), image_tag, build_log, manifest (JSON: tartiblangan testlar — name, stage, visibility), starter (fayl), solution_wall_ms, warm_wall_ms, time_limit_s, memory_limit_mb, runtime_info (masalan, Flutter versiyasi).
- `Assignment`: task, group, opens_at, deadline, allow_late, max_attempts (null — cheksiz).
- `Submission`: assignment, student, task_version, archive, sha256, status (`queued`, `running`, `finished`), verdict, tests_total, tests_passed, failed_test_index, failed_test_name, public_message, internal_log, wall_ms, is_late, created_at, started_at, finished_at.
- `SubmissionTestResult`: submission, index, name, stage, visibility, status, duration_ms, message.
- `Job`: kind (`build`, `judge`, `rejudge`), lane, priority, status (`queued`, `running`, `done`, `failed`), task_version yoki submission, attempts, lease_expires_at, worker_node, last_error, vaqt belgilari.
- `WorkerNode`: name, arch, slots, last_heartbeat, version.

Verdictlar: `accepted`, `wrong_answer` (N-testda xato), `compile_error`, `time_limit`, `memory_limit`, `runtime_error`, `rejected` (noto'g'ri zip yoki taqiqlangan kod), `system_error`.

Urinishlar hisobi: `rejected` va `system_error` jarimaga kirmaydi, qolganlari kiradi. `allow_late=false` bo'lsa muddatdan keyin yuborish bloklanadi, `true` bo'lsa yechim `is_late` bilan belgilanadi. `max_attempts` ga yetilganda yuborish bloklanadi.

## 3. Judge — tekshiruvchi

### 3.1 Runner profillar

Yadro dasturlash tilini bilmaydi; tilga oid hamma narsa profilda. Yangi til = yangi Dockerfile + seed (+ kerak bo'lsa yangi parser), yadro kodi o'zgarmaydi.

| Profil | Lane | O'quvchi yuboradi | Bajarilishi | Parser |
|---|---|---|---|---|
| `dart` | fast | `lib/` | `dart test` | `dart_json` |
| `flutter` | heavy | `lib/` | 1-bosqich `dart test` (mantiq), 2-bosqich `flutter test` (widget) | `dart_json` |
| `backend-python` | fast | butun loyiha (kutubxonalarsiz) | `app` konteynerda o'quvchi serveri, `tester` konteynerda pytest + httpx (qora quti) | `ohw_jsonl` |
| `web-static` | fast | HTML/CSS/JS | bitta konteyner: statik server + pytest-playwright | `ohw_jsonl` |
| keyin: `backend-node`, `web-vite` | | | | |

Base image'lar (barchasi multi-arch): `dart` — rasmiy Dart image; `flutter` — o'zimizniki (§4); `pytest-http` — python slim + pytest + httpx; `playwright` — rasmiy Playwright Python image; `backend-python` app — python slim + o'qituvchi kutubxonalari.

### 3.2 O'qituvchi paketi (barcha profillar uchun bitta format)

```
task.zip
├── ohw.yaml          # ixtiyoriy: start_cmd, port, limitlar, allow_dart_io kabi sozlamalar
├── solution/         # o'qituvchi yechimi (dart/flutter uchun solution/lib/)
├── starter/          # ixtiyoriy: o'quvchiga beriladigan boshlang'ich kod
├── test/public/      # ochiq testlar — starter'ga qo'shiladi
├── test/hidden/      # yashirin testlar — faqat serverdagi image ichida
└── pubspec.yaml | requirements.txt | android/ | assets/ ...   # profilga xos fayllar
```

- **Kutubxonalarni faqat o'qituvchi belgilaydi.** O'quvchi zipidagi pubspec yoki requirements e'tiborsiz qoldiriladi. O'quvchi starter'dagi pubspec bilan ishlaydi, shuning uchun `package:<nom>/` importlari mos keladi.
- **Test nomi — o'quvchiga ko'rinadigan tavsif.** Dart: `test('…')` matni. pytest: docstring'ning birinchi qatori (bo'lmasa funksiya nomi). O'qituvchilarga testlarni o'zbekcha, tushunarli nomlash tavsiya qilinadi.
- Tartib: fayl nomi bo'yicha (`01_…`, `02_…`), fayl ichida e'lon qilingan tartibda; avval public, keyin hidden.
- Flutter'da bosqich avtomatik aniqlanadi: `package:test/` import qilgan test fayli → 1-bosqich (`dart test`), `package:flutter_test/` → 2-bosqich (`flutter test`).
- Har bir profil uchun `examples/` dan namuna paket o'qituvchiga yuklab olish uchun beriladi.

### 3.3 Image yig'ish (`build` job)

1. Paketni validatsiya qil (§3.6) va strukturani tekshir. Xatolar o'qituvchiga aniq ro'yxat ko'rinishida qaytariladi (masalan, "test/hidden papkasi topilmadi").
2. Profil base image'i ustiga build context yarat: kutubxonalar manifesti → o'rnatish (**internet faqat shu bosqichda**) → testlar → birlashtirilgan test fayllari.
3. Birlashtirish: `test/_ohw_all_test.dart` har bir test faylini prefiks bilan import qiladi va `group('<fayl_nomi>', f.main)` ichida chaqiradi (setUp/tearDown boshqa faylga o'tib ketmasligi uchun). Natijada kompilyatsiya bir marta bo'ladi — asosiy tezlashtirish. Parser ko'rsatishda shu guruh prefiksini olib tashlaydi. Flutter'da har bir bosqich uchun alohida birlashtirilgan fayl.
4. **Isitish va o'qituvchi yechimini tekshirish:** testlar o'qituvchi yechimi bilan ishga tushiriladi. Birorta test o'tmasa → `build_failed`, log o'qituvchiga ko'rsatiladi. Hammasi o'tsa: manifest (tartiblangan test nomlari), `solution_wall_ms`, runtime versiyasi yoziladi; kompilyatsiya keshi image ichida qoladi.
5. **Tayyor image'da qayta tekshirish:** o'qituvchi yechimi isitilgan image'da xuddi o'quvchi yechimidek tekshiriladi va `accepted` bo'lishi shart (aks holda `build_failed`). Vaqti — `warm_wall_ms`.
   Vaqt limiti: `clamp(ceil(warm_wall_s × 2.5), profil.min_time_s, profil.max_time_s)`; o'qituvchi o'zgartira oladi. Sabab (PoC): o'quvchi ham iliq image'da tekshiriladi; sovuq isitish vaqtidan olingan limit 6–18 marta katta chiqardi.
6. Starter zip: paket − `solution/` − `test/hidden/`, ustiga `starter/` qo'yiladi.
7. Image tegi deterministik: `ohw-task:<task_version_id>-<sha12>`. Nodeda image bo'lmasa, worker uni saqlangan paketdan o'zi qayta yig'adi — shuning uchun nodelar stateless.

### 3.4 Yechimni tekshirish (`judge` job)

1. Zipni validatsiya qil (§3.6). Ildizni o'zing top: o'quvchi butun loyihani zip qilsa ham `lib/` (yoki profil belgisi — `index.html`, kirish fayli) 3 qavat chuqurlikkacha qidiriladi. Keraksizlarni tashla: `__MACOSX`, `.git`, `build/`, `.dart_tool/`, `node_modules/`, `venv/`, `__pycache__`. Faqat `profile.student_paths` olinadi.
2. Statik tekshiruv (dart/flutter): `dart:io`, `dart:ffi`, `dart:isolate`, `dart:mirrors` va pubspec `dependencies` da yo'q `package:` importlari — `dev_dependencies` (`test`, `flutter_test`, `mocktail` …) ham taqiqlanadi (shu jumladan `export`, `part` va shartli importlar) → `rejected`, xabar: "Taqiqlangan import: dart:io — bu topshiriqda ruxsat etilmagan". `ohw.yaml` dagi `allow_dart_io: true` bilan ruxsat beriladi.
3. Image'dan konteyner yarat (limitlar §3.6), fayllarni `put_archive` bilan joyla (tar ichida uid/gid 1000), ishga tushir.
4. Chiqishni qatorma-qator o'qi → parser → umumiy event → har bir test tugashi bilan `SubmissionTestResult` yoz, test boshlanganda joriy test nomini yangila.
5. **Birinchi xatoda to'xtat:** konteynerni kill qil, qolgan testlar bajarilmaydi. Flutter'da 1-bosqich o'tmasa 2-bosqich boshlanmaydi.
6. Verdict: wall-time oshsa → `time_limit`; `State.OOMKilled` → `memory_limit`; test yuklanmasa yoki kompilyatsiya xatosi → `compile_error`; event oqimi manifestga mos kelmasa yoki to'liq bo'lmasa → `runtime_error`; birorta test o'tmasa → `wrong_answer`; hammasi o'tsa → `accepted`.
7. Konteyner va vaqtinchalik fayllar har doim o'chiriladi (`finally`).

Backend (`backend-python`) qo'shimchalari: `app` konteyneri `start_cmd` bilan ishga tushadi (standart: `uvicorn main:app --host 127.0.0.1 --port 8000`, `ohw.yaml` da o'zgartiriladi); port `startup_timeout_s` (standart 20) ichida ochilmasa → `runtime_error`, o'quvchiga o'z serverining log oxiri (qisqartirilgan) ko'rsatiladi. MVP'da baza faqat SQLite; har tekshiruv yangi konteyner, demak toza baza.

web-static qo'shimchalari: o'quvchi fayllari `/site` ga qo'yiladi; platforma conftest'i statik serverni `127.0.0.1` da ishga tushiradi va `page` fixture'ini `base_url` bilan beradi.

### 3.5 Parserlar va event formati

Umumiy event: `{type: start | pass | fail | done, index, name, stage, duration_ms, message}`.

- `dart_json`: `dart test --reporter json` va `flutter test --reporter json` (yoki `--machine` — PoC'da aniqlanadi) chiqishini o'qiydi: `testStart`, `testDone`, `error`, `print`, `done`. `hidden: true` bo'lgan testlar ("loading …" sintetik testlari) ro'yxatda ko'rsatilmaydi, lekin ularning xatosi `compile_error` ni bildiradi. `print` eventlari faqat o'qituvchi logiga boradi.
- `ohw_jsonl`: platformaning o'z kichik pytest plugini (`pytest_runtest_logreport` hook) JSON-lines chiqaradi. pytest `-x -p no:cacheprovider` bilan ishlaydi.
- Parserlar yozib olingan haqiqiy chiqishlar (fixture fayllar) bilan unit-test qilinadi.

### 3.6 Izolyatsiya va limitlar

O'quvchi kodi — ishonchsiz kod. Har bir tekshiruv konteyneri:
`network_mode=none`, `mem_limit` = `memswap_limit` (swap'siz), `nano_cpus`, `cpu_shares=JUDGE_CPU_SHARES` (sayt va baza CPU'da ustunlik oladi), `pids_limit=256`, `user=1000:1000`, `cap_drop=["ALL"]`, `security_opt=["no-new-privileges"]`, hajmi cheklangan `/tmp` tmpfs, chiqish hajmi limiti (`JUDGE_MAX_OUTPUT_KB`), wall-clock timeout. Build bosqichi ham vaqt va RAM limiti bilan ishlaydi — o'qituvchi paketi ham to'liq ishonchli emas.

Profil standartlari (`dart` va `flutter` — Phase 0 o'lchovlaridan keyin, `docs/poc-results.md`):

| Profil | RAM | CPU | Vaqt min–max |
|---|---|---|---|
| `dart` | 1024 MB | 1.0 | 15–120 s |
| `flutter` | 1536 MB | 1.5 | 30–300 s |
| `backend-python` | app 512 + tester 512 MB | 1.0 | 30–120 s |
| `web-static` | 1536 MB | 1.0 | 45–180 s |

Zip validator: hajm limiti (o'quvchi `SUBMISSION_MAX_ZIP_MB`, o'qituvchi `TASK_MAX_ZIP_MB`), ochilgandagi umumiy hajm va fayllar soni limiti (zip-bomb), `..` va absolyut yo'llar (zip-slip), symlinklar — rad etiladi.

### 3.7 Natijani soxtalashtirishga qarshi himoya

- O'quvchi test kodini ham, xom stdout'ni ham ko'rmaydi.
- Dart/Flutter'da `dart:io` taqiqlangani sababli o'quvchi kodi stdout'ga to'g'ridan-to'g'ri yoza olmaydi, faylni o'qiy olmaydi va `exit()` chaqira olmaydi; `print` esa JSON reporter ichida `print` event bo'lib qoladi.
- Natija faqat manifestdagi test nomlari aynan shu tartibda kelganda qabul qilinadi.
- Backend: o'quvchi serveri (`app`) va testlar (`tester`) alohida konteynerlarda; tester `network_mode=container:<app>` orqali `localhost` ga ulanadi. O'quvchi kodi test jarayoniga tegolmaydi.
- web-static: o'quvchi JS'i faqat brauzer ichida bajariladi.
- Integration testlarda `spoof_attempt` namunasi bo'ladi va u hech qachon `accepted` olmasligi tekshiriladi.

### 3.8 Kim nimani ko'radi

- O'quvchi: har bir test qatori (tartib raqami, nomi, holati, vaqti), xato bergan test nomi. Public test xatosida assertion xabari ham ko'rinadi; hidden test xatosida faqat nomi (o'qituvchi `show_hidden_messages` bilan o'zgartira oladi).
- Kompilyatsiya xatosida faqat xato matni; `test/hidden/` dagi yo'l va kod parchalari olib tashlanadi, masalan: "Kodingiz topshiriqdagi interfeysga mos emas: The method 'total' isn't defined for the type 'Cart'". Maksimal 2000 belgi.
- O'qituvchi: hamma narsa — to'liq log, kod, stdout, vaqtlar.

### 3.9 Navbat, slotlar, masshtablash

- Job olish: tranzaksiya ichida `select_for_update(skip_locked=True)`, tartib `priority DESC, created_at`.
- `JUDGE_SLOTS=heavy:1,fast:1`: `fast` slotlar faqat fast joblarni oladi; `heavy` slotlar avval heavy, bo'lmasa fast oladi. Shunda tez tekshiruvlar Flutter ortida kutib qolmaydi.
- Slot — worker jarayonidagi thread. Bo'sh slot navbatni har `JUDGE_POLL_INTERVAL_S` da tekshiradi (keyin LISTEN/NOTIFY).
- Lease: ishlayotgan job har 10 s da `lease_expires_at` ni uzaytiradi. Muddati o'tgan joblar navbatga qaytariladi (eng ko'pi 3 urinish, keyin `system_error`). Worker qulasa ham yechim yo'qolmaydi.
- `WorkerNode` heartbeat yozadi. `/system`: lane bo'yicha navbat uzunligi, nodelar holati, oxirgi soatdagi o'rtacha kutish vaqti.
- Worker ishga tushganda tekshiradi: `heavy_slots × heavy profillar maks. RAM + fast_slots × fast profillar maks. RAM + JUDGE_RESERVED_MEMORY_MB ≤ jami RAM`. Sig'masa — aniq xabar bilan to'xtaydi.
- Adolat: bitta o'quvchining bir vaqtda `SUBMISSION_MAX_ACTIVE_PER_STUDENT` (1) ta faol yechimi bo'ladi; bitta topshiriqqa `SUBMISSION_COOLDOWN_S` (60) soniyada bir marta yuboriladi. Rejudge va build joblarining prioriteti alohida sozlanadi (rejudge — eng past).
- Navbatdagi o'quvchiga o'rni ko'rsatiladi: "Oldingizda 3 ta yechim".
- Gorizontal masshtab: yangi nodeda faqat worker ishga tushiriladi (`JUDGE_NODE_NAME`, o'sha `DATABASE_URL`, umumiy storage). Image'lar kerak bo'lganda o'sha nodeda yig'iladi.

## 4. Flutter optimizatsiyasi

- Base image: `debian:trixie-slim` + `git clone --depth 1 --branch $FLUTTER_VERSION` (git clone multi-arch uchun; Dart SDK arxitekturaga mos o'zi yuklanadi). Yig'ishda dummy loyihada `flutter test` bir marta ishlatiladi — kerakli artefaktlar (`flutter_tester` va boshqalar) keshlanadi. Analytics va CLI animatsiyalari o'chiriladi.
- Ko'p ishlatiladigan paketlar (`profiles/flutter/common_packages.txt`: provider, bloc, flutter_bloc, equatable, dio, http, go_router, get_it, mocktail …) base image pub keshiga oldindan yuklanadi — o'qituvchi topshiriq yig'ishi tezlashadi.
- Test buyruqlari: `--no-pub`, `--concurrency=1`, bitta birlashtirilgan fayl, isitilgan kesh.
- 2 bosqichli tekshiruv: mantiq `dart test` bilan (soniyalar), widget `flutter test` bilan faqat mantiq o'tsa. Agar PoC'da `dart test` Flutter loyiha ichida ishlamasa — profil konfiguratsiyasida `two_stage: false`. **PoC qarori: MVP'da `two_stage` yo'q** — iliq image'da butun Flutter tekshiruvi ~5 s, mantiq fayli esa `package:flutter` ni import qilmasligi kerak bo'lardi; Phase 2'da qayta ko'riladi.
- Faqat unit va widget testlar; integration_test va emulyator yo'q. Platform channel'lar (kamera, GPS va h.k.) testlarda mock qilinadi — buni o'qituvchilar yo'riqnomasida yoz.
- Topshiriq sahifasida serverdagi Flutter versiyasi ko'rsatiladi, o'quvchi o'z kompyuterida shu versiyadan foydalanishi uchun.

## 5. Veb xavfsizligi

- Yuklangan fayllar (`MEDIA_ROOT`) faqat ruxsatni tekshiradigan view orqali beriladi.
- Markdown har doim `nh3` bilan tozalanadi.
- django-axes bilan login urinishlari cheklanadi: bitta login + IP juftligiga 10 ta xato, keyin 15 daqiqa blok (markazda butun sinf bitta IP ortida, shuning uchun faqat IP bo'yicha bloklanmaydi); CSRF yoqilgan; prod'da `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS.
- Hamma sahifa standart bo'yicha login talab qiladi (`LoginRequiredMiddleware`); ochiq sahifa view'da `@login_not_required` bilan aniq belgilanadi.
- Yuklash hajmi limiti Caddy (`request_body max_size`) va Django darajasida.
- Sirlar faqat `.env` da; repoda faqat `.env.example`.
- Admin harakatlari jurnali (audit log) — Phase 2.

## 6. Konfiguratsiya (`.env`)

Quyida prod qiymatlari. `.env.example` da dev qiymatlari turadi (`DJANGO_DEBUG=true`, `localhost` dagi `compose.dev.yml` bazasi, `MEDIA_ROOT=media`); `make setup` `.env` ni yangi `DJANGO_SECRET_KEY` bilan yaratadi.

```
DJANGO_SECRET_KEY=
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=
DATABASE_URL=postgres://ohw:ohw@db:5432/ohw
TIME_ZONE=                          # O'zbekiston vaqti (UTC+5)
MEDIA_ROOT=/data/media

JUDGE_NODE_NAME=node-1
JUDGE_SLOTS=heavy:1,fast:1          # server kuchaytirilganda faqat shu o'zgaradi
JUDGE_RESERVED_MEMORY_MB=3072
JUDGE_CPU_SHARES=512
JUDGE_RUNTIME=runc                  # keyin: runsc (gVisor)
JUDGE_POLL_INTERVAL_S=1
JUDGE_LEASE_S=60
JUDGE_MAX_OUTPUT_KB=512

SUBMISSION_COOLDOWN_S=60
SUBMISSION_MAX_ACTIVE_PER_STUDENT=1
SUBMISSION_MAX_ZIP_MB=5
SUBMISSION_MAX_UNPACKED_MB=20       # zip ochilgandagi hajm (faqat olinadigan fayllar)
SUBMISSION_MAX_FILES=500
TASK_MAX_ZIP_MB=50
TASK_MAX_UNPACKED_MB=200
TASK_MAX_FILES=5000

DART_VERSION=3.13.5                 # dart base image: rasmiy dart:<versiya>
FLUTTER_VERSION=3.47.5              # aniq stable versiya
```

## 7. Testlash strategiyasi

- `judge/core`, `judge/parsers`, `judge/packaging`: Docker'siz unit testlar. Zip validator uchun zararli zip fixture'lari: zip-slip, symlink, zip-bomb, absolyut yo'l.
- `examples/<profil>-<nom>/` har birida `task/` paket va `submissions/` ichida: `ok`, `fail_logic`, `fail_widget` (flutter), `compile_error`, `timeout`, `memory`, `forbidden_import`, `spoof_attempt`. Integration testlar (marker `docker`) har biri kutilgan verdictni olishini tekshiradi.
- Web: pytest-django — ruxsatlar matritsasi, har URL uchun IDOR testlari, yuborish oqimi (soxta in-memory runner bilan).
- Worker: lease va reaper mantiqi, slot/lane tanlash, xotira sig'ishi tekshiruvi — unit testlar.

## 8. Deploy

- `compose.prod.yml`: `caddy` (avtomatik HTTPS), `web` (gunicorn, 2–3 worker), `worker` (`/var/run/docker.sock` ulangan, `web` bilan bitta image), `db` (PostgreSQL 17). Volume'lar: `pgdata`, `media`, `caddy_data`.
- Oracle'da 80/443 portlari ham VCN Security List'da, ham server ichidagi firewall'da (iptables/firewalld) ochilishi kerak.
- 4 GB swap — kompilyatsiya cho'qqilari uchun xavfsizlik zaxirasi.
- Har kecha `pg_dump` zaxira nusxasi (keyin Object Storage'ga).
- Disk: arxivlangan topshiriqlarning image'lari tozalanadi, `docker image prune` muntazam ishlaydi.
- Always Free instance uzoq vaqt deyarli bo'sh tursa, Oracle uni to'xtatishi mumkin — ta'til paytlarida kuzatib tur.
- Deploy jarayoni `docs/deploy.md` da qadam-baqadam yoziladi.
