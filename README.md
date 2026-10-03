# Обновления игр Valve

Страница с графиками: насколько часто, насколько крупно и на какую аудиторию Valve обновляет **Deadlock, CS2, Dota 2 и Team Fortress 2**. Данные с мая 2024 года (первый публичный журнал изменений Deadlock) по начало октября 2026.

Живая версия: https://dykomenko.github.io/valve-update-history/

## Что внутри

| Путь | Что это |
|---|---|
| `index.html` | готовая страница (данные вшиты, внешних библиотек нет) |
| `src/index.template.html` | исходник страницы |
| `data/updates.json` | все посчитанные данные: события, помесячные ряды, сводки |
| `data/deadlock_ccu.json` | проверенные месячные пики онлайна Deadlock с источниками |
| `data/deadlock_forum.psv` | число строк в каждом посте журнала на форуме Deadlock (без текста постов) |
| `scripts/` | загрузка и сборка |

## Как пересобрать

```bash
pip install requests beautifulsoup4 lxml
export RAW_DIR=raw                      # куда складывать скачанное (в git не попадает)

python scripts/fetch_news.py            # Steam News: CS2, Dota 2, Deadlock, TF2
python scripts/fetch_dota.py            # патчи Dota 2 с dota2.com
python scripts/fetch_gt.py              # история SteamDatabase/GameTracking-* (нужен gh CLI)
python scripts/fetch_online.py          # SteamCharts, steamdb.com, вики Deadlock
python scripts/build_data.py            # -> data/updates.json
python scripts/build_page.py            # -> index.html
```

Форум Deadlock закрыт проверкой браузера, поэтому его читают из обычной вкладки браузера: `scripts/forum_changelog.js`
выводит таблицу, которую нужно сохранить в `data/deadlock_forum.psv`.

## Как считается

* **Обновление** — день, когда Valve опубликовала патчноуты (несколько постов за день = одно).
* **Строка патчноутов** — один пункт списка изменений. Это мера объёма, а не качества.
* **Размер** — микро (<10 строк), малые (10–29), средние (30–99), крупные (100+). Посты Deadlock о выходе героя без списка изменений — отдельная категория «релиз без списка».
* **Сборки в Steam** — число дней в месяце с коммитом в `SteamDatabase/GameTracking-*` (ловит и тихие обновления).
* **Онлайн** — месячные пики со SteamCharts; у Deadlock публичной статистики нет, поэтому только проверенные месяцы (SteamDB в пересказе прессы и запись steamdb.com с июля 2026).
* **Строк на 100 тыс. игроков** — строки патчноутов в месяц, делённые на типичный (медианный) месячный пик онлайна в сотнях тысяч.

Подробности и ограничения — в разделе «Как это считалось» на странице.

Тексты патчноутов Valve в репозиторий не входят: хранятся только даты, названия и счётчики.
