# Arxitektura qarorlari jurnali

Format: sana — qaror. Sabab. Yangi qarorlar oxiriga qo'shiladi; eski qaror o'zgarsa, yangisida qaysi biri bekor qilinganini yoz.

- **2026-10-01 — Tekshiruv faqat serverda.** O'quvchi kompyuterida faqat ochiq testlar ishlatiladi (starter orqali), rasmiy verdict faqat serverdan. Sabab: mijoz qurilmasiga ishonib bo'lmaydi — natijani soxtalashtirish va yashirin testlarni o'qish oson.
- **2026-10-01 — Kutubxonalar topshiriq image'iga bir marta o'rnatiladi.** O'quvchi kutubxona qo'sha olmaydi. Sabab: har yechim uchun `pub get` sekin; tekshiruv internetsiz ishlaydi.
- **2026-10-01 — Stack: Django monolit + HTMX + PostgreSQL navbat.** Sabab: auth, admin, ORM tayyor; Redis/Celery'siz kamroq servis; sahifalar zaif kompyuterlarda ham yengil.
- **2026-10-01 — Tayyor judge tizimlari (Judge0, DMOJ va h.k.) ishlatilmaydi.** Sabab: ular stdin/stdout dasturlari uchun; loyiha darajasidagi test freymvorklari, kutubxonalar va test-ma-test jonli natija uchun mos emas.
- **2026-10-01 — Judge yadrosi tilni bilmaydi, tilga oid hamma narsa runner profilda.** Sabab: Flutter, Dart, backend va frontend bitta yadro bilan; yangi til yadroga tegmasdan qo'shiladi.
- **2026-10-01 — Backend qora quti usulida tekshiriladi.** O'quvchi serveri va testlar alohida konteynerlarda, umumiy network namespace orqali. Sabab: testlar o'quvchi tiliga bog'liq emas; o'quvchi kodi test jarayoniga tegolmaydi.
- **2026-10-01 — Flutter tezligi: birlashtirilgan test fayli, isitilgan kesh, ikki bosqich (`dart test` → `flutter test`).** Sabab: asosiy vaqt kompilyatsiyaga ketadi; mantiq xatolari og'ir widget kompilyatsiyasisiz aniqlanadi. Ikki bosqich PoC natijasiga bog'liq.
- **2026-10-01 — Server: Oracle Always Free A1, linux/arm64, 2 OCPU / 12 GB.** Boshida 1 `heavy` + 1 `fast` slot. Parallel tekshiruvlar soni faqat `JUDGE_SLOTS` va qo'shimcha worker nodelar bilan oshiriladi.
- **2026-10-01 — UI konsepsiyasi "Uy vazifasi daftari".** Katakli daftar, qizil hoshiya, o'qituvchi belgilari va muhr; jurnal acmp uslubida. Tafsilotlar: `docs/UI.md`.
