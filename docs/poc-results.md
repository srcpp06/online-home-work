# Phase 0 o'lchovlari

Har bir o'lchovning to'liq hisoboti `docs/poc/` da; bu yerda — xulosa va qaror nuqtasi uchun takliflar. O'lchov vositasi va yo'riqnoma: `make poc`, [`docs/poc.md`](poc.md).

| O'lchov | Mashina | Hisobot | Holat |
|---|---|---|---|
| Lokal (rasmiy) | CachyOS, x86_64, 4 CPU, 11.5 GiB, cgroup v2, Docker 29.8.1 | [`x86_64-20261001-2059.md`](poc/x86_64-20261001-2059.md) | ✓ 17/17 verdict kutilgandek |
| Bulut sessiyasi (mo'ljal) | Ubuntu 24.04, x86_64, 4 CPU, 15.7 GiB, cgroup v1 | [`x86_64-cloud-sandbox-20261001.md`](poc/x86_64-cloud-sandbox-20261001.md) | ✓ 17/17 |
| Prod (rasmiy) | Oracle A1, linux/arm64, 2 OCPU, 12 GB | — | kutilmoqda |

Lokal o'lchov Flutter base image'ini haqiqiy Dockerfile'dan (`apt-get` qadami bilan, `debian:trixie-slim`) yig'di — bulut sessiyasida tekshirib bo'lmagan oxirgi qadam ham tasdiqlandi.

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

1. **Zanjir ishlaydi.** Paket → image → isitish → o'quvchi zipi → verdict; barcha yechim turlari, soxtalashtirish va taqiqlangan import kutilgandek.
2. **Isitilgan kesh — asosiy tezlashtirish.** Dart'da 10 marta, Flutter'da ~3 marta. Isitishsiz har bir yechim 11–13 s kompilyatsiya kutardi.
3. **RAM limitlari keragidan ancha katta.** Dart eng ko'pi 0.48 GB ishlatdi (limit 1 GB), Flutter 0.93 GB (limit 3 GB).
4. **Vaqt limitlari juda saxiy.** Limit sovuq isitish vaqtidan hisoblanadi (12.6 s × 2.5), tekshiruv esa iliq image'da 1–4 s davom etadi. Natijada cheksiz siklli yechim slotni Dart'da 32 s, Flutter'da 90 s band qiladi.
5. **Ikki bosqich texnik jihatdan ishlaydi, lekin cheklov bilan:** mantiq fayli `package:flutter` ni import qilmasligi shart. Iliq image'da butun Flutter tekshiruvi 2–4 s, ya'ni ikki bosqich hozircha sezilarli yutuq bermaydi.
6. **4 yadroli kompyuterda ikki slot deyarli halaqit bermaydi (1.1–1.2x).** Prod'da 2 yadro bor — asosiy savol ARM o'lchovida.

## Qaror nuqtasi uchun takliflar (ARM natijasidan keyin tasdiqlanadi)

| Sozlama | Hozir | Taklif | Sabab |
|---|---|---|---|
| `flutter.memory_mb` | 3072 | 1536 | cho'qqi 0.93 GB; xotira limiti tezroq ishlaydi; 12 GB serverga ko'proq heavy slot sig'adi |
| `dart.memory_mb` | 1024 | 1024 | cho'qqi 0.48 GB, zaxira yetarli |
| Vaqt limiti asosi | sovuq isitish × 2.5 | iliq qayta ishga tushirish × 2.5 | builder yechimni ikkinchi marta (iliq) ishga tushirib o'lchaydi; limit o'quvchi tekshiruviga mos bo'ladi |
| `dart.min_time_s` / `flutter.min_time_s` | 20 / 90 | ARM'dagi iliq vaqtga qarab, masalan 10 / 30 | cheksiz sikl slotni behuda band qilmasin |
| `two_stage` | yo'q | MVP'da o'chiq, Phase 2'da qayta ko'rib chiqiladi | iliq image'da yutuq kichik; o'qituvchiga qo'shimcha cheklov |
| `JUDGE_SLOTS` | heavy:1, fast:1 | ARM'dagi "Two slots at once" ga qarab | 2 yadroda sekinlashuv qanchaligini bilish kerak |
| `JUDGE_RESERVED_MEMORY_MB` | 3072 | 3072 | heavy 1536 + fast 1024 + 3072 = 5.6 GB ≤ 12 GB, ikkinchi heavy slotga joy qoladi |
