# Online Home Work

IT o'quv markazlari uchun loyiha tekshiruv platformasi. O'qituvchi topshiriq, kutubxonalar va testlarni yuklaydi, o'quvchi yechimini yuboradi, platforma uni izolyatsiyalangan Docker konteynerda tekshirib, har bir test natijasini jonli ko'rsatadi.

**Holat:** Phase 1 (MVP veb): judge tayyor (Phase 0), sayt skeleti bor. Reja: [docs/ROADMAP.md](docs/ROADMAP.md).

## Ishga tushirish

Talablar: [uv](https://docs.astral.sh/uv/), GNU Make, Docker va Docker Compose (CachyOS: `sudo pacman -S uv make docker docker-compose`).

```
make setup   # kutubxonalar, pre-commit hook'lari, .env (yangi maxfiy kalit bilan)
make dev     # PostgreSQL + migratsiyalar + sayt: http://127.0.0.1:8000/admin/
make check   # lint + testlar, har commitdan oldin
make help    # barcha buyruqlar
```

Admin uchun birinchi foydalanuvchi: `uv run python manage.py createsuperuser`.

`.env` eski bo'lsa (sayt `missing settings` deb to'xtasa): `rm .env` va `make setup`.

## Hujjatlar

- [docs/SPEC.md](docs/SPEC.md): rollar, domen modeli, judge, xavfsizlik, konfiguratsiya
- [docs/UI.md](docs/UI.md): dizayn tizimi va UI matnlari
- [docs/decisions.md](docs/decisions.md): arxitektura qarorlari jurnali
