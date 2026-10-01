# Online Home Work

IT o'quv markazlari uchun loyiha tekshiruv platformasi. O'qituvchi topshiriq, kutubxonalar va testlarni yuklaydi, o'quvchi yechimini yuboradi, platforma uni izolyatsiyalangan Docker konteynerda tekshirib, har bir test natijasini jonli ko'rsatadi.

**Holat:** Phase 0 (PoC): faqat judge, sayt hali yo'q. Reja: [docs/ROADMAP.md](docs/ROADMAP.md).

## Ishga tushirish

Talablar: [uv](https://docs.astral.sh/uv/), GNU Make, Docker.

```
make setup   # kutubxonalar va pre-commit hook'lari
make check   # lint + testlar, har commitdan oldin
make help    # barcha buyruqlar
```

## Hujjatlar

- [docs/SPEC.md](docs/SPEC.md): rollar, domen modeli, judge, xavfsizlik, konfiguratsiya
- [docs/UI.md](docs/UI.md): dizayn tizimi va UI matnlari
- [docs/decisions.md](docs/decisions.md): arxitektura qarorlari jurnali
