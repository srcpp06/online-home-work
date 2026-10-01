# Namuna: Vazifalar ro'yxati (Flutter)

Flutter profili uchun namuna topshiriq: mantiq testlari va widget testlari bitta paketda. O'qituvchilar uni shablon sifatida yuklab olishi mumkin; platforma esa uni integration testlarda va `make poc` o'lchovida ishlatadi.

## Shart (o'quvchiga ko'rinadigan matn)

Vazifalar ro'yxati ilovasini yozing.

`TodoList` klassi:

- `add(String title)` — vazifa qo'shadi va `true` qaytaradi. Bo'sh yoki faqat bo'shliqdan iborat nom qo'shilmaydi (`false`).
- `toggle(int index)` — vazifani bajarilgan deb belgilaydi; qayta bosilsa belgi olinadi.
- `remaining` — bajarilmagan vazifalar soni.
- `filtered(Filter filter)` — `Filter.all`, `Filter.active` (bajarilmaganlar) yoki `Filter.done` (bajarilganlar).

`TodoApp` vidjeti:

- matn maydoni (`Key('title')`) va "Qoʻshish" tugmasi (`Key('add')`);
- har bir vazifa — katakchali qator (`CheckboxListTile`);
- sarlavhada "Qolgan: N".

Widget testlari elementlarni `Key` orqali topadi. Shuning uchun kalitlar shartda aniq ko'rsatilishi kerak.

## Paket tuzilishi

[Savat namunasi](../dart-cart/README.md) bilan bir xil. Flutter'da testlar `package:flutter_test` dan foydalanadi; mantiq testlari `test(...)`, widget testlari `testWidgets(...)` bilan yoziladi va hammasi `flutter test` bilan ishlaydi.

Faqat unit va widget testlar ishlaydi: emulyator ham, `integration_test` ham yo'q. Kamera, GPS kabi platforma kanallari testlarda mock qilinishi kerak.

## Yechimlar va kutilgan natija

| Yechim | Nima qilingan | Natija |
|---|---|---|
| `ok` | to'g'ri, boshqacha yozilgan (`ListView.builder`) | Qabul qilindi |
| `fail_logic` | bo'sh nomli vazifani ham qo'shadi | 3-testda xato |
| `fail_widget` | ro'yxat o'zgaradi, lekin `setState` yo'q — ekran yangilanmaydi | 4-testda xato |
| `compile_error` | `remaining` yo'q | Kompilyatsiya xatosi |
| `timeout` | `add` cheksiz sikl | Vaqt limiti oshdi |
| `memory` | `add` xotirani to'ldiradi | Xotira limiti oshdi |
| `forbidden_import` | `dart:io` bilan soxta natija va `exit` | Rad etildi |
| `spoof_attempt` | test natijasiga o'xshash JSON chop etadi | 2-testda xato |

Aniq kutilgan natijalar `example.json` da.

## Ishga tushirish

```
cd task && zip -r ../task.zip . && cd ..
cd submissions/ok && zip -r ../../ok.zip lib && cd ../..
uv run python -m judge.cli run task.zip ok.zip --profile flutter
```

Barcha namunalar birdaniga: repo ildizida `make poc`.
