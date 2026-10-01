# Namuna: Savat (Dart)

Dart profili uchun namuna topshiriq. O'qituvchilar uni shablon sifatida yuklab olishi mumkin; platforma esa uni integration testlarda va `make poc` o'lchovida ishlatadi.

## Shart (o'quvchiga ko'rinadigan matn)

Internet do'kon savatini yozing. `Cart` klassi:

- `add(Product product)` — mahsulot qo'shadi. Shu nomli mahsulot savatda bo'lsa, faqat soni ortadi.
- `remove(String name)` — mahsulotni olib tashlaydi. Savatda yo'q mahsulot xato bermaydi.
- `itemCount` — savatdagi mahsulotlar soni (dona hisobida).
- `total` — jami narx, so'mda.
- `totalWithDiscount(int percent)` — chegirmadan keyingi narx. Foiz 0 dan 100 gacha; boshqa qiymatda `ArgumentError`.

## Paket tuzilishi

```
task/
├── pubspec.yaml         kutubxonalar: faqat o'qituvchi belgilaydi
├── ohw.yaml             ixtiyoriy sozlamalar
├── solution/lib/        o'qituvchi yechimi: image'ni isitadi, keyin o'chiriladi
├── starter/lib/         o'quvchiga beriladigan boshlang'ich kod
├── test/public/         ochiq testlar (o'quvchi ham ko'radi)
└── test/hidden/         yashirin testlar (faqat serverda)
```

Test nomi — o'quvchiga ko'rinadigan tavsif, shuning uchun u tushunarli o'zbekcha jumla bo'lsin. `group` nomi test nomining boshiga qo'shiladi: `group('Chegirma:')` ichidagi `test('0% da jami oʻzgarmaydi')` o'quvchiga "Chegirma: 0% da jami oʻzgarmaydi" bo'lib ko'rinadi. Testlar fayl nomi tartibida ishlaydi: avval ochiq, keyin yashirin.

## Yechimlar va kutilgan natija

| Yechim | Nima qilingan | Natija |
|---|---|---|
| `ok` | to'g'ri, o'qituvchinikidan boshqacha yozilgan | Qabul qilindi |
| `fail_logic` | bir xil mahsulot sonini qo'shmaydi | 3-testda xato |
| `compile_error` | `remove` yo'q | Kompilyatsiya xatosi |
| `timeout` | `total` cheksiz sikl | Vaqt limiti oshdi |
| `memory` | `add` xotirani to'ldiradi | Xotira limiti oshdi |
| `forbidden_import` | `dart:io` bilan soxta natija va `exit` | Rad etildi |
| `spoof_attempt` | test natijasiga o'xshash JSON chop etadi | 1-testda xato |

Aniq kutilgan natijalar `example.json` da.

## Ishga tushirish

```
cd task && zip -r ../task.zip . && cd ..
cd submissions/ok && zip -r ../../ok.zip lib && cd ../..
uv run python -m judge.cli run task.zip ok.zip --profile dart
```

Barcha namunalar birdaniga: repo ildizida `make poc`.
