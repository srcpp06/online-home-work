# UI — "Uy vazifasi daftari" dizayn tizimi

## 1. Konsepsiya

Klassik o'quv muhiti — katakli daftar, sinf jurnali, o'qituvchining qizil ruchkasi — zamonaviy, toza interfeysda. Bu skeuomorfizm emas: motivlar abstrakt va o'lchovli ishlatiladi, qolgan hamma joy sokin va intizomli.

Foydalanuvchilar: o'quvchilar (ko'pincha telefon yoki zaif kompyuter), o'qituvchilar (desktop, jadval bilan ko'p ishlaydi), markaz adminlari. Interfeysning asosiy vazifasi: "yechim qabul qilindimi, bo'lmasa qaysi testda va nega" degan savolga bir qarashda javob berish.

**Bitta yorqin element — "daftar sahifasi".** Boshqa joylarda dekor yo'q.

## 2. Tokenlar

Ranglar (`assets/source.css` dagi `:root` CSS o'zgaruvchilari; `make css` ularni `static/css/app.css` ga yig'adi, Tailwind'da `bg-desk`, `text-ink` kabi; boshqa ranglar yo'q):

| Token | Hex | Vazifasi |
|---|---|---|
| `--desk` | `#EEF1F6` | ilova foni (parta) |
| `--paper` | `#FFFFFF` | sahifalar, panellar |
| `--grid` | `#D9E6F2` | daftar kataklari, ajratgich chiziqlar |
| `--margin` | `#E2574C` | daftar hoshiya chizig'i |
| `--ink` | `#1D2B6B` | siyoh: sarlavhalar, asosiy tugmalar, havolalar, fokus |
| `--text` | `#1E2433` | asosiy matn |
| `--text-2` | `#5B6478` | ikkinchi darajali matn |
| `--pen-red` | `#C62828` | xato, rad etilgan |
| `--pass` | `#1B7A4B` | qabul qilindi |
| `--warn` | `#A86400` | vaqt yoki xotira limiti |

Shriftlar (self-hosted woff2; Latin, Latin Extended va Kirill subsetlari):
- Sarlavhalar: **Literata** (600). TeX Gyre Schola tekshirildi: unda `ʻ` (U+02BB), `ʼ` (U+02BC) va kirill yo'q, shuning uchun shu yerdagi zaxira tanlov ishlatildi.
- Interfeys va matn: **Golos Text** (400, 600).
- Kod va fayl yo'llari: **JetBrains Mono** (faqat shu yerda; kichik yorliqlar uchun monospace ishlatilmaydi); ligaturalar o'chiq — `=>` o'quvchi yozgandek ko'rinadi.
- Golos Text va JetBrains Mono'da `ʻ` yo'q: bu bitta harf "OHW Marks" dan (Inter'ning faqat `ʻ` glifi, ~1 KB) chiziladi. Testlar (`tests/apps/ui/test_fonts.py`) har bir shrift to'plami `ʻ ʼ`, lotin va kirillni o'zi chizishini tekshiradi.

O'lchamlar:
- Shrift shkalasi: 14 / 16 / 19 / 24 / 32 px. Matn qator balandligi 1.6, serif sarlavhalar 1.25.
- Topshiriq sharti matni kengligi ≤ 72ch.
- Daftar katagi: 24 px; daftar sahifasidagi qatorlar shu to'rga tekislanadi.
- Radius: kontrollar 6 px, panellar 10 px, daftar sahifasi 4 px.
- Jadvallarda raqamlar `font-variant-numeric: tabular-nums`.

## 3. Imzo komponent: daftar sahifasi

Topshiriq sharti va jonli natija sahifalarida ishlatiladi. Oq sahifa, och-ko'k katak to'r, chap tomonda qizil hoshiya chizig'i. Soya faqat shu komponentda bor — stol ustidagi qog'oz effekti. Boshqa panel va kartochkalarda soya yo'q.

Jonli natijada har bir test daftar qatori bo'lib yoziladi; hoshiya ustunida o'qituvchi belgisi paydo bo'ladi: ✓ (o'tdi, `--pass`) yoki ✗ (xato, `--pen-red`), joriy test yonida kichik "yozilmoqda" indikatori. Xato bergan test ostida uning izohi qizil ruchka rangida. Yakuniy natija — muhr uslubidagi belgi: qo'sh chiziqli ramka, −2° burilish, masalan "Qabul qilindi" yoki "3-testda xato".

```
┌────────────────────────────────────────────────┐
│    ┃ Savat hisobi                   Urinish 3  │
│ ✓  ┃ 1. Savat boʻsh boʻlsa jami 0 ga teng       │
│ ✓  ┃ 2. Mahsulot qoʻshilganda jami ortadi        │
│ ✗  ┃ 3. Chegirma 10% dan oshmasligi kerak        │
│    ┃    Kutilgan: 90, olingan: 85               │
│    ┃                      ╔══════════════╗      │
│    ┃                      ║ 3-testda xato ║     │
│    ┃                      ╚══════════════╝      │
└────────────────────────────────────────────────┘
```

Navbatda turganda: "Navbatda. Oldingizda 3 ta yechim." Tekshiruv boshlanganda qatorlar birma-bir paydo bo'ladi.

## 4. Jurnal (acmp uslubidagi natijalar jadvali)

Sinf jurnali ko'rinishi: ingichka chiziqlar, qatorlarda o'quvchilar, ustunlarda topshiriqlar (A, B, C… — to'liq nomi tooltip'da).

```
               A     B     C     D
Aliyev Vali    +    +2    −1
Karimova Sora  +1    +     …
Toshev Anvar        −3
```

- Katak: bo'sh — urinish yo'q; `+` yoki `+2` — qabul qilindi (undan oldin 2 ta xato); `−3` — 3 urinish, hali qabul yo'q; `…` — tekshirilmoqda.
- Qabul — och yashil fon, xato — och qizil fon; ma'no belgining o'zida ham bor (rangsiz ham tushunarli).
- Saralash: yechilganlar soni ↓, urinishlar ↑, ism.
- Sarlavha qatori va ism ustuni sticky; mobilda gorizontal scroll.
- Katak bosilsa: urinishlar ro'yxati → kod (Pygments) va natija.
- Kechikkan yechimlar alohida belgi bilan.

## 5. Boshqa komponentlar

- Holat belgisi: ikon + matn (Lucide, self-hosted SVG). Holat hech qachon faqat rang bilan berilmaydi.
- Fayl yuklash zonasi: drag & drop + tugma; yuklashdan oldin fayl nomi va hajmi, xato bo'lsa aniq sababi.
- Yuborish tugmasi cooldown paytida qolgan soniyalarni ko'rsatadi.
- Yon menyu rolga qarab; mobilda yuqori panel.
- Topshiriq yaratish ustasi: qadamlar ko'rsatkichi (bu haqiqiy ketma-ketlik bo'lgani uchun raqamlar o'rinli).
- Paket strukturasi tekshiruvi: topilgan va topilmagan elementlar ro'yxati (`pubspec.yaml` ✓, `test/hidden` — 5 ta fayl ✓, `solution/lib` ✗).

## 6. Sahifalar

O'quvchi:
- Topshiriqlarim: guruh bo'yicha, holat (yangi, urinilgan, qabul qilindi) va muddat bilan.
- Topshiriq: shart (daftar sahifasi), "Boshlangʻich loyihani yuklab olish", serverdagi Flutter versiyasi, yuborish zonasi, urinishlar tarixi.
- Jonli natija.

O'qituvchi:
- Guruhlarim → jurnal.
- Topshiriqlar → yaratish ustasi: profil (faqat o'z yo'nalishlari) → shart (Markdown + preview) → paket yuklash va struktura tekshiruvi → build logi (jonli) → test ro'yxati, limitlar → e'lon qilish.
- Guruhga biriktirish (ochilish vaqti, muddat, kechikishga ruxsat, urinishlar limiti).
- Yechim tafsiloti: kod, to'liq log, vaqtlar; "Qayta tekshirish".

Markaz admini: markaz menejerlari, o'qituvchilar, o'quvchilar, guruhlar; parolni tiklash; CSV import (Phase 2).

Markaz menejeri (faqat ko'rish): markaz bo'yicha umumiy ko'rinish — guruhlar, o'qituvchilar va ularning topshiriqlari; istalgan guruh jurnali; yechim tafsiloti (kod va test natijalari, log'siz). Tahrirlash, yaratish va "Qayta tekshirish" tugmalari unga ko'rsatilmaydi.

Superadmin: Django admin + `/system` (navbat, nodelar, o'rtacha kutish).

Kirish sahifasi: sokin, markazda daftar sahifasi ichidagi forma. Birinchi kirishda parolni almashtirish sahifasi.

## 7. Qoidalar

- Ishlatilmaydi: krem fon va terrakota aksent; bir xil soya ostidagi bir xil kartochkalar to'plami; gradient fonlar; ALL CAPS yorliqlar; `·` bilan ulangan meta qatorlar; tugma va havolalardagi `→`; har bir sarlavha ustidagi dekorativ yorliqlar.
- Animatsiya faqat bitta: test qatori natija kelganda paydo bo'lishi (150 ms, opacity + kichik siljish). `prefers-reduced-motion` da o'chadi.
- Mobil-first (o'quvchilar natijani telefonda ko'radi); jurnal desktop uchun optimallashtiriladi.
- Kirish imkoniyati: WCAG AA kontrast; ko'rinadigan fokus (2 px `--ink`); hamma narsa klaviatura bilan boshqariladi; jonli natija ro'yxatida `aria-live="polite"`.
- Dark mode — "Doska" mavzusi (to'q yashil-qora fon, bo'r rangidagi matn, xira katak to'r) — Phase 2.
- Har bir sahifani yaratgach skrinshot olib, shu hujjatga mosligini tekshir. Barcha komponentlar bitta sahifada: `/ui/` (faqat `DJANGO_DEBUG=true` da).

## 8. Matn yozish qoidalari

- UI — o'zbek tili, rasmiy lotin imlosi: `oʻ`, `gʻ` uchun `ʻ` (U+02BB), tutuq belgisi uchun `ʼ` (U+02BC). Masalan: "Oʻqituvchi", "Boshlangʻich", "Taʼlim".
- Tugmalar aniq harakatni aytadi: "Yechimni yuborish", "Topshiriq yaratish", "Guruhga biriktirish", "Qayta tekshirish", "Eʼlon qilish". Bir harakat butun oqimda bir xil nomlanadi.
- Xato xabari: nima bo'ldi + qanday tuzatiladi. Masalan: "Zip ichida lib/ papkasi topilmadi. Loyihangizning lib/ papkasini zip qilib qayta yuklang." Kechirim so'ralmaydi, noaniq so'zlar ishlatilmaydi.
- Bo'sh holat — harakatga taklif: "Hali topshiriq yoʻq. Birinchi topshiriqni yarating."
- Tizim ichki nomlari (job, lane, slot, manifest) foydalanuvchiga ko'rsatilmaydi (superadmin `/system` sahifasidan tashqari).

## 9. Atamalar

| Ichki nom | UI'da |
|---|---|
| task | Topshiriq |
| submission | Yechim |
| attempt | Urinish |
| group | Guruh |
| direction | Yoʻnalish |
| journal | Jurnal |
| starter | Boshlangʻich loyiha |
| public / hidden tests | Ochiq testlar / Yashirin testlar |
| deadline | Muddat |
| late | Kechikkan |
| queued | Navbatda |
| running | Tekshirilmoqda |
| accepted | Qabul qilindi |
| wrong_answer | N-testda xato |
| compile_error | Kompilyatsiya xatosi |
| time_limit | Vaqt limiti oshdi |
| memory_limit | Xotira limiti oshdi |
| runtime_error | Bajarilishda xato |
| rejected | Rad etildi |
| system_error | Tizim xatosi — urinish hisoblanmaydi |
| teacher / student / center admin / center manager | Oʻqituvchi / Oʻquvchi / Markaz admini / Markaz menejeri |
