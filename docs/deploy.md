# Serverga deploy

Bu qo'llanma Phase 0 dagi Oracle Cloud serveri (Ampere A1, Ubuntu, arm64) uchun yozilgan; boshqa Linux serverda ham xuddi shunday. Buyruqlar **serverda** (`ssh` bilan kirgandan keyin) bajariladi. Serverdagi shell — bash.

Natija: `https://<domen>` da sayt, orqada 5 ta konteyner (`compose.prod.yml`):

| Servis | Vazifasi |
|---|---|
| `caddy` | HTTPS (Let's Encrypt sertifikatini o'zi oladi va yangilaydi), so'rovlarni `web` ga uzatadi |
| `web` | Django + gunicorn (3 ta jarayon) |
| `worker` | `judge_worker`: image yig'adi va yechimlarni tekshiradi; Docker bilan faqat u gaplashadi |
| `db` | PostgreSQL 17 |
| `migrate` | har deploy'da bir marta: migratsiyalar va runner profillar, keyin to'xtaydi |

Ma'lumotlar Docker volume'larida: `pgdata` (baza), `media` (paketlar va yechimlar), `caddy_data` (sertifikatlar). `docker compose down` ularni o'chirmaydi; `down -v` o'chiradi — **prod'da hech qachon `-v` ishlatma**.

## 1. Domen

Saytga domen kerak: Caddy HTTPS sertifikatini domen uchun oladi.

- Domen bor bo'lsa: DNS'da `A` yozuvi qo'sh — masalan `ohw.markaz.uz` → serverning ommaviy IP manzili. Tekshirish: `ping ohw.markaz.uz` server IP'sini ko'rsatishi kerak.
- Hozircha domen yo'q bo'lsa: `sslip.io` dan foydalan. IP `129.154.10.20` bo'lsa, domen `129-154-10-20.sslip.io` — u o'zi shu IP'ga ishora qiladi, sozlash kerak emas. Keyin haqiqiy domenga o'tish: `.env` da `SITE_DOMAIN` va `DJANGO_ALLOWED_HOSTS` ni o'zgartirib, `make deploy`.

## 2. Portlar: 80 va 443

Oracle'da port ikki joyda yopiq, ikkalasida ham ochish kerak.

1. **Oracle konsoli:** Networking → Virtual Cloud Networks → serverning VCN'i → Subnet → Security List → *Add Ingress Rules*: Source CIDR `0.0.0.0/0`, IP Protocol TCP, Destination Port `80`. Xuddi shunday `443` uchun (ixtiyoriy: `443` UDP — HTTP/3).
2. **Server ichidagi firewall** (Oracle'ning Ubuntu image'ida iptables):

   ```
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
   sudo netfilter-persistent save
   ```

## 3. Swap (4 GB)

Kompilyatsiya cho'qqilarida xotira yetmay qolsa, yadro jarayonni o'ldirmasligi uchun zaxira:

```
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Tekshirish: `free -h` da `Swap: 4.0Gi`.

## 4. Kod va base image'lar

Docker va repo Phase 0 da o'rnatilgan. Kodni yangila:

```
cd ~/online-home-work
git pull
```

Base image'lar (`ohw-base-dart`, `ohw-base-flutter`) PoC paytida yig'ilgan. Borligini tekshir:

```
docker images | grep ohw-base
```

Ikkalasi `.env` dagi versiyalar bilan (`DART_VERSION`, `FLUTTER_VERSION`) ro'yxatda bo'lishi kerak. Yo'q bo'lsa yoki versiya o'zgargan bo'lsa: `make base-images` (Flutter ~15–20 daqiqa).

## 5. `.env` (prod sozlamalari)

PoC'dagi `.env` dev uchun edi (`DJANGO_DEBUG=true`). Uni chetga olib, prod'ni yarat:

```
mv .env .env.poc
scripts/create-env.sh --production ohw.markaz.uz
```

Skript o'zi qo'yadi: yangi `DJANGO_SECRET_KEY`, baza paroli (`POSTGRES_PASSWORD` va `DATABASE_URL` da bir xil), `DJANGO_DEBUG=false`, domen, `MEDIA_ROOT=/data/media`, `DOCKER_GID` (worker Docker'ga ulanishi uchun), superadmin eshigining siri (`ADMIN_GATE_SECRET`) va gunicorn sozlamalari. Qolgan qiymatlar `.env.example` dagidek; kerak bo'lsa `nano .env` bilan o'zgartir:

- `JUDGE_SLOTS=heavy:1,fast:1` — parallel tekshiruvlar. Server kuchaytirilganda faqat shu o'zgaradi.
- `JUDGE_RESERVED_MEMORY_MB=3072` — sayt va baza uchun RAM. Worker ishga tushganda slotlar sig'ishini tekshiradi; sig'masa, logda aniq xabar bilan to'xtaydi.
- `TIME_ZONE=Asia/Tashkent`.

`.env` faqat serverda turadi: git'ga tushmaydi, image ichiga ham kirmaydi. Uning nusxasini xavfsiz joyda saqla — yo'qolsa, baza paroli ham yo'qoladi.

## 6. Ishga tushirish

```
make deploy
```

Birinchi marta image yig'iladi (Python paketlari, Tailwind binari GitHub'dan, `collectstatic`) — bir necha daqiqa. Oxirida `make deploy` servislar holatini ko'rsatadi: `migrate` — `Exited (0)` (o'z ishini qilib to'xtagan), qolganlari — `running`. Worker ishga tushganda xotira sig'ishini va base image'lar borligini tekshiradi; muammo bo'lsa, logida nima qilish kerakligini yozadi (10-bo'lim).

Superadmin hisobi:

```
docker compose -f compose.prod.yml exec web python manage.py createsuperuser
```

Superadmin paneli internetdan ochilmaydi: unga SSH tunnel orqali kirasan (12-bo'lim). Panelda markaz va markaz menejerini yarat. Menejer saytning xodimlar eshigidan (`https://<domen>/staff/login/`) kirib adminlarni qo'shadi, admin esa o'qituvchi, o'quvchi va guruhlarni.

### Tekshiruv ro'yxati

- [ ] `http://<domen>` → `https://<domen>` ga o'tadi, brauzer qulf belgisini ko'rsatadi.
- [ ] O'qituvchi `examples/dart-cart/task` papkasining zipini yuklaydi → bir necha soniyada "Tayyor".
- [ ] O'quvchi `examples/dart-cart/submissions/ok/` ning zipini yuboradi → "Qabul qilindi".
- [ ] `make prod-logs SERVICE=worker` da `job N: done` qatorlari.

## 7. Zaxira nusxalar (cron)

`crontab -e` va oxiriga qo'sh (yo'lni o'zingnikiga moslashtir):

```
30 2 * * * cd /home/ubuntu/online-home-work && scripts/backup.sh db >> backups/backup.log 2>&1
45 2 * * 0 cd /home/ubuntu/online-home-work && scripts/backup.sh media >> backups/backup.log 2>&1
0 4 * * 0 docker image prune -f >> /home/ubuntu/online-home-work/backups/backup.log 2>&1
```

- Har kecha baza (`backups/db-*.sql.gz`, oxirgi 14 tasi), har yakshanba fayllar (`backups/media-*.tar.gz`, oxirgi 4 tasi).
- `docker image prune -f` faqat nomsiz (keraksiz) qatlamlarni o'chiradi; topshiriq image'lariga tegmaydi.
- Zaxira o'sha serverda turibdi: server yo'qolsa, u ham yo'qoladi. Vaqti-vaqti bilan `backups/` ni o'z kompyuteringga ko'chir (`scp`); keyin Object Storage'ga avtomatik (Phase 2).

Bazani zaxiradan tiklash (avval saytni to'xtat):

```
docker compose -f compose.prod.yml stop web worker
gunzip -c backups/db-YYYYMMDD-HHMM.sql.gz | docker compose -f compose.prod.yml exec -T db psql -U ohw -d ohw
docker compose -f compose.prod.yml start web worker
```

(Bo'sh bazaga tiklanadi: kerak bo'lsa avval `docker compose -f compose.prod.yml exec db dropdb -U ohw ohw` va `createdb -U ohw ohw`.)

## 8. Yangilash

```
cd ~/online-home-work
git pull
make deploy
```

`make deploy` image'ni qayta yig'adi, migratsiyalarni qo'llaydi va o'zgargan servislarni qayta ishga tushiradi. Worker to'xtatilganda yangi ish olmaydi, boshlanganlarini tugatadi (6 daqiqagacha kutiladi); navbatdagi yechimlar yo'qolmaydi — yangi worker ularni oladi.

## 9. Kundalik buyruqlar

| Nima | Buyruq |
|---|---|
| Holat | `docker compose -f compose.prod.yml ps` |
| Loglar (hammasi / bittasi) | `make prod-logs` / `make prod-logs SERVICE=worker` |
| Bitta servisni qayta ishga tushirish | `docker compose -f compose.prod.yml restart worker` |
| Django shell | `docker compose -f compose.prod.yml exec web python manage.py shell` |
| Hozir zaxira | `make backup` |
| Disk | `df -h` va `docker system df` |

## 10. Muammolar

| Belgi | Sabab va yechim |
|---|---|
| Brauzer saytni ochmaydi, `curl http://<domen>` javob bermaydi | 80/443 portlari yopiq: 2-qadamning ikkala qismini tekshir. |
| Sertifikat xatosi, `make prod-logs SERVICE=caddy` da `challenge failed` | DNS hali serverga ishora qilmaydi yoki 80-port yopiq. DNS tarqalishi bir necha daqiqadan bir necha soatgacha. |
| `502 Bad Gateway` | `web` hali ishga tushmoqda yoki yiqilgan: `make prod-logs SERVICE=web`. |
| Worker logida `can't reach Docker` yoki `Permission denied` | `.env` dagi `DOCKER_GID` noto'g'ri: `getent group docker` dagi raqamni qo'y, `make deploy`. |
| Worker logida `the slots need ... MB` | Slotlar RAM'ga sig'maydi: `JUDGE_SLOTS` ni kamaytir yoki `JUDGE_RESERVED_MEMORY_MB` ni tekshir. |
| Topshiriq "Yig'ilmoqda" da qotib qoldi | Worker ishlamayapti: `docker compose -f compose.prod.yml ps worker`, keyin uning loglari. |
| Worker logida `base images missing on this node` | Base image yo'q yoki `.env` dagi versiya boshqa: `make base-images` (4-qadam), keyin `make deploy`. |

## 11. Oracle Always Free haqida

- Instance uzoq vaqt deyarli bo'sh tursa (CPU, tarmoq, xotira 7 kun davomida juda past), Oracle uni to'xtatishi mumkin. Ta'til paytlarida konsolda holatini kuzatib tur; to'xtasa — konsoldan *Start*, servislar o'zi qaytadi (`restart: unless-stopped`).
- Ikkinchi server qo'shish (keyin): yangi serverda faqat `worker` ishga tushiriladi — o'sha `DATABASE_URL` va umumiy storage bilan (SPEC §3.9). Buning uchun baza tarmoqqa ochilishi va media umumiy bo'lishi kerak; bu alohida vazifa.

## 12. Superadmin paneli (faqat SSH orqali)

`/admin/` internetdan ochilmaydi: `https://<domen>/admin/` har doim 404 beradi. Panelning alohida "maxfiy eshigi" bor: Caddy uni faqat serverning o'zida, `127.0.0.1:8443` da ochadi. Unga SSH tunnel bilan kirasan — parol o'g'irlansa ham, serverga SSH kaliti bo'lmagan odam panelga yetib bora olmaydi.

1. Laptopda tunnelni och (terminal ochiq tursin):

   ```
   ssh -i ~/.ssh/oracle_server -N -L 8443:127.0.0.1:8443 ubuntu@SERVER_IP
   ```

2. Brauzerda `https://localhost:8443/admin/` ni och. Sertifikat Caddy'ning o'zi bergani uchun brauzer bir marta ogohlantiradi: *Advanced → Proceed to localhost*. Trafik baribir SSH ichida shifrlangan.
3. Superadmin login va paroli bilan kir. Ish tugagach, tunnel terminalida Ctrl+C.

Eski `.env` da `ADMIN_GATE_SECRET` bo'lmasa, `make deploy` "set ADMIN_GATE_SECRET in .env" deb to'xtaydi. Serverda bir marta qo'sh:

```
echo "ADMIN_GATE_SECRET=$(head -c 48 /dev/urandom | base64 | tr -d '/+=\n')" >> .env
make deploy
```
