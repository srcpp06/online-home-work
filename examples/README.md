# Namuna topshiriqlar

Har bir papka — bitta runner profili uchun to'liq namuna:

| Papka | Profil | Nima tekshiriladi |
|---|---|---|
| [`dart-cart`](dart-cart/README.md) | `dart` | sof mantiq: savat, chegirma |
| [`flutter-todo`](flutter-todo/README.md) | `flutter` | mantiq + widget: vazifalar ro'yxati |

Namunalar uch ish bajaradi:

1. **O'qituvchilar uchun shablon.** `task/` — platformaga yuklanadigan paket tuzilishi.
2. **Integration testlar.** `tests/examples/` har bir yechim `example.json` dagi natijani olishini tekshiradi (`make test-docker`).
3. **O'lchov.** `make poc` hamma namunani judge orqali o'tkazadi va vaqtlarni Markdown jadval qilib chiqaradi.

## Tuzilish

```
<nom>/
├── example.json        profil va har bir yechim uchun kutilgan natija
├── task/               o'qituvchi paketi (zip qilinib yuklanadi)
└── submissions/<tur>/  o'quvchi yechimlari: faqat lib/
```

Yechim turlari (SPEC §7): `ok`, `fail_logic`, `fail_widget` (Flutter), `compile_error`, `timeout`, `memory`, `forbidden_import`, `spoof_attempt`. `task/starter/` ham tekshiriladi: boshlang'ich kod kompilyatsiya bo'lishi va 1-testda yiqilishi kerak.

Yangi namuna qo'shish: shu tuzilishda papka yarating va `example.json` yozing — test va `make poc` uni o'zi topadi.
