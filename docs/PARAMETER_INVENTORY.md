# ESEPTEP: инвентаризация параметров и границы настройки

Аудит исходного кода базовой версии PR #73 (`170e0a4`), 17 ноября 2026.
Это описание реализации, а не подтверждение строительных норм. Изменений формул аудит не делает.
Ссылки ниже используют функции/идентификаторы, чтобы оставаться полезными после сдвигов строк.

## Классификация

- **Цена**: KZT за явно указанную единицу. Не является нормой расхода.
- **Норма/допущение**: количество, запас, геометрический коэффициент, комплектация. Для редактирования требуется единица, диапазон, источник методики и регрессионные эталоны.
- **Матрица**: набор контрольных площадей, комплектов и/или исторических бюджетов. Нельзя превращать бюджет в цену товара или считать его автоматически нормативом.
- **Технические параметры**: входные ключи, единицы, варианты, ограничения точности, маршрутизация. Не должны редактироваться как хозяйственные цены.

## Общие источники

| Источник | Что содержит | Граница настройки |
|---|---|---|
| `calculators/definitions.py: CALCULATORS`, `_material` | Заголовки, единицы, исходные цены, `ratio`, поля/опции и defaults, предупреждения | Metadata не равно runtime формула; большинство отдельных функций используют собственные правила |
| `definitions.py: SEGMENTS` | material multipliers 0.9/1/1.22, labor 5500/7500/10500 | Проверять фактический caller: многие пути используют `PLAIN_REFERENCE`, а не SEGMENTS |
| `definitions.py: *_FIELDS`, `*_MASTER_TEMPLATE_GROUPS` | Технические ключи форм, допустимые опции, заготовки ведомостей | Не менять ключи/POST/единицы ради перевода; шаблон мастера не обязательно runtime BOM |
| `calculators/validation.py` | MAX_AREA=10000, MAX_COUNT=100, максимум 2 десятичных знака, допустимые варианты | Ограничения приложения, НЕ строительные нормы |
| `services.py: calculate_materials` | Dispatch всех 12 алгоритмов; fallback `_calculate_ratio_based` | Не добавлять редактор исполняемых формул/eval |
| `services.py: _variant_row`, `_round_quantity`, `_build_result`, `_build_variant_result` | Округление количеств/денег, суммы, copy payload | Изменение округления меняет результат и требует версии методики |
| `calculators/models.py: CalculatorCategory/CalculatorTemplate` | Категории и метаданные | Эти модели не управляют ценами и коэффициентами 12 функций |
| `calculators/material_registry.json`, `material_keys.py` | Стабильные ключи материала+единицы | Append-only идентичность; не переименовывать ключи при локализации |
| `calculators/pricing.py`, `PriceBook/MaterialPrice` | Отдельное админ-предложение по строкам расчёта, версия и покрытие | Не меняет исходные количества/справочные суммы; частичная сумма не является полным бюджетом |

## Все 12 алгоритмов

Все функции ниже находятся в `calculators/services.py`; справочные описания/материалы также находятся в `definitions.py`.

| Калькулятор / функция | Цены | Нормы, геометрия, комплектация | Матрицы и ограничения |
|---|---|---|---|
| Демонтаж `_calculate_demontazh` | Inline `_variant_row`, отдельные цены base/optimal/maximum, вывоз/контейнеры | Мешки зависят от cosmetic/partial/full; film=ceil(area*1.2); скотч/перчатки/рейсы/диски от площади с делителями и minimum1 | Укрупнённый расчёт, без фактической массы/объёма демонтируемого материала; услуги вывоза смешаны с расходниками |
| Электрика `_calculate_elektrika`, `_electric_quantities`, `_scaled_electric_quantities` | `ELECTRIC_COMFORT_PRICES`, `ELECTRIC_VARIANT_TOTAL_RATIOS`, `_electric_rows` | Формулы по площади/комнатам; группы `ELECTRIC_AREA_DEPENDENT/ROOM_DEPENDENT/FIXED`, зависимые подрозетники/клеммы/крепёж | `ELECTRIC_COMFORT_REFERENCE_TOTALS`, `ELECTRIC_REFERENCE_MATRIX`; nearest selection с весом комнат. Округлённая площадь может выбрать комплект целого эталона. Варианты преимущественно масштабируют цену, хотя текст обещает комплектацию |
| Сантехника `_calculate_santehnika` | Local `price_sets` для трёх вариантов; Business extra=150000 | `kitchen_point=1`; отдельные коэффициенты длины труб/фитингов по площади и числу санузлов; fixed collectors | Business extra явно не имеет состава. Нельзя выдавать его за цену конкретных материалов |
| Штукатурка `_calculate_shtukaturka` | `_row_by_title` берёт цены definitions | wall=area*3; opening loss=10%; смесь ceil(net*thickness*0.30); грунтовка max1/int(net/18); fixed инструменты/расходники | Площадь стен и проёмы не измерены. Округление грунтовки вниз требует отдельной методологической проверки |
| ГКЛ `_calculate_gipsokarton`, `_drywall_quantities` | Prices внутри `DRYWALL_REFERENCE_MATRIX`; `_drywall_variant_from_comfort` выводит цену пропорцией target_total/comfort_total | `DRYWALL_AREA_DEPENDENT/PERIMETER_DEPENDENT`; `_drywall_perimeter` и overrides | `DRYWALL_REFERENCE_MATRIX` по ceiling/wall/partition; `DRYWALL_PERIMETER_OVERRIDES`; rounded-area exact detection. Бюджетное масштабирование цены не подтверждает товар/комплектацию |
| Наливной пол `_calculate_nalivnoy_pol` | Definitions через `_self_level_row` | Расход area*thickness*15; мешки25кг; fixed tools; игольчатый валик зависит от толщины | `SELF_LEVEL_REFERENCE_MATRIX`, `SELF_LEVEL_AREA_DEPENDENT`; nearest с весом толщины20. Historical total не подгоняет текущую сумму; расход не привязан к паспорту продукта |
| Плитка `_calculate_plitka`, `_tile_comfort_materials` | Цены строк `TILE_REFERENCE_MATRIX`; варианты через `_drywall_variant_from_comfort` | Масштабирование количеств с ceil; zone и tile_format выбирают комплект | `TILE_REFERENCE_MATRIX`, exact по round(area); fractional area может получить целый эталон без масштабирования. Текст расхода грунта/клея в metrics не самостоятельная проверка нормативов |
| Ламинат/SPC/паркет `_calculate_laminat_spc_parket`, `_flooring_materials` | Inline prices покрытий/клея/грунта/common_tail | direct ceil(area*1.05), diagonal*1.12, herringbone*1.18; клей1.23, грунт0.24; плинтус override или area*0.5+9 | `FLOORING_PLINTH_OVERRIDES/REFERENCE_TOTALS`; final `_build_flooring_result` суммирует строки, игнорирует legacy exact_total. Материалы рассчитаны для direct: другие раскладки только metrics |
| Малярка `_calculate_malyarka`, `_painting_materials` | Цены материалов `PAINTING_REFERENCE_MATRIX` | wall=floor*3 минус10%; коэффициенты `PAINTING_VARIANT_QUANTITY_COEFFICIENTS`, ceil quantities | `PAINTING_REFERENCE_MATRIX` по finish_type; target_total передаётся, но `_painting_materials` его не использует для подгонки суммы |
| Натяжной потолок `_calculate_natyazhnoy_potolok` | Inline comfort prices | perimeter=round(area*1.35); profile ceil(*1.06); свет ceil(area/8); cable=lights*5; niche=rooms; `CEILING_VARIANT_QUANTITY_COEFFICIENTS` | `CEILING_REFERENCE_TOTALS`/nearest используются для legacy target; `_ceiling_variant_from_comfort` считает строки, target_total не подгоняет их |
| Двери `_calculate_dveri` | Definitions через `_row_by_title` | Количества от count и fixed minimum | Одновременно обычный/магнитный замок и обычные/скрытые петли. Требуется решение о взаимоисключающих опциях, не просто правка цен |
| Тёплый пол `_calculate_teplyy_pol`, `_warm_floor_comfort_materials` | Inline цены для electric_mat/electric_cable/water | reserve ceil(area*1.05), contours ceil(area/15), cable area*9, water pipe area*6, другие коэффициенты; `WARM_FLOOR_VARIANT_QUANTITY_COEFFICIENTS` | `WARM_FLOOR_REFERENCE_TOTALS` и legacy target; `_warm_floor_variant_from_comfort` target не подгоняет. Нет теплотехнического расчёта/гидравлики/нагрузок |

Наличие матрицы ещё не означает влияние её поля `total` на итог. До переноса константы в БД нужно пройти caller и проверить зависимость результата. Не восстанавливать удалённую подгонку итогов под legacy бюджеты.

## Ремонт под ключ и загруженный проект

- `marketplace/views.py: TURNKEY_PACKAGES`: economy120000 / standard170000 / premium250000 KZT/м²; длительности45/60/75 дней и списки пакетов — отдельные описательные обещания. `marketplace_home` считает площадь × ставку. `CITIES/DEVELOPERS` ограничивают выбор, но НЕ меняют ставку.
- `projects/views.py: REPAIR_LEVEL_RATES`: те же три ставки. `project_upload` рассчитывает бюджет из введённой пользователем площади. `AI_ANALYSIS_MODE='demo'` и `DEMO_AI_SUMMARY` НЕ извлекают размеры/материалы из загруженного плана.
- На базовой версии GET существующего ProjectUpload заново умножает area на hardcoded rate; отдельного сохранённого итогового snapshot нет. Поэтому замена rates на live DB без snapshot изменит старые бюджеты при открытии.

### Безопасная первая настройка

Единая типизированная неизменяемая опубликованная редакция трёх ставок KZT/м². Явная активация администратором; черновик не влияет на сайт; только один активный набор; защита от гонки публикации. Legacy fallback с прежними значениями сохраняет поведение без настройки.

Для нового/явно пересчитанного загруженного проекта сохранить area, package_key, rate, total, currency, rate_version, source_note и дату в snapshot. GET/переключение языка читает snapshot, не считает по текущему прайсу. Для старого upload без snapshot — прежняя legacy ставка и честная отметка происхождения, НЕ ретроактивно текущая активная. Не объявлять момент миграции датой исторического расчёта. Доступ сохраняет owner/session isolation.

Ремонтные ставки не включают в себя редактирование коэффициентов всех12 калькуляторов: такое утверждение было бы неверным.

## Методологические блокеры перед расширением настроек

1. Зафиксировать источники расхода, единицы, упаковки, технологические условия и версию методики. Не выдумывать нормативы по названию материала.
2. Решить дробные площади возле эталонов, правила округления расходников/упаковок и монотонность. Существующие тесты consistency не подтверждают инженерную точность.
3. Определить реальные комплектации вариантов; сейчас у части вариантов изменяется цена/коэффициент без соответствующих SKU.
4. Развести материалы, инструменты, услуги вывоза и дополнительные пакетные суммы.
5. Решить дверные альтернативы, выбор раскладки покрытия, фактическую геометрию стен/проёмов и пользовательские обмеры.
6. Электрика/теплопол — предварительный бюджет, не инструкция монтажа и не проект безопасности.
7. Цена/остаток поставщика не подтверждены технически; updated_at не доказывает проверку цены. Exact title+unit — кандидат, не совместимость.
8. Проверять новые ставки и параметры на неизменность исторических снимков, RU/KK, права, concurrency, Decimal и предельную точность БД.
