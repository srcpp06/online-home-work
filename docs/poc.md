# PoC o'lchovi: qanday ishga tushiriladi

Phase 0 ning oxirgi ikki o'lchovi uchun yo'riqnoma: avval lokal kompyuterda (x86_64), keyin Oracle A1 serverida (linux/arm64). Ikkalasida ham asosiy buyruq bitta — `make poc`.

## `make poc` nimani o'lchaydi

1. **Verdictlar va vaqtlar.** `examples/` dagi har bir topshiriq noldan yig'iladi (sovuq), keyin boshlang'ich kod va har bir yechim isitilgan image'da tekshiriladi. Har bir verdict `example.json` bilan solishtiriladi; vaqt va RAM cho'qqisi yoziladi.
2. **Kompilyatsiya keshi.** To'g'ri yechim isitilgan image'da va keshi o'chirilgan holda — isitish qancha tezlashtirishini ko'rsatadi.
3. **Ikki slot bir vaqtda.** Flutter (heavy) va Dart (fast) tekshiruvlari alohida va birga — `JUDGE_SLOTS=heavy:1,fast:1` serverni qanchalik sekinlashtiradi.
4. **Ikki bosqichli Flutter.** Flutter loyihasi ichida `dart test` ishlaydimi va qancha tez (SPEC §4, `two_stage`).

Natija Markdown jadval bo'lib ekranga chiqadi va `docs/poc/<arxitektura>-<sana>.md` ga saqlanadi. Biror verdict kutilganidan farq qilsa, buyruq xato kodi bilan tugaydi. Bir to'liq o'tish taxminan 6–10 daqiqa oladi (vaqt limiti holatlari limitni to'liq kutadi).

Mo'ljal uchun: Claude Code bulut sessiyasidagi natija — [`docs/poc/x86_64-cloud-sandbox-20261001.md`](poc/x86_64-cloud-sandbox-20261001.md).

## 1. Lokal kompyuter (CachyOS, x86_64)

Quyidagi buyruqlar Fish'da ham, bash'da ham ishlaydi.

Bir martalik tayyorgarlik:

```
sudo pacman -S --needed docker docker-buildx uv make git zip
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

Shundan keyin tizimdan chiqib qayta kiring (yoki kompyuterni qayta yoqing), aks holda `docker` sudo'siz ishlamaydi. Tekshirish: `docker run --rm hello-world`.

Loyihani olish va o'lchash:

```
git clone https://github.com/srcpp06/online-home-work.git
cd online-home-work
git switch claude/peaceful-darwin-r5riyt
make setup
make base-images
make check
make test-docker
make poc
```

- `make setup` — Python kutubxonalari, git hook'lar va `.env` (yo'q bo'lsa `.env.example` dan yaratiladi). Bir marta yetarli.
- `make base-images` — Dart va Flutter base image'larini shu kompyuter arxitekturasida yig'adi (Flutter ~5 daqiqa, internet kerak).
- `make test-docker` — hamma Docker testlari (~5 daqiqa); o'lchovdan oldin hammasi o'tishi kerak.
- Docker Hub `429 Too Many Requests` desa: `docker login` qiling yoki biroz kutib qayta urining.

## 2. Oracle Cloud A1 (linux/arm64)

Instance: Ampere A1, 2 OCPU, 12 GB RAM, Ubuntu 24.04 (aarch64) image, boot volume kamida 50 GB. Serverda standart shell — bash; buyruqlar shunga mos.

```
ssh ubuntu@<server-ip>
```

Swap (SPEC §8: kompilyatsiya cho'qqilari uchun zaxira):

```
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Docker, uv va vositalar:

```
sudo apt-get update
sudo apt-get install -y make git zip
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
curl -LsSf https://astral.sh/uv/install.sh | sh
exit
```

Qayta ulaning (`ssh ubuntu@<server-ip>`), keyin lokal kompyuterdagi kabi:

```
git clone https://github.com/srcpp06/online-home-work.git
cd online-home-work
git switch claude/peaceful-darwin-r5riyt
make setup
make base-images
make test-docker
make poc
make poc
```

`make poc` ikki marta ishlatiladi: ikkinchi o'tish natijalar qanchalik barqarorligini ko'rsatadi. Ko'proq takrorlash kerak bo'lsa: `uv run python -m scripts.poc --repeat 5`.

## Muammolar

| Xabar | Sabab va yechim |
|---|---|
| pacman: `failed retrieving file ... .sig ... 404` | Oyna (mirror) hali to'liq yangilanmagan: `sudo cachyos-rate-mirrors`, `sudo pacman -Syu`, keyin qayta o'rnating. `uv` uchun muqobil: `curl -LsSf https://astral.sh/uv/install.sh \| sh` va Fish'da `fish_add_path ~/.local/bin` |
| `error: uv is not installed` | `sudo pacman -S uv` (serverda: `curl -LsSf https://astral.sh/uv/install.sh \| sh`, keyin qayta ulaning) |
| `error: docker is not installed` | `sudo pacman -S docker docker-buildx` |
| `error: can't reach the Docker daemon` | `sudo systemctl enable --now docker` va `sudo usermod -aG docker $USER`, keyin tizimdan chiqib qayta kiring |
| `error: DART_VERSION is not set` (yoki boshqa sozlama) | `.env` eski: yetishmagan qatorni `.env.example` dan ko'chiring yoki `.env` ni o'chirib `make setup` qiling |
| `429 Too Many Requests` | Docker Hub limiti: `docker login` yoki biroz kutib qayta urining |

## Natijani yuborish

`docs/poc/` dagi yangi fayllarni commit qilib push qiling yoki matnini Claude'ga yuboring. Natijalar asosida qaror nuqtasida quyidagilar hal qilinadi:

| Savol | Qaysi jadvaldan |
|---|---|
| Profil RAM limitlari (`memory_mb`) | "Peak RAM" ustunlari, ayniqsa sovuq yig'ish va kesh o'chirilgan holat |
| Vaqt limitlari (`min_time_s`, `max_time_s`) | "Total" va "Cold build" |
| `two_stage` yoqilsinmi | "Two-stage Flutter" |
| Boshlang'ich `JUDGE_SLOTS` | "Two slots at once" — ARM'da 2 yadro, sekinlashuv shu yerda ko'rinadi |
| `JUDGE_RESERVED_MEMORY_MB` | Peak RAM + sayt va baza uchun zaxira |
