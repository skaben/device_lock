# skaben_lock

Клиент SKABEN тип "Замок лазерной двери".

Игровая функция - ограничение доступа в игровые зоны (имитация силового поля при помощи красных лазеров).

Игровое взаимодействие:

- ввод кода с цифровой клавиатуры
- сброс кода клавишей *
- подтверждение ввода клавишей #
- прикладывание карты доступа (RFID)

При успешной аутентификации (кодом или картой) лазеры замка отключаются на
определенный в конфигурации период времени (по умолчанию 10 секунд)

В зависимости от режима работы базы временной интервал может изменяться. (cм.
описание конфигуратора SKABEN сервера)

как поставить:

`./pre-run.sh install`\
конфигурация системы - `conf/system.yml`\
[описание параметров конфигурации](https://github.com/skaben/device_boilerplate)