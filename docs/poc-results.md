# Phase 0 o'lchovlari

Har bir o'lchovning to'liq hisoboti `docs/poc/` da; bu yerda — xulosa va qaror nuqtasi uchun takliflar. O'lchov vositasi va yo'riqnoma: `make poc`, [`docs/poc.md`](poc.md).

| O'lchov | Mashina | Hisobot | Holat |
|---|---|---|---|
| Prod (rasmiy) | Oracle A1, linux/arm64, 2 OCPU, 11.6 GiB, Ubuntu 24.04, cgroup v2, Docker 29.8.2 | [`aarch64-20261003-0710.md`](poc/aarch64-20261003-0710.md), [`aarch64-20261003-0716.md`](poc/aarch64-20261003-0716.md) | ✓ ikki o'tish, har biri 17/17 |
| Lokal (rasmiy) | CachyOS, x86_64, 4 CPU, 11.5 GiB, cgroup v2, Docker 29.8.1 | [`x86_64-20261001-2059.md`](poc/x86_64-20261001-2059.md) | ✓ 17/17 verdict kutilgandek |
| Bulut sessiyasi (mo'ljal) | Ubuntu 24.04, x86_64, 4 CPU, 15.7 GiB, cgroup v1 | [`x86_64-cloud-sandbox-20261001.md`](poc/x86_64-cloud-sandbox-20261001.md) | ✓ 17/17 |

Lokal o'lchov Flutter base image'ini haqiqiy Dockerfile'dan (`apt-get` qadami bilan, `debian:trixie-slim`) yig'di — bulut sessiyasida tekshirib bo'lmagan oxirgi qadam ham tasdiqlandi. ARM serverda `make test-docker` ham to'liq o'tdi (117 test).

## Prod natijalari (Oracle A1, arm64)

Har katakda: 1-o'tish / 2-o'tish.

| | Dart (`dart-cart`) | Flutter (`flutter-todo`) |
|---|---|---|
| Sovuq yig'ish (pub get + isitish) | 15.9 / 15.6 s | 21.9 / 21.3 s |
| O'qituvchi yechimi (isitish, sovuq kompilyatsiya) | 11.8 / 11.6 s | 13.6 / 13.5 s |
| Isitilgan image'da tekshirish (to'g'ri yechim) | 1.6 / 1.6 s | 5.0 / 4.9 s |
| Birinchi xatoda to'xtash (3-test) | 1.6 / 1.5 s | 3.3 / 3.3 s |
| Kompilyatsiya xatosi | 1.4 / 1.4 s | 2.5 / 2.4 s |
| Rad etilgan zip (taqiqlangan import) | 0.0 s, konteyner ochilmaydi | 0.0 s |
| Hisoblangan vaqt limiti | 30 s | 90 s (profil minimumi) |
| RAM: tekshiruv / sovuq kompilyatsiya (ikki o'tishning eng kattasi) | 250 / 471 MB | 683 / 935 MB |
| Xotira limiti ishlagan vaqt | 3.1 / 3.2 s (1024 MB) | 12.2 / 12.6 s (3072 MB) |
| Kesh foydasi (keshsiz → isitilgan) | 11.6 → 1.5 s, 7.8x / 7.9x | 13.0 → 4.5 s / 13.3 → 4.5 s, 2.9x |
| Ikki slot birga (sekinlashuv) | 1.14x / 1.14x | 1.10x / 1.09x |

Ikki bosqichli Flutter (Flutter loyihasi ichida `dart test`):

| Tekshiruv | Natija | Vaqt |
|---|---|---|
| `dart test`, Flutter importisiz mantiq (birinchi marta) | o'tdi | 8.0 / 8.1 s |
| `dart test`, xuddi shu, kesh iliq | o'tdi | 1.0 / 1.0 s |
| `flutter test`, xuddi shu mantiq testi | o'tdi | 12.2 / 12.7 s |
| `dart test`, mantiq fayli Flutter import qiladi | yiqildi | 7.7 / 6.9 s |

Ikki o'tish orasidagi farq 3% dan oshmaydi — o'lchov barqaror.

## Lokal natijalar (x86_64)

| | Dart (`dart-cart`) | Flutter (`flutter-todo`) |
|---|---|---|
| Sovuq yig'ish (pub get + isitish) | 17.8 s | 18.2 s |
| O'qituvchi yechimi (isitish, sovuq kompilyatsiya) | 12.6 s | 11.2 s |
| Isitilgan image'da tekshirish (to'g'ri yechim) | 1.6 s | 4.0 s |
| Birinchi xatoda to'xtash | 1.5 s (3-test) | 2.6 s (3-test) |
| Kompilyatsiya xatosi | 1.2 s | 2.1 s |
| Rad etilgan zip (taqiqlangan import) | 0.0 s, konteyner ochilmaydi | 0.0 s |
| Hisoblangan vaqt limiti | 32 s | 90 s (profil minimumi) |
| RAM: tekshiruv / sovuq kompilyatsiya | 250 / 476 MB | 680 / 927 MB |
| Xotira limiti ishlagan vaqt | 2.5 s (1024 MB) | 11.0 s (3072 MB) |
| Kesh foydasi (keshsiz → isitilgan) | 12.5 → 1.2 s, 10.0x | 11.1 → 3.9 s, 2.8x |
| Ikki slot birga (sekinlashuv) | 1.19x | 1.12x |

Ikki bosqichli Flutter (Flutter loyihasi ichida `dart test`):

| Tekshiruv | Natija | Vaqt |
|---|---|---|
| `dart test`, Flutter importisiz mantiq (birinchi marta) | o'tdi | 7.7 s |
| `dart test`, xuddi shu, kesh iliq | o'tdi | 0.8 s |
| `flutter test`, xuddi shu mantiq testi | o'tdi | 11.6 s |
| `dart test`, mantiq fayli Flutter import qiladi | yiqildi | 7.0 s |

Bulut sessiyasi natijalari shu tartibda (kesh 8.8x / 3.0x, RAM bir xil darajada); yagona katta farq — Flutter xotira limiti 21–25 s (cgroup v1) o'rniga 11 s.

## Xulosalar

1. **Zanjir prod arxitekturasida ishlaydi.** Paket → image → isitish → o'quvchi zipi → verdict; ARM'da ham barcha yechim turlari, soxtalashtirish va taqiqlangan import kutilgandek, ikki o'tishda bir xil.
2. **ARM (2 OCPU) lokal x86 (4 CPU) bilan deyarli teng.** Dart bir xil, isitilgan Flutter tekshiruvi ~20% sekinroq (4.0 → 4.9 s). Har bir slot 1–1.5 CPU bilan cheklangan, shuning uchun yadrolar soni emas, bitta yadro tezligi muhim.
3. **Isitilgan kesh — asosiy tezlashtirish.** Dart'da 8–10 marta, Flutter'da ~3 marta. Isitishsiz har bir yechim 11–13 s kompilyatsiya kutardi.
4. **RAM limitlari keragidan ancha katta.** Dart eng ko'pi 0.47 GB ishlatdi (limit 1 GB), Flutter 0.94 GB (limit 3 GB).
5. **Vaqt limitlari juda saxiy.** Limit sovuq isitish vaqtidan hisoblanadi (~12 s × 2.5), tekshiruv esa iliq image'da 1.5–5 s davom etadi. Natijada cheksiz siklli yechim slotni Dart'da 30 s, Flutter'da 90 s band qiladi.
6. **Ikki bosqich texnik jihatdan ishlaydi, lekin cheklov bilan:** mantiq fayli `package:flutter` ni import qilmasligi shart. Iliq image'da butun Flutter tekshiruvi ~5 s, ya'ni ikki bosqich sezilarli yutuq bermaydi.
7. **Prod'dagi 2 yadroda ikki slot deyarli halaqit bermaydi (1.09–1.14x).** `JUDGE_SLOTS=heavy:1,fast:1` xavfsiz.

## Qaror nuqtasi uchun takliflar (Erkin tasdig'ini kutmoqda)

| Sozlama | Hozir | Taklif | Sabab |
|---|---|---|---|
| `flutter.memory_mb` | 3072 | 1536 | cho'qqi 0.94 GB (ikki mashinada ham), ~1.6x zaxira; xotira limiti tezroq ishlaydi; 12 GB serverga ko'proq heavy slot sig'adi |
| `dart.memory_mb` | 1024 | 1024 | cho'qqi 0.47 GB, zaxira yetarli |
| Vaqt limiti asosi | sovuq isitish × 2.5 | iliq qayta ishga tushirish × 2.5 | builder tayyor image'da o'qituvchi yechimini yana bir marta o'quvchi tekshiruvidek ishlatadi (+2–5 s yig'ish); limit o'quvchi tekshiruviga mos bo'ladi va tayyor image yechimni qabul qilishi isbotlanadi |
| `dart.min_time_s` / `flutter.min_time_s` | 20 / 90 | 15 / 30 | ARM'da iliq tekshiruv 1.8 / 5.3 s (ikki slot birga); keshsiz holat ham (11.6 / 13.3 s) limitga sig'adi — to'g'ri yechim kesh ishlamasa ham `time_limit` olmaydi; cheksiz sikl slotni 15 / 30 s band qiladi |
| `max_time_s`, `cpus` | 120 / 300, 1.0 / 1.5 | o'zgarmaydi | 2 yadroda ham ikki slot 1.1x sekinlashadi |
| `two_stage` | yo'q | MVP'da o'chiq, Phase 2'da qayta ko'rib chiqiladi | iliq image'da yutuq kichik; o'qituvchiga qo'shimcha cheklov |
| `JUDGE_SLOTS` | heavy:1, fast:1 | heavy:1, fast:1 | ARM'da sekinlashuv 1.09–1.14x; yuklama oshsa `fast:2` faqat konfiguratsiya bilan sinaladi |
| `JUDGE_RESERVED_MEMORY_MB` | 3072 | 3072 | heavy 1536 + fast 1024 + 3072 = 5.6 GB ≤ 11.6 GiB, ikkinchi heavy slotga joy qoladi |
