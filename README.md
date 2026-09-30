# L03 · Золотий набір і ранер

Демо-набір із 14 кейсів, ранер курсу і дошки до лабораторної заняття L03
курсу з тестування LLM-агентів. Набір перевіряє бота підтримки PayPilot:
правильні відповіді в кейсах рахує код банку — рушії стенду, а сам набір
проганяється на справній версії стенду і на зламаній.

Python локально не потрібен: ранер іде в Docker, у голому образі
`python:3.12-slim`, без збирання і без залежностей. Ключ API цьому
репозиторію теж не потрібен: ранер ходить у стенд по HTTP, а ключ моделі
живе в `.env` стенду.

## Що зробити, коротко

Корінь курсу завжди `~/paypilot`: стенд у `~/paypilot/paypilot-stand`, цей
репозиторій — у `~/paypilot/l03` (папка уроку, поруч із `l02`).

1. Підняти локальний стенд: у `~/paypilot/paypilot-stand` — `docker compose up -d --build`, потім `docker compose exec stand python scripts/doctor.py`.
2. Склонувати цей репозиторій поруч зі стендом:
   `git clone https://github.com/sergeytkachenko/paypilot-l03-eval.git ~/paypilot/l03`
3. `cd ~/paypilot/l03` і перевірити набір: `docker compose run --rm eval --dry-run`.
4. Прогнати набір на справній версії: `docker compose run --rm eval --profile clean`.
5. Прогнати на зламаній: `docker compose run --rm eval --profile lesson-03`.

Команди влаштовані як на L02: усе після `eval` — прапорці.

Деталі кожного кроку нижче.

## Що в репозиторії

| Файл | Що це |
|---|---|
| `complaints.md` | двадцять скарг C-01…C-20, той самий корпус, що на L02 |
| `triage.md` | дошка кроку 1: скарги в трьох купках за відтворюваністю — придатні одразу, після добору контексту, непридатні |
| `case-FX-004.json` | перший кейс набору, розгорнутий по полях |
| `sets/l03.jsonl` | демо-набір: 14 кейсів, по одному на рядок; його читає ранер |
| `generate_from_engines.py` | генератор: викликає рушії стенду і друкує кейси з готовими очікуваннями |
| `ladder.md` | дошка драбини перевірок: рівень перевірки для кожного кейса |
| `gaps.md` | дошка «чого набір не ловить» |
| `runner.py`, `loader.py`, `assertions.py`, `stand.py`, `judge.py`, `console.py` | ранер курсу, лише стандартна бібліотека Python |
| `validate.py` | друкує `set_hash` і покриття набору |
| `cli.py` | розбирає прапорці запуску, перемикає профіль стенду і викликає ранер |
| `docker-compose.yml`, `.env.example` | запуск у Docker і шаблон `.env` |

## Що потрібно

- Docker Desktop (macOS, Windows) або Docker Engine з compose (Linux).
- Піднятий **локальний** стенд `~/paypilot/paypilot-stand` на
  `http://localhost:8000` із живою моделлю: `doctor.py` показує
  `llm provider [OK]`. Ранер скидає базу стенду перед кожним кейсом, тому на
  спільному стенді його не запускай.
- Каталог стенду на цьому ж комп'ютері: ранер і генератор імпортують з нього
  рушії (`app/engines`). Клонуй цей репозиторій у `~/paypilot/l03`, поруч зі
  стендом: тоді шлях за замовчуванням (`../paypilot-stand`) уже правильний.

## Запуск

```bash
mkdir -p ~/paypilot
git clone https://github.com/sergeytkachenko/paypilot-l03-eval.git ~/paypilot/l03
cd ~/paypilot/l03
docker compose run --rm eval --dry-run
```

`--dry-run` нічого не викликає: друкує хеш набору і зведення — скільки
кейсів, які оракули, які рівні перевірок. Для демо-набору перший рядок —
`set l03.jsonl set_hash 87e42e249737`. Два прогони можна порівнювати, лише
коли хеш однаковий: зміниш хоч один символ у наборі — зміниться хеш.

Прогін і код повернення:

```bash
docker compose run --rm eval --profile clean
echo $?
```

`--profile` перемикає стенд на названий профіль перед прогоном і чекає,
поки стенд почне приймати запити. Без `--profile` ранер профіль не чіпає:
ганяє той, що зараз на стенді. Який профіль був у прогоні, видно в першому
рядку виводу.

Ранер ставить боту кейси набору по одному, перед кожним скидає базу стенду
і друкує блок на кейс: рядок із `PASS` або `FAIL`, рівнем і назвою
перевірки, а під ним — питання, що очікувалося, кожен виклик інструмента з
аргументами і результатом, вердикт і початок відповіді бота. У звіт по
подробиці ходити не треба. Із `--brief` лишається по рядку на кейс. Колір є
лише в терміналі; змінна `NO_COLOR` його вимикає.

```text
FAIL  FX-004     L2 generation  tool_grounded_numeric  3.2s, 4876 tokens
      question  I'm CUS-0007. Convert 2000 EUR to USD. What is the final amount I receive?
      expected  quote_fx.final_amount = 2154.35 +/-0.02, and the same figure in the answer
      tool      quote_fx(customer_id=CUS-0007, amount=2000, from_currency=EUR, to_currency=USD)
                -> final_amount=2157.608696, from_currency=EUR, to_currency=USD, …
      verdict   quote_fx.final_amount = [2157.608696], expected 2154.35 +/-0.02
      answer    Here's your conversion breakdown: …
```

Демо-набір — 14 звернень до бота, близько хвилини. Код
повернення — 0, якщо пройшли всі кейси, і 1, якщо впав хоч один; у
PowerShell його показує `$LASTEXITCODE`. Читай його одразу після прогону:
будь-яка команда між ними його перезапише. І не додавай до прогону `| tee`:
після конвеєра `$?` — це код `tee`.

Далі те саме з `--profile lesson-03`: справна версія дає точку відліку, а
зламана перевіряє сам набір. Якщо набір на ній не червоніє, слабкий набір, а
не бот. Після прогонів стенд лишається на останньому профілі.

## Прапорці

| Прапорець | Що робить |
|---|---|
| `--profile clean` | перемикає стенд на профіль перед прогоном |
| `--only FX-004,LIM-003` | лише названі кейси |
| `--set l03` | який набір читати: `sets/<назва>.jsonl` |
| `--gate daily` | кейси якого гейта: `daily`, `release` або `all`; за замовчуванням `daily` |
| `--brief` | по рядку на кейс, без подробиць |
| `--dry-run` | хеш і покриття набору, нічого не викликає |

```bash
docker compose run --rm eval --profile clean --only FX-004,LIM-003
```

Профіль можна перемкнути й без прогону — у чаті стенду
(`http://localhost:8000`, бічна панель, блок «Профіль заняття») або з
термінала:

```bash
curl -s -X PUT localhost:8000/api/_test/profile \
  -H 'Content-Type: application/json' -d '{"profile":"clean"}'
```

## Мок моделі

Частина 4 заняття перевіряє виклики інструментів без моделі. Між стендом і
API моделі стає MockServer: стенд, як і завжди, шле запит на адресу
провайдера, але йде через проксі (`HTTPS_PROXY`) і довіряє його
сертифікату (`SSL_CERT_FILE`), а відповідає мок за сценарієм з
`mock/expectations.json`. Код стенду не змінюється, ключ не потрібен:
запит до моделі не доходить. Override-файл перемикає стенд на провайдер
`openai` з фіктивним ключем, бо для мока провайдер — лише формат запиту.

```bash
cd ~/paypilot/l03
docker compose up -d llm-mock
cd ~/paypilot/paypilot-stand
docker compose -f docker-compose.yml -f ../l03/mock/stand.override.yml up -d --force-recreate stand
cd ~/paypilot/l03
docker compose run --rm eval --set l03-mock --profile clean
```

Набір `sets/l03-mock.jsonl` — ті самі FX-004, LIM-003 і DIS-006 плюс
FX-004-CALL: перевірка `tool_called_with`, що стенд виконав саме той
виклик, який повернула «модель», з тими самими аргументами. На `clean` має
бути 4/4, на `lesson-03` — 1/4: виклик правильний, результати інструментів
ні.

Що стенд надіслав моделі, показує журнал мока, а `verify` перевіряє
взаємодію: чи повернув стенд результат інструмента у другому запиті.

```bash
docker compose run --rm eval python mock/journal.py
curl -s -o /dev/null -w '%{http_code}\n' -X PUT localhost:1080/mockserver/verify \
  -H 'Content-Type: application/json' -d @mock/verify-fx-004.json
```

`202` — перевірка пройшла; інакше MockServer друкує, що очікував і що
отримав. Повернути справжню модель:

```bash
cd ~/paypilot/paypilot-stand
docker compose up -d --force-recreate stand
cd ~/paypilot/l03
docker compose stop llm-mock
```

Сертифікат `mock/mockserver-ca.pem` — стандартний CA MockServer, його
приватний ключ опублікований у репозиторії MockServer, тому цей мок
годиться лише для локального стенду. `/health` за проксі й далі показує
`"provider":"openai"`: чи стенд за моком, видно з журналу мока, а не зі
стенду.

## Змінні ранера

Те саме, що прапорці, але через оточення; прапорець сильніший за змінну.
Передаються через `-e` після `--rm`:

| Змінна | Що робить |
|---|---|
| `SET=l03` | який набір читати: `sets/<SET>.jsonl`; за замовчуванням `l03`. `validate.py` читає ту саму змінну |
| `CASE=FX-004,LIM-003` | лише названі кейси |
| `GATE=daily` | лише кейси щоденного гейта, це значення за замовчуванням; `GATE=release` — лише релізні, `GATE=` — усі |
| `BRIEF=1` | по рядку на кейс, без подробиць |

```bash
docker compose run --rm -e CASE=FX-004,LIM-003 eval
```

Свій набір для домашнього завдання клади поруч із демо-набором, у
`sets/<назва>.jsonl`, і запускай із `--set <назва>`.

Команди з `python` після `eval` працюють як раніше:
`docker compose run --rm eval python validate.py`.

## Генератор

```bash
docker compose run --rm eval python generate_from_engines.py > sets/_generated.jsonl
```

Генератор викликає рушії стенду напряму, без бота й моделі: працює за
секунду й нічого не коштує. Кейси він друкує у стандартний вивід, а рядок
`# 21 cases generated from the engines` — у потік помилок, тому його видно
в терміналі, а не у файлі. Не пиши вивід генератора в `sets/l03.jsonl`:
перезапишеш демо-набір, і зміниться `set_hash`.

У Windows PowerShell 5.1 `>` пише файл у кодуванні UTF-16, і такий набір
ранер не прочитає. У PowerShell 7 (`pwsh`), macOS і Linux файл виходить у
UTF-8.

## Звіти

Кожен прогін пише JSON-звіт у `reports/` цього каталогу:
`reports/<набір>-<профіль>-<час>.json`. У ньому `set_hash`,
`prompt_version`, профіль, вердикт кожного кейса і відповіді бота. Ранер
друкує шлях як `evals/reports/…`: так його бачить контейнер, а файл лежить
у `reports/`. На Linux файли звітів належать користувачу root: читати їх
можна, видаляти — через `sudo`.

## `.env`

Файл необов'язковий: без нього діють значення за замовчуванням. Якщо треба
їх змінити — `cp .env.example .env`.

| Змінна | Що це |
|---|---|
| `STAND_DIR` | шлях до каталогу `paypilot-stand`, за замовчуванням `../paypilot-stand`. Windows: `C:/paypilot/paypilot-stand` |
| `EVAL_STAND_URL` | адреса стенду зсередини контейнера, за замовчуванням `http://host.docker.internal:8000`, див. нижче |

`judge.py` — модель-суддя для перевірок рівня 7. У демо-наборі таких
перевірок немає, тож ключ судді на цьому занятті не потрібен.

## Адреса стенду

Усередині контейнера `localhost` — це сам контейнер, а не твій комп'ютер.
Тому сервіс `eval` ходить на стенд через `http://host.docker.internal:8000`.
Стенд на іншому порту — задай `EVAL_STAND_URL` у `.env`, наприклад
`http://host.docker.internal:8010`.

Linux, стенд опублікований лише на `127.0.0.1`: `host.docker.internal` туди
не дістане. Бери сервіс `eval-host`, він працює в мережі хоста й ходить на
`http://127.0.0.1:8000`:

```bash
docker compose --profile host run --rm eval-host
```

Змінні й команди в нього ті самі, що в `eval`. Стенд на іншому порту — у
`.env` задай `EVAL_STAND_URL=http://127.0.0.1:<порт>`.
