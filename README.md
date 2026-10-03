# Online Home Work

IT o'quv markazlari uchun loyiha tekshiruv platformasi. O'qituvchi topshiriq, kutubxonalar va testlarni yuklaydi, o'quvchi yechimini yuboradi, platforma uni izolyatsiyalangan Docker konteynerda tekshirib, har bir test natijasini jonli ko'rsatadi.

**Holat:** Phase 1 (MVP veb): judge tayyor (Phase 0), sayt skeleti bor. Reja: [docs/ROADMAP.md](docs/ROADMAP.md).

## Ishga tushirish

Talablar: [uv](https://docs.astral.sh/uv/), GNU Make, Docker va Docker Compose (CachyOS: `sudo pacman -S uv make docker docker-compose`).

```
make setup   # kutubxonalar, pre-commit hook'lari, .env (yangi maxfiy kalit bilan)
make dev     # PostgreSQL + migratsiyalar + CSS + sayt: http://127.0.0.1:8000/admin/
make check   # lint + testlar, har commitdan oldin
make help    # barcha buyruqlar
```

Admin uchun birinchi foydalanuvchi: `uv run python manage.py createsuperuser`. Dizayn tizimi: http://127.0.0.1:8000/ui/ (faqat dev).

`make dev` birinchi marta Tailwind CSS binarini GitHub'dan yuklab oladi (`.django_tailwind_cli/`, internet kerak).

`.env` eski bo'lsa (sayt `missing settings` deb to'xtasa): `rm .env` va `make setup`.

Tekshiruvlar uchun worker alohida terminalda: `make worker` (avval bir marta `make base-images`).

Serverga o'rnatish: [docs/deploy.md](docs/deploy.md) (`make deploy`).

## Hujjatlar

- [docs/SPEC.md](docs/SPEC.md): rollar, domen modeli, judge, xavfsizlik, konfiguratsiya
- [docs/UI.md](docs/UI.md): dizayn tizimi va UI matnlari
- [docs/decisions.md](docs/decisions.md): arxitektura qarorlari jurnali
- [docs/deploy.md](docs/deploy.md): serverga deploy, zaxira nusxalar, muammolar
